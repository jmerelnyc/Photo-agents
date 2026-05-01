# Subagent Invocation SOP

## File IO protocol

- Directory: `temp/{task_name}/` (when cwd is temp/, this is `./{task_name}/`).
- Launch: `python -m photoagents --task {name} [--input "short text"] [--bg] [--llm_no N]` (cwd = code root).
- `--input` automatically creates the directory, clears old output, and writes input.txt; for long input, write input.txt by hand first and then launch without `--input`.
- Prefer `--bg` (background; prints PID and exits). You can `sleep` and `poll` later in the same code_run. When not using `--bg`, do not combine launch + polling in one call.
- The subagent's cwd is still temp/, not the task directory.
- Input: just goal + constraints; the subagent is just as capable as you. **Do not write step-by-step instructions or over-describe**; if there is bulk data, pass paths.
- Communication: output.txt (append; `[ROUND END]` = a turn has finished) -> write reply.txt to continue -> if you don't reply within 10 min, the subagent exits. After reply, output goes to output1.txt / output2.txt / etc. (same format).
- Intervention files: `_stop` (exit at end of current turn) | `_keyinfo` (inject working memory) | `_intervene` (append instruction).
- **When idle, the main agent should read output to monitor progress and use intervention files to correct course; do not blindly long-sleep poll.**
- For supervisor mode, launch with `--verbose`. Output then includes raw tool results, so the main agent can audit raw data instead of just trusting the summary.

## Scenario 1: test mode — behavior verification
**Use**: observe the agent's real behavior, then update RULES/L2/L3/SOP.
**Flow**: create test_path/, write input.txt -> launch subagent -> poll output.txt every 2s -> verify -> clean up duplicates.
**Test principles**: only give the goal, do not hint at the location, do not steer the approach, observe the autonomous choice.
**Correction loop**: spot a problem -> design a test -> isolate the root cause (RULES/L2/L3/SOP) -> patch -> verify.
**Technical notes**: Insight has higher priority than SOPs; subagent cwd = temp/.
**Two test types**:
- Test SOP quality: input names the SOP (e.g. "use ezgmail_sop to read the last 3 unread emails"), eliminates navigation noise; failure = SOP problem.
- Test navigation: input only states the goal; verify the subagent autonomously finds the right SOP from the insight. Never inline SOP content.

## Scenario 2: Map mode — parallel processing
**Use**: distribute N independent same-shape sub-tasks to their own subagents.
**Core advantage**: independent contexts. The long context of processing document A does not pollute the quality of processing document B.
**Constraints**:
- Shared file system is a feature: different agents work on different input files and produce different output files.
- Shared resources can collide: keyboard/mouse cannot be shared; the browser is not currently parallel-safe — avoid two agents touching the same tab.
- A task that does not fit Map mode -> the main agent runs it sequentially; do not use a subagent.
**Standard flow (map-reduce)**:
1. Main agent prep: scrape/dump data into multiple independent input files.
2. Distribute: launch one subagent per file (the main agent may handle one as well).
3. Collect: when all subagents are done, the main agent reads each output file and aggregates.

## Internal plan_mode use inside a subagent
**Principle**: a subagent is itself a full agent; if it receives a multi-step task, it should manage execution with an internal plan.
**Trigger conditions**: 3+ sub-steps, dependencies between sub-steps, need a checkpoint to resume.
**Implementation**:
1. **When the main agent creates the subagent**: tell it in input.txt that the task has multiple steps and recommend plan_mode.
2. **Inside the subagent**: detect multi-step tasks, create `./subagent_plan.md` and run plan_mode.
3. **Main agent monitoring**: only watch the final result (output*.txt); do not care how the subagent runs internally.
4. **File handoff**: when creating the subagent, the main agent writes `context.json` in task_dir with **absolute paths** to all relevant files.
   **First action of the subagent must be to read context.json.**
   **All file ops must use the absolute paths from context.json.**
**Format example**:
```json
{
  "task": "task description",
  "work_dir": "/absolute/path/to/plan_dir/",
  "input_files": {
    "paper_info": "/absolute/path/to/paper_info.txt"
  },
  "output_files": {
    "pdf": "/absolute/path/to/paper.pdf",
    "report": "/absolute/path/to/paper_report.md"
  },
  "dependencies": ["paper_info.txt must exist"]
}
```
