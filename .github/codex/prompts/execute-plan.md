Read `plans/active.md` first and implement that plan.

Only proceed when the plan frontmatter contains `status: ready`. If the plan is still `status: draft`, stop without editing files and explain that the plan is not ready.

Treat `plans/active.md` as the source of truth for this run. Follow `AGENTS.md` if present.

Before editing, inspect the repository structure and relevant files. Keep changes scoped to the plan. Prefer the repository's existing patterns over new abstractions. Add or update tests when behavior changes.

Run the relevant verification commands named in the plan or implied by the repository. If verification cannot run, explain the blocker and the closest check completed.

Do not commit secrets, tokens, credentials, `.env` files, generated private data, or machine-local files. Do not perform destructive operations. If the plan is ambiguous, unsafe, or requires credentials that are not present, stop and explain what needs clarification.

At the end, summarize changed files, behavior changes, and verification results.

