## 0. Core axioms (highest priority)
1.  **Action-Verified Only**
    *   **Definition**: anything written into L1/L2/L3 must come from a **successful tool call result** (e.g. a successful `shell`, a `file_read` confirming the contents exist, code that ran).
    *   **Forbidden**: never write the model's "intrinsic knowledge", "guesses", "unexecuted plans" or "unverified hypotheses" as if they were facts.
    *   **Slogan**: **No execution, no memory.**
2.  **Sanctity of verified data**
    *   **Definition**: any verified configuration, pitfall guide or critical path must **not be lost** during refactoring/GC.
    *   **Practice**: you may compress wording or move things between layers (L2 -> L3), but you must never lose accuracy or traceability.
    *   Be extremely careful when editing memory; avoid overwrite or code_run. Apply minimal patches; if you cannot, don't change it at all.
3.  **No volatile state**
    *   **Definition**: never store data that changes frequently with time/session.
    *   **Examples**: current timestamp, transient session ID, running PID, a one-off absolute path, the device currently connected.
4.  **Minimum sufficient pointer**
    *   The upper layer keeps only the shortest identifier needed to locate the lower layer; anything more is redundant.
---
## Memory layer architecture
```
L1: global_mem_insight.txt (extreme-summary index, hard-capped <= 30 lines)
    -> navigation pointer
L2: global_mem.txt (fact base; concise but tends to grow)
    -> detailed reference
L3: photoagents/skills/ (records library: .md/.py and other files)
L4: ~/.photoagents/sessions/ (historical session layer, auto-collected by the scheduler reflection task; lets you find past context)
```
---
## Per-layer responsibilities and principles
### L1: global memory index (global_mem_insight.txt)
**Role**: provide an extremely small navigation index for L2 and L3 so key abilities remain discoverable.
**Characteristics**:
- Size limit: <= 30 lines (hard), < 1k tokens (soft). Do not write details (only allowed for very high frequency tasks).
- Content: two-tier "scenario keyword -> memory location" map plus RULES (red-line rules + high-frequency mistake points).
  - First tier: high-frequency scenario key -> value (give the sop/py/L2 section name directly); self-contained names get a single word, no repeated translation.
  - Second tier: low-frequency scenarios get only their keywords; the agent reads L2 or `ls`'s L3 when needed.
  - Crucial: the scenario trigger word is essential (without it the ability is unknown), but never write How-to detail.
  - RULES: compressed pitfall rules, including:
    - Red-line rules (fatal): violating them kills the process or crashes the system (e.g. "never unconditionally kill python — kills self").
    - Red-line rules (silent): violating them does not raise errors but produces wrong results (e.g. "search via google not baidu").
    - High-frequency mistakes: easily-forgotten constraints (e.g. "es(PATH set)" so you don't search for the path).
- Updates: when L2/L3 add/remove entries, classify by frequency into the right layer. Be extremely careful; no overwrite, no code_run. Apply minimal patches; if you cannot, don't change it.
**Forbidden**: never store passwords or API keys. Inline non-sensitive trigger params (like a proxy port) is OK. No "How to" or detailed explanation. Never include task-specific technical detail (those live in L3). Never write logs!
---
### L2: global fact base (global_mem.txt)
**Role**: store global environmental facts (paths, credentials, configs, constants).
**Characteristics**:
- Trend: grows as the environment grows (acceptable).
- Content: fact entries organized under `## [SECTION]` headings.
- Sync: when an entry changes, only update the corresponding L1 TOPIC navigation row, and only its name.
**Forbidden**: no volatile state, no guesses, no general knowledge an LLM can recall by itself.
---
### L3: task-level concise records (photoagents/skills/)
Role: hold the small amount of detail that L1/L2 cannot absorb but is essential for **future reuse on a specific task**. Content must be **as short as possible** while still serving its reuse purpose.
Principles:
- Only record: things that matter across sessions and are hard to rebuild quickly via a few `file_read`/`web_scan`/short scripts.
- Prioritize: hidden prerequisites unique to the task, common pitfalls — anything where forgetting causes expensive retries.
- Do not record: ordinary procedures, paths/state recoverable in a few probes.
Forms:
- SOP (`*_sop.md`): for a single task or small task family, keep a minimal "key prerequisites + common pitfalls" list, not a long tutorial.
- Tool scripts (`*.py`): only when reuse is high and the logic is non-trivial enough that you do not want to rederive it each time.
---
## L1 <-> L2/L3 sync rules
| Operation | L1 sync |
|-----------|---------|
| L2/L3 adds a scenario | New entries default to low-frequency; add the filename to the L3 list (no description if self-explanatory; only counter-intuitive scenarios may add a parenthetical trigger word). |
| L2/L3 removes a scenario | Remove the matching keyword/mapping line. |
| L2/L3 modifies a value | If scenario lookup is unaffected, do not touch L1. |
| Generic pitfall discovered | Compress to one line and add to RULES. |

> **Sync red line**: L1 only contains keywords/names; never copy detail in. Inside parentheses only put a 2-4 character scenario trigger word — no mechanism, method, or step. Track L1 token count and index utility.
> Counter example: bad `sop_name(scenario A: method 1 + method 2 + method 3)` -> good `sop_name(scenario A)`.

---
## Information classification quick decision tree
```
"Where does this information go?"

Is it an "environment-specific fact"? (IP, non-standard path, credential, ID, API key — anything an LLM zero-shot cannot generate accurately)
  -> YES -> L2 (global_mem.txt)
            then -> by frequency, into L1 first tier (key->value) or second tier (keywords only)
  -> NO
       -> Is it a "general operating principle"? (global pitfall guide, troubleshooting method, principle that does not target a specific task)
       -> YES -> L1 [RULES] (one compressed sentence at most)
       -> NO
            -> Is it "task-specific technique"? (Hard-won success that may be reused later, e.g. WeChat parsing parameters, specific game coordinates, transient tool config)
            -> YES -> L3 (photoagents/skills/ — dedicated SOP or script)
            -> NO -> classify as "general knowledge" or "redundant info": never store, drop it.
```
