---
status: draft
title: Replace with the task title
---

# Objective

Describe the concrete outcome Codex should deliver.

# Scope

List the files, modules, commands, or product areas Codex may touch.

# Non-goals

List anything Codex should explicitly avoid in this run.

# Constraints

- Keep changes focused and reviewable.
- Follow repository conventions and `AGENTS.md`.
- Do not add production dependencies unless the plan explicitly asks for them.
- Do not commit secrets, credentials, `.env` files, or machine-local files.

# Implementation Steps

1. Inspect the relevant code and tests.
2. Implement the smallest complete change that satisfies the objective.
3. Add or update tests when behavior changes.
4. Run the relevant verification commands.

# Verification

- Replace this with the exact commands Codex should run, such as `pytest`, `npm test`, or project-specific checks.
- If a command cannot run in CI, Codex should explain why and provide the closest available verification.

# Done Criteria

- The objective is implemented.
- Relevant tests or checks are run.
- The pull request summary explains changed files, behavior changes, and verification results.

