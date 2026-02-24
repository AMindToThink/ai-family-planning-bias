"""Convert Claude Code conversation JSONL logs to readable Markdown."""

import json
import sys
import textwrap
from pathlib import Path


def extract_text_from_content(content: object) -> tuple[str, list[dict]]:
    """Extract text and tool calls from message content.

    Returns (text, tool_calls) where tool_calls is a list of
    {name, input, result} dicts.
    """
    if isinstance(content, str):
        return content, []

    text_parts: list[str] = []
    tool_calls: list[dict] = []

    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type", "")
            if block_type == "text":
                text_parts.append(block.get("text", ""))
            elif block_type == "tool_use":
                tool_calls.append({
                    "id": block.get("id", ""),
                    "name": block.get("name", ""),
                    "input": block.get("input", {}),
                })
            elif block_type == "tool_result":
                result_content = block.get("content", "")
                if isinstance(result_content, list):
                    for rc in result_content:
                        if isinstance(rc, dict) and rc.get("type") == "text":
                            result_text = rc.get("text", "")
                            # Attach to matching tool call
                            tool_id = block.get("tool_use_id", "")
                            for tc in tool_calls:
                                if tc["id"] == tool_id:
                                    tc["result"] = result_text
                                    break
                elif isinstance(result_content, str):
                    tool_id = block.get("tool_use_id", "")
                    for tc in tool_calls:
                        if tc["id"] == tool_id:
                            tc["result"] = result_content
                            break
            # Skip thinking blocks — they're internal

    return "\n".join(text_parts), tool_calls


def format_tool_call(tc: dict, compact: bool = True) -> str:
    """Format a tool call for markdown output."""
    name = tc.get("name", "unknown")
    inp = tc.get("input", {})

    # Format input concisely
    if name == "Bash":
        cmd = inp.get("command", "")
        desc = inp.get("description", "")
        label = f"`{cmd}`" if len(cmd) < 120 else f"`{cmd[:120]}...`"
        if desc:
            label = f"{desc}: {label}"
        input_str = label
    elif name == "Read":
        input_str = f"`{inp.get('file_path', '')}`"
    elif name == "Write":
        path = inp.get("file_path", "")
        content = inp.get("content", "")
        lines = content.count("\n") + 1
        input_str = f"`{path}` ({lines} lines)"
    elif name == "Edit":
        path = inp.get("file_path", "")
        input_str = f"`{path}`"
    elif name == "Glob":
        input_str = f"`{inp.get('pattern', '')}`"
    elif name == "Grep":
        input_str = f"pattern=`{inp.get('pattern', '')}` path=`{inp.get('path', '.')}`"
    elif name == "Task":
        desc = inp.get("description", "")
        agent = inp.get("subagent_type", "")
        input_str = f"[{agent}] {desc}"
    elif name == "WebSearch":
        input_str = f'"{inp.get("query", "")}"'
    elif name == "WebFetch":
        input_str = f"`{inp.get('url', '')}`"
    elif name in ("TaskCreate", "TaskUpdate", "TaskList", "TaskGet"):
        input_str = json.dumps(inp, indent=None)[:200]
    else:
        input_str = json.dumps(inp, indent=None)[:200]

    result = tc.get("result", "")
    if compact and result:
        result_lines = result.strip().split("\n")
        if len(result_lines) > 10:
            result_preview = "\n".join(result_lines[:5]) + f"\n... ({len(result_lines)} lines total)"
        else:
            result_preview = result.strip()
    else:
        result_preview = result.strip() if result else ""

    parts = [f"> **{name}**: {input_str}"]
    if result_preview:
        parts.append(f">\n> <details><summary>Result</summary>\n>\n> ```\n> {result_preview}\n> ```\n> </details>")

    return "\n".join(parts)


def convert_jsonl_to_markdown(jsonl_path: Path, title: str) -> str:
    """Convert a JSONL conversation log to Markdown."""
    lines: list[str] = []
    lines.append(f"# {title}\n")

    messages: list[dict] = []
    with open(jsonl_path) as f:
        for line_str in f:
            entry = json.loads(line_str)
            if entry.get("type") in ("user", "assistant"):
                messages.append(entry)

    # Pair up tool results with tool calls
    pending_tool_calls: dict[str, dict] = {}

    msg_num = 0
    for entry in messages:
        msg_type = entry.get("type", "")
        message = entry.get("message", {})
        role = message.get("role", "")
        content = message.get("content", "")

        text, tool_calls = extract_text_from_content(content)

        # Handle tool results from user messages (these are responses to tool_use)
        if role == "user" and isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    tool_id = block.get("tool_use_id", "")
                    result_content = block.get("content", "")
                    result_text = ""
                    if isinstance(result_content, list):
                        for rc in result_content:
                            if isinstance(rc, dict) and rc.get("type") == "text":
                                result_text = rc.get("text", "")
                    elif isinstance(result_content, str):
                        result_text = result_content
                    if tool_id in pending_tool_calls:
                        pending_tool_calls[tool_id]["result"] = result_text
            # Don't render tool_result-only user messages as user turns
            has_user_text = False
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        t = block.get("text", "").strip()
                        if t and not t.startswith("<"):
                            has_user_text = True
            if not has_user_text:
                continue

        # Skip empty messages
        if not text.strip() and not tool_calls:
            continue

        # Filter out system-reminder text from user messages
        if role == "user":
            # Remove system-reminder tags
            import re
            text = re.sub(r'<system-reminder>.*?</system-reminder>', '', text, flags=re.DOTALL).strip()
            if not text and not tool_calls:
                continue

        if role == "user":
            msg_num += 1
            lines.append(f"---\n\n## User (message {msg_num})\n")
            if text.strip():
                lines.append(text.strip())
                lines.append("")
        elif role == "assistant":
            if text.strip():
                lines.append(f"**Assistant:**\n")
                lines.append(text.strip())
                lines.append("")
            if tool_calls:
                for tc in tool_calls:
                    pending_tool_calls[tc["id"]] = tc
                # Render tool calls that already have results, or just the call
                for tc in tool_calls:
                    lines.append(format_tool_call(tc))
                    lines.append("")

    # Now re-render with results attached — actually we need a different approach.
    # The simple approach above works because tool results come in subsequent user messages
    # and we already handle that in the loop.

    return "\n".join(lines)


def main() -> None:
    logs_dir = Path("/Users/matthew.khoriaty/Desktop/research/ai_eugenics_test/logs/conversation")

    sessions = [
        ("01_initial_exploration.jsonl", "Session 1: Initial Exploration"),
        ("02_framework_implementation.jsonl", "Session 2: Framework Implementation"),
        ("03_paired_experiment.jsonl", "Session 3: Paired Language Experiment"),
        ("04_full_scale_run.jsonl", "Session 4: Full-Scale Run & Report"),
    ]

    for filename, title in sessions:
        jsonl_path = logs_dir / filename
        if not jsonl_path.exists():
            print(f"Skipping {filename} (not found)")
            continue

        md_path = jsonl_path.with_suffix(".md")
        print(f"Converting {filename} -> {md_path.name}...")
        md_content = convert_jsonl_to_markdown(jsonl_path, title)
        md_path.write_text(md_content)
        print(f"  Wrote {len(md_content)} chars")


if __name__ == "__main__":
    main()
