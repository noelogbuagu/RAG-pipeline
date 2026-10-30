# Project working agreements

## Build journal

When making meaningful code, dependency, configuration, or architecture changes,
read `BUILD_JOURNAL.md` and update it as part of the same task, before reporting
completion. Before a requested commit, check that the journal covers the staged
work and include its relevant updates in that commit.

Write for the project owner learning to build a RAG pipeline. Record dated,
ordered milestones explaining the goal, what was built, why it works that way,
key files or commands, checks actually performed, and remaining limitations.
Group related edits into one milestone; omit line-by-line corrections and
routine retries. Clearly distinguish working features, placeholders, and plans.
Preserve earlier milestones when the architecture changes and add the new
decision with its reason. Correct factual errors in place. Add commit references
only when known; never create an extra commit just to record its own hash.

For user edits, document meaningful changes once inspected and understood.
For discussion-only turns, update the journal only when a substantive design
decision is agreed. Keep secrets and private document contents out of the journal.
Keep `README.md` focused on the current overview and startup instructions.

## User edits

Preserve imports the user has added for upcoming work, even if currently unused,
unless the user asks to remove them.
