# Plan Mode SOP

**Trigger**: 3+ steps with dependencies / multi-file coordination / conditional branches / parallel work.
**Disabled when**: 1-2 step simple tasks — just do them.
Before starting, you must create the working directory `./plan_XXX/` (XXX = short English name for the task).
Then issue a single code_run({'inline_eval':True, 'script':'handler.enter_plan_mode("./plan_XXX/plan.md")'}) to enter plan mode.

---

## I. Exploration phase (mandatory before planning)

**Hard rules (read first, act later)**:

- **The main agent must not run environment probes itself** (always delegate to a subagent, no exceptions).
- The main agent only: creates the directory, matches SOPs, launches the subagent, reads the conclusions.
- The subagent only does read-only probing; it must not modify files or perform side-effecting actions.
- **If the exploration subagent fails to start: diagnose -> retry, max 2 attempts. The main agent must NOT fall back to probing on its own.**

**Goal**: before writing any plan, figure out three things:
1. environment state (what's there, what's missing); 2. available SOPs; 3. critical uncertainties.

**Why subagent is mandatory**: the main agent's context is the scarcest resource, and long probe outputs would crowd out planning/execution space.

### Step 1: create the directory (mandatory) + match SOPs + set the plan flag (main agent does this directly)

1. Create the working dir: `mkdir plan_XXX/`.
2. Match available domain SOPs from the L1 Insight index in your context.
3. Update checkpoint: `[task] XXX | [need] one sentence | [constraints] key limits | [matched SOPs] ... | [phase] exploration`.

### Step 2: launch the exploration subagent (supervisor mode)

Following subagent.md, start the exploration subagent with `--verbose` to enable supervisor mode. Input highlights:

- **Task**: probe the environment, write findings into `plan_XXX/exploration_findings.md`.
- **Probe targets** (pick by task type, not all):
  - Code task -> key file structure, dependencies, entry points.
  - Browser task -> current state of the target page, interactive elements.
  - Automation task -> environment check (which / pip / paths / permissions).
  - Data task -> sample (first 5 rows + last 5 rows + total).
- **Output structure**: `## Environment` / `## Key findings` / `## Risks/Uncertainties`.
- **Constraints**: read-only, no file modification, <= 10 tool calls.
- **Complexity assessment**: while probing, record data scale (file count, line count, page count) into findings — used later to decide on delegation.

### Step 3: supervised wait + read the conclusions

The main agent observes output.txt progress (`--verbose` includes raw tool outputs) instead of blindly sleeping:

1. **Observe**: read output.txt; review the subagent's probe direction and raw data.
2. **Correct as needed**:
   - Wrong direction -> write `_intervene` with corrective instruction.
   - Missing key context -> write `_keyinfo` to inject information.
   - Enough info -> write `_stop` to terminate early and save turns.
3. **Collect**: wait for `[ROUND END]`, then read `exploration_findings.md`.

**Output**: `exploration_findings.md` (structured findings). The main agent uses it to enter the planning phase and writes the "Exploration findings" section at the top of plan.md. First-hand insight gained while supervising can also feed into planning.

---

## II. Planning phase (with review gate)

### Step 4: read domain SOPs -> write plan.md

Read the domain SOPs matched during exploration, then sketch the plan skeleton. "WAIT-CONFIRM" placeholders are allowed; "I have not investigated this" is not.

**[D] delegation rule**: when writing a step, combine exploration findings with operation volume; mark `[D]` if any of the following hold:

- Reads many files / large code (>3 files or >100 lines).
- Browses pages and extracts info.
- Performs more than 3 repetitive operations.
- Runs tests/builds and analyzes their output.

Do NOT mark `[D]` for: read/update plan.md, single-file small edits, ask_user, simple one-off commands.

**plan.md format**:

