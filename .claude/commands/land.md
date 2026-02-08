# Landing the Plane - Session Completion

When ending a work session, complete ALL steps below. Work is NOT complete until `git push` succeeds.

## Mandatory Workflow

1. **File issues for remaining work** - Create bd issues for anything that needs follow-up. If creating sub-issues, link them as dependents of the parent issue: `bd dep <parent-id> --blocks <new-issue-id>`
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Push to remote** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

## Critical Rules

- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
