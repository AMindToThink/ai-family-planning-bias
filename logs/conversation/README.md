# Claude Code Conversation Logs

These are the raw conversation transcripts from the Claude Code sessions used to build and run this research project. Each session is available as both a raw JSONL file (machine-readable) and a rendered Markdown file (human-readable).

| Session | Description |
|---------|-------------|
| [01_initial_exploration.md](01_initial_exploration.md) | Initial project scoping and plan design |
| [02_framework_implementation.md](02_framework_implementation.md) | Building the evaluation framework: prompt templates, dataset generator, scorer, eval task, analysis pipeline, and tests |
| [03_paired_experiment.md](03_paired_experiment.md) | Designing and running the paired language-isolation experiment (Experiment 2) |
| [04_full_scale_run.md](04_full_scale_run.md) | Running Experiment 1 at full scale and consolidating the research report |

## Regenerating Markdown from JSONL

```bash
uv run python scripts/jsonl_to_markdown.py
```

## Notes

- The `.jsonl` files are the raw Claude Code conversation format (one JSON object per line).
- The `.md` files are auto-generated summaries that show user messages, assistant responses, and tool calls (with abbreviated results).
- Thinking blocks are omitted from the Markdown rendering.
- Session 4 is the current session; its JSONL was snapshotted mid-conversation and may not include the final messages.
