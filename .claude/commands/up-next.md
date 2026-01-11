# Up Next - Find Ready Work

Find the next available issue to work on and present it for approval.

## Workflow

1. **List ready issues** - Run `bd ready` to see available work
2. **Pick the top issue** - Select the first ready issue from the list
3. **Get issue details** - Run `bd show <id>` to get full context
4. **Present the issue** - Explain to the user:
   - Issue ID and title
   - What the issue is about (summarize the description)
   - Why this work matters (context/goals)
   - Key files or areas that will likely be affected
   - Any dependencies or blockers
5. **Ask for confirmation** - Use AskUserQuestion to ask if the user wants to work on this issue, with options:
   - "Yes, let's plan to work on this" - Proceed to claim the issue with `bd update <id> --status in_progress`
   - "Show me another" - Pick the next issue from the ready list and repeat from step 3
   - "No, not now" - End the workflow

## Notes

- If no ready issues exist, inform the user and suggest they can create one with `bd new "<title>"`
- When claiming an issue, confirm it's been marked as in_progress
- After claiming, offer to start planning the implementation
