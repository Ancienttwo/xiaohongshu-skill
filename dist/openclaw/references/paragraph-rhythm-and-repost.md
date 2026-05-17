# Xiaohongshu Paragraph Rhythm and Repost Recovery

Use this reference when a published Xiaohongshu note looks correct syntactically but reads as a dense block on the platform.

## Durable lesson

Xiaohongshu does not reward essay-style density. Single line breaks are not enough when adjacent lines form different logical thoughts. For this user, publish-ready body copy must have visible blank-line rhythm.

## Pre-publish rhythm gate

Before any `xhs post`:

1. Generate the exact body with `scripts/publish_note.py --body-output <tmp-file>`.
2. Confirm `markdown_leaks == []`.
3. Inspect the body-output, not only the Markdown draft.
4. Require logical paragraphs to be separated by blank lines.
5. Keep consecutive non-empty lines to 2-3 lines per visual group; allow 4+ only for an intentionally approved compact list.
6. Section openers such as `🌿 1｜...` should usually have blank lines before and after.
7. CTA and hashtag blocks should be separated from the main body by blank lines.

A simple validation target:

```text
markdown_leaks: []
max_consecutive_nonempty <= 3
logical sections separated by blank lines
```

## If the user reports screenshot density after publishing

Treat the report as a publishing-quality issue, not a cosmetic nit.

1. Repair the local draft first.
2. Dry-run again and save a body-output artifact.
3. Verify markdown leaks and paragraph rhythm.
4. Do not delete or repost until the user explicitly authorizes the write action.
5. When authorized, delete the dense version, repost the spaced version, then verify with `xhs my-notes --json`.
6. Update `metrics.csv` so the deleted dense version is excluded from health scoring and the new note_id becomes the tracking target.
7. Append action-log entries for the failed/successful delete attempts, repost, and final verification.

## Example status-note wording

For a deleted dense version:

```text
published_after_format_fix_snapshot; note_id=<old_id>; ...; deleted_for_dense_spacing; exclude_from_health_scoring_after_repost
```

For the final spaced repost:

```text
published_spacing_fix_snapshot; note_id=<new_id>; tab_status=<status>; permission_code=<code>; spacing_validated_max_run=3
```
