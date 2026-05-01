# Autonomous Action SOP

WARNING (paths): `autonomous_reports/` lives under `temp/` and is accessed as `./autonomous_reports/`. It is **not** `../photoagents/skills/autonomous_reports/` or `../autonomous_reports/`. The TODO file lives under cwd.
Reports are stored in `./autonomous_reports/`, named `RXX_short_description.md` (XX is auto-incremented from history.txt).

You are authorized to act autonomously, as long as your actions have no side effects on the environment.

## Startup (step 1)
- update_working_checkpoint: `Autonomous action | re-read this SOP at wrap-up | from autonomous_ops.helper import *; set_todo() / complete_task(tasktitle, historyline, report_path)`

Step 2:
```python
from photoagents.skills.sops.autonomous_ops.helper import *
print(get_history(40))  # know history to avoid repeats
print(get_todo())       # check the to-do list
```

## Task selection
- If there are unfinished entries -> pick **one**, jump straight into execution; the other entries wait for next time.
- No TODO -> read `sops/autonomous_ops/task_planning.md` to plan; execute next time.
- Never pick the same sub-task two runs in a row.
- Value formula: **"data the AI training set cannot cover" x "lasting benefit for future collaboration"**.

## Execution
- Once you pick a task, call update_working_checkpoint and append the chosen TODO entry plus important notes to the checkpoint.
- Call code_run to register the wrap-up callback. Use `script=handler._done_hooks.append("Re-read the autonomous-task SOP and check whether your wrap-up was correct; fix it if not")`, with `inline_eval=True` (secret parameter).
- <=30 turns, small steps, probe and experiment in parallel.
- Use throwaway scripts to test hypotheses. Do not draw conclusions from read-only inspection alone — finish the verification before writing the report.
- Even a failure run is logged: record the experimental procedure and result. Failure reports are also valuable.
- The user is offline. If a decision is required, write it to the report for review later — do not block.

**Wrap-up (all four steps are mandatory):**
0. Re-read this SOP.
1. Write the report in cwd (any filename); if you have memory updates to suggest, append them to the end of the report.
2. `from <module> import helper; complete_task(tasktitle, historyline, report_path)` -> auto-numbers, moves the report into `autonomous_reports/`, prepends to history (historyline format: `type | topic | conclusion`, strict single line).
3. `set_todo()` to get the TODO path -> mark the completed entry as `[x]`.
4. Exit. Remaining TODOs wait until next time.

## Permission boundaries
- No approval needed: read-only probes, write actions and script experiments inside cwd.
- Needs report-and-review: changes to global_mem, edits to SOPs in `photoagents/skills/`, software installation, external API calls, deleting non-temporary files.
- Absolutely forbidden: reading credentials, modifying the core codebase, irreversible/dangerous operations.

## Wait for user review
- After the user returns they review the report and decide to approve, request changes, or reject the proposal.
