# Task Planning Mode

- **Has TODO**: if `TODO.txt` in cwd has unfinished entries -> jump straight to "Execution flow".

Value formula: **"data the AI training set cannot cover" x "lasting benefit for future collaboration"**. The core deliverable is memory — package valuable findings as memory-update proposals inside the report.

Flow entry:
- **No TODO -> enter task planning mode** (this turn does not execute; focus on planning):
  0. update_working_checkpoint: `Planning mode: produce TODO and exit immediately; do not execute any TODO; the next autonomous run enters execution mode.`
  1. WARNING **read history.txt critically**: 90% of historical tasks are low value; read in order to **identify failure modes and avoid them**, not in order to imitate.
     - Low-value patterns: shallow checks, hypothesis-free walkthroughs, repeated exploration, broad-spectrum collection, basic usage of well-known tools.
     - High-value clues: unfollowed findings, tools to actually test, outputs that can be improved.
  2. Reflect: why were those tasks low value? How would you redesign them for high value?
  3. Critically inventory existing reports and memory (`ls autonomous_reports/` + `photoagents/skills/`); think about how to amplify their value or improve them.
  4. Combine the above and produce 5-7 TODO lines into `TODO.txt`. Completed TODOs may be compressed and pushed down.
  5. Each line: `[ ] type(deliverable / surf / environment) | one-sentence goal | acceptance criterion`.
  6. Summon a subagent to review the TODO: input is just the TODO list + "read the memory library and judge for yourself; rate each item 1-10 and explain briefly" (do not feed extra priors).
  7. Read the subagent's scores; delete or replace low scores.
  8. **Exit immediately**; the next autonomous run executes.

Goal ranking (descending value):
1. **Useful deliverables and capability extension**: write a tool that solves a pain point; unlock new capabilities on top of existing ones (every new capability node enlarges the possibility space).
2. **Environmental discovery**: find tools / libraries / data sources / configurations already on the machine that have not been used.
3. **Niche tool discovery**: find rare, useful tools on GitHub / V2EX / 52pojie / etc., and stress-test the ones the AI commonly recommends but that have catches.
4. **Understanding the user, recommendations**: analyze legacy code / PC files / bookmarks to infer preferences and produce personalized recommendations (games / videos / tools, with reasons). (Low frequency.)
5. **Self-improvement**: think about gaps in the framework, propose improvements.
6. **Memory audit**: fix incorrect or stale records.

**Large tasks**: it is fine to design **valuable** large tasks; break them into modules or steps and write them into the TODO; each autonomous run handles one module.

Selection principles: personalization first (knowledge that can only be obtained by probing this PC) -> blind spots first (the model can't reproduce on its own; some difficulty is OK) -> hypothesis-driven (be explicit about what you want to verify; probe and experiment together) -> avoid low-value verification (don't verify static config, no aimless walkthrough, no work that you would breeze through).

Probe strategy (focused; not a menu):
- **Lead-driven**: follow-up tasks distilled from recent reports beat picking topics out of thin air.
- **Capability tree expansion**: prefer tools/skills that unlock new capability nodes (one node opens many possibilities).
- **Personalization first**: knowledge obtainable only by probing this PC / this user > generic knowledge.
- Surfing rules: <= 2 topics per run, must read the body and distill insight; no headline-only collection; if you find a good tool, queue a "test it" task for the next round.

No-go zones: Hacker News - news headline browsing - aimless headline / news collection - basic usage of well-known tools - researching agents weaker than the current framework - researching other web automation / computer use frameworks - reading our own codebase.
