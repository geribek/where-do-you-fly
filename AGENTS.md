# Project working agreement

This is a public repository. Read SECURITY.md before changing configuration, fixtures, workflows or publication behavior.

When present, read `.private/project-context.md` for the owner's local delivery-tracker instructions and `.private/jira-backlog.md` for its initial story map. These files are private, ignored and must never be copied into public issues, commits, summaries or artifacts. Keep delivery tracking updated automatically as work progresses. If private context is unavailable, do not guess its URLs or identifiers.

Use only synthetic coordinates, airport identifiers and configuration in tracked code, tests and documentation. Actual deployment settings and credentials belong in the ignored local environment or the runtime secret store. Never log their values. Run `python3 scripts/security_check.py --all` before preparing a public commit; the installed pre-commit hook checks the staged snapshot again. Do not bypass a failing scanner.

A roadmap entry does not authorize implementation beyond the requested phase. Live-provider access and hardware purchases remain explicitly gated.

## Branch and pull-request workflow

Create feature branches for new work and prepare pull requests into `main`. Use coherent commits with meaningful messages. Do not commit implementation directly to `main` or merge a pull request unless explicitly requested. Keep private delivery-tracker identifiers out of public commit messages and PR descriptions.
