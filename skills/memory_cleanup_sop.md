# Memory Cleanup SOP

## Core principle: existence encoding
The LLM itself is the compressor and the decoder. L1 only needs to make it **aware that some kind of knowledge exists**; it can fetch the deeper content via tool calls on its own.

**The essence of L1: express, in the smallest number of words, what memory is available in what scenario (existence).**

L1 has two kinds of content. Both are evaluated by the same ROI rule:
- **Existence pointers**: the shortest trigger words that point at L2/L3 knowledge.
- **Behavior rules**: mistakes you would make without a reminder (fatal or high-frequency, anything past the ROI threshold).

ROI = (probability of error without these words x cost of the error) / per-turn token cost of keeping them.

## Quick decisions
**Keep**: counter-intuitive trigger words — scenario words that wouldn't make you think of an SOP otherwise. Example: `tmwebdriver_sop(httponly cookie)`. Without the words "httponly cookie" you would not realize cookie retrieval lives in tmwebdriver_sop.
**Delete**:
- Name translations: `proxy-pool/(proxy pool)` — the name explains itself, the parenthetical is dead weight; just `proxy-pool` is enough.
- Content descriptions: `opencli_sop(66 sites CLI, reuses Chrome session)` — those are implementation details that belong inside the SOP, not trigger scenarios.
- Intuitive abilities: things you would think of without prompting — zero gain, paying the per-turn cost for nothing.
- Redundancy: rules already covered by L3 / fragments already in another L1 line.

## Four compression principles
1. **Self-explanatory naming beats annotation**: if the SOP name says it all, do not annotate it in L1; renaming has higher ROI than rewriting L1.
2. **Smallest description for an existence set**: when many similar entries can be covered by a parent scenario, name the set instead of listing each child. E.g. `qq ops / Feishu ops / WeWork ops` -> `im ops: *_im_sop`. If sub-names are self-explanatory, list names without translation.
3. **Entry = scenario <-> approach existence**: e.g. `video understanding: yt-dlp grabs subtitles`, `fofa(asset mapping)` — the scenario name is the trigger, the approach name encodes existence. Parentheses **only carry counter-intuitive trigger words**; non-counter-intuitive parentheticals (translations, descriptions, implementation details) are pure waste.
4. **Layer placement**: entries with behavior rules or high-frequency / high-ROI value go into the upper scenario row; pure existence pointers stay in the L2/L3 flat list.

## Cleanup procedure
1. Read L1 line by line. Split each line by `|` and classify each fragment: existence pointer / RULE / translation / content description / implementation detail / redundant.
2. Clean RULES first. For each, ask "is this globally high-ROI, or scenario-specific and low-risk?"
   - Globally high-ROI -> keep.
   - Scenario-specific / low-risk -> demote to L3 or delete.
3. Clean existence pointers. Check that each expresses **scenario <-> approach existence**; only add a scenario trigger when it is **counter-intuitive**. Remove translations, content descriptions, implementation details.
4. Check that L3 filenames are self-explanatory. Solve via renaming first, not by adding L1 description. Finally verify total line count <= 30.

**Red line**: memory edits do persistent damage; an error compounds every turn. L1 only allows word-level patches — never overwrite.
If something causes confusion, fix L1 promptly or rename the memory.