```markdown
<!-- EXECUTION PROTOCOL (read every turn — this is your execution guide)
1. file_read(plan.md), find the first [ ] item.
2. If that step is annotated with an SOP -> file_read the SOP's quick-ref section.
3. Execute the step + a mini verification of the output.
4. file_patch [ ] -> [done] + short result, then loop back to step 1 to take the next [ ].
5. After all steps (including verify steps) are marked complete -> termination check: file_read(plan.md) and confirm 0 remaining [ ].
WARNING: never execute from memory | never skip verify steps | never finish without the termination check | never stop to write a pure-text report.
TIP: heavy lifting (lots of code/files/web/repetitive ops) should be delegated to subagents to keep the main agent's context clean.
-->
# Task title
Need: one sentence | Constraints: key limits

## Exploration findings
- Finding 1: XXX (source: file_read/web_scan/code_run)
- Finding 2: YYY
- Uncertainty: ZZZ

## Execution plan
1. [ ] step 1 brief
   SOP: xxx_sop.md
2. [D] step 2 brief (delegated to subagent)
   SOP: yyy_sop.md
   Depends on: 1
3. [P] step 3 brief (parallel; read subagent.md and run Map mode)
   SOP: yyy_sop.md
4. [?] step 4 (conditional)
   SOP: (none) <- high risk
   Condition: if X succeeds -> 4.1, otherwise -> 4.2

---

## Verification checkpoint
N+1. [ ] **[VERIFY] start an independent verification subagent**
     SOP: verify_sop.md plan_sop.md
     Action: read section 4 of plan_sop.md -> prepare verify_context.json -> launch the verification subagent -> read VERDICT -> handle result accordingly
     WARNING: cannot be skipped; cannot be marked [done] without launching the subagent.

---
```

### Step 5: self-check list (main agent goes through each)

- Did exploration findings make it into the plan? (no key constraint missed)
- Are SOP annotations on each step reasonable? (does that SOP really cover that step?)
- Are inter-step dependencies right? (no implicit dependency missing)
- For high-risk steps (SOP: none / irreversible), is the execution idea clear?
- Is step granularity appropriate? (no "process all files"; expand to specific items)
- **Are complex / tedious steps marked `[D]`?** (lots of code / web / repetition must be delegated)
- **Does the plan have a "Verification checkpoint" section with a `[VERIFY]` step?** (mandatory)

### Step 6: user confirmation

Run ask_user to confirm the plan before moving to execution. **The user must confirm before execution.**

### Step 7: enter execution phase

Update checkpoint: `[exec] plan.md | current: step 1 | NOTE: any [P] markers require subagent.md / Map mode`.

---

## III. Execution loop

> **Core principle: keep going, do not pause to summarize.** Finish a step, immediately file_read(plan.md), find the next `[ ]`, until all are done.

### Per-turn flow

1. **Read plan** — `file_read(plan.md)`, find the first `[ ]`.
2. **Read SOP** — if the step is annotated, file_read that SOP first.
3. **Check markers** — `[D]` -> must delegate to subagent, main agent only consumes the summary; `[P]` -> read subagent_sop.md, run Map mode; `[?]` -> evaluate and pick a branch, mark unused branch [SKIP].
4. **Execute** — steps with no special marker are run by the main agent.
5. **Mini verify** — quickly confirm the output exists and is sane (file_read for non-empty, check exit codes, etc.).
6. **Mark done** — `file_patch` `[ ]` -> `[done short result]` (progress lives in plan.md).
7. **Continue** — immediately go back to step 1, file_read(plan.md), and process the next `[ ]`.

### Termination check (after marking the last step; do not skip)

file_read(plan.md), full-text scan, confirm every step (including [VERIFY]) is `[done]` / `[fail]`, with 0 `[ ]` left.
Output: `Termination check: [N] steps complete, 0 [ ] remaining -> task done`.
If you find anything missed, keep executing — do not claim completion.

### Execution-phase prohibitions

- **Never execute from memory**: before each new step you must `file_read(plan.md)`. No "I remember the next step is...".
- **Never skip verify steps**: [VERIFY] is mandatory; "the task is done" is not a reason to skip it.
- **Never finish without the termination check**: after marking the last step, file_read the entire plan, confirm 0 `[ ]`, output the termination line.
- **Never stop to write a text-only progress report**: after a step, immediately file_read(plan.md) and continue.

### Dynamic delegation principle

Even if a step is not marked `[D]`, if you discover during execution that it requires:

- Reading many files / large code to understand context (>3 files or >100 lines).
- Repeated trial-and-error debugging.
- Browsing the web to extract info.

Then proactively delegate: spin up a subagent for the concrete operation, ask it to return a concise summary, the main agent decides based on the summary. Keeping the main agent's context clean is the top priority.

---

## IV. Verification phase (independent subagent verification)

> Enter once all steps are `[done]`. Independent adversarial verification by a subagent is **mandatory** to avoid context contamination.

### Trigger conditions

- All execution steps are `[done]`.
- **Every plan-mode task must be verified by a subagent** (the main agent has confirmation bias and is easily fooled by surface success).

### Step 8: prepare verification context

Inside `./plan_XXX/`, create `verify_context.json` containing:

- task_description: the original user request (verbatim).
- plan_file: absolute path of plan.md.
- task_type: code | data | browser | file | system.
- deliverables: list of deliverables (type / path / expected).
- required_checks: list of mandatory checks (check / tool).

**What to send**: task description, plan path, deliverables list, required checks.
**What not to send**: execution log, debugging notes.

### Step 9: launch the verification subagent

Following subagent.md, start the verification subagent. Input highlights:

- **Role**: you are an independent verifier; your job is adversarial verification (prove the deliverables don't work).
- **Forced first step**: file_read verify_sop.md in full.
- **Per verify_sop.md section 3**, choose the verification strategy that matches task_type and execute it.
- **Each check must include tool-call evidence** (real execution, not narration).
- **Task description**: (fill in the original request)
- **Deliverables list**: (fill in deliverables)
- **Output**: in result.md, follow verify_sop.md section 6, with the last line `VERDICT: PASS / FAIL / PARTIAL`.
- **Constraints**: complete within 3 turns, at least 1 real tool call per turn.

Pass the path to verify_context.json so the subagent can read full context itself.

### Step 10: collect verification result

Poll output.txt for `[ROUND END]`, then read result.md:

1. **Find the VERDICT line**: read the last lines of result.md, extract `VERDICT: PASS/FAIL/PARTIAL`.
2. **Validity check**: if every PASS item lacks a tool call (just narration), treat the verification as invalid -> FAIL.
3. **Handle**:
   - **PASS** -> proceed to wrap-up.
   - **FAIL** -> enter the fix loop.
   - **PARTIAL** -> main agent decides; if acceptable, complete; otherwise fix.
   - **No VERDICT line** -> extract key info from output.txt; main agent decides PASS/FAIL itself.

**Wrap-up (after PASS)**:

1. Mark the `[VERIFY]` step in plan.md as `[done]`.
2. Update checkpoint: `[done] XXX task | [outputs] ... | [lessons] ...`.
3. Confirm completion to the user.

**Important**: only after PASS may you mark [VERIFY] as `[done]` and claim the task is complete. On FAIL, enter the fix loop.

**Fallback**: if the subagent did not produce result.md (turn budget exhausted), extract the VERDICT from output.txt.

### Fix loop (after FAIL)

FAIL -> extract failed items -> back to execution to fix (do not re-plan) -> done -> launch verification subagent again -> at most 2 FAIL-retry rounds, then ask_user to step in.

When fixing:

1. Append failed items to plan.md as new steps (mark them `[FIX]`).
2. Only fix what failed; do not redo PASS items.
3. After fixing, rebuild verify_context.json (only the failed items).

### Special scenarios

Browser / mouse / scheduled tasks: the main agent runs the operation and exports evidence (screenshot / recording / log) -> the subagent verifies the evidence file. **The main agent must not decide PASS/FAIL by itself.**

---

## V. Failure handling

1. **Record**: in the checkpoint, `step_X: [FAILED] reason (retry: N/3)`.
2. **Retry**: network timeout -> auto retry 3 times (2s/4s/8s); config error -> ask user; otherwise mark `[fail]` and skip.
3. **Subagent failure**: read stderr.log -> if known error, main agent fixes and restarts | unknown error retry once | max 2 restarts.
4. **Dependency propagation**: when a step fails, mark dependent items `[SKIP]`.
5. **Plan is wrong**: roll back to planning, fix plan.md, go through the review gate again.

## Hard constraints

- Each step must have its own done-criteria.
- No "process all files" — expand to specific items.
- Only one item at a time; if the plan is wrong, return to planning to fix it.
- Add an extra verification step before any irreversible operation.
