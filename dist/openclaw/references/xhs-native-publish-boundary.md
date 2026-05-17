# XHS Native Publish Boundary

Session lesson: Xiaohongshu note drafts should remain Markdown for human review and archival structure, but the publishing boundary must convert the approved draft into Xiaohongshu-native plain text before `xhs post`.

## Problem Pattern

If a Markdown draft body is passed directly to `xhs post --body`, Xiaohongshu displays Markdown markers literally, e.g.:

- `**十神 = 我和外界的十种关系。**`
- `🌿 **1｜比劫：和我同类的人**`
- `## Heading`

This is a publishing-process bug, not a draft-format bug. Do not “fix” it by rewriting source drafts into plain text.

## Durable Rule

- Draft artifacts may and should stay in Markdown.
- The publish script is responsible for extracting title/body/hashtags, converting Markdown formatting to native plain text, and rejecting Markdown leakage.
- Never manually assemble `xhs post --body` from a Markdown section.
- Always dry-run the exact draft first and require `markdown_leaks: []` before posting.

## Conversion Expectations

The publishing boundary should convert:

- `**bold**` → `bold`
- `## Heading` → `Heading` or omit structural-only headings
- `- [ ] checklist` → plain line, or exclude if it is an operator checklist
- `[text](url)` → `text`
- Markdown tables → readable native lines or excluded from note body
- fenced code blocks → excluded unless intentionally part of the public copy

Use Xiaohongshu-native rhythm instead:

- short spoken lines
- blank lines between idea groups
- emoji section markers
- Chinese punctuation
- simple dividers such as `——`

## Required Publish Flow

1. Keep the approved draft as Markdown.
2. Run `scripts/publish_note.py` without `--post` to prepare and validate the native body.
3. Inspect or save `--body-output` when needed.
4. Confirm the dry-run reports `"markdown_leaks": []`.
5. Only after explicit user authorization, run the same command with `--post`.
6. Verify through `xhs my-notes --json`, log the JSON response, and append initial metrics.

## Regression Test

Use `tests/test_publish_note.py` to prevent regressions. It should cover extraction from `## Final Title`, `## Final Body`, and `## Hashtags`, plus detection of leaked Markdown markers.