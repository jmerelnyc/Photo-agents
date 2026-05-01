# Memory Scanner SOP

## 1. Quick start
A memory pattern search tool. Supports Hex (Cheat Engine style) and string matching. The LLM mode is provided to make it easy for the model to analyze memory context.

**Python use:**
```python
from photoagents.skills.procmem_scanner import scan_memory

# Example: search for a specific hex pattern, with llm_mode for context.
results = scan_memory(pid, "48 8b ?? ?? 00", mode="hex", llm_mode=True)
```

**CLI:**
```powershell
# basic search
python -m photoagents.skills.procmem_scanner <PID> "pattern" --mode string

# LLM-enhanced mode (JSON with surrounding context, recommended)
python -m photoagents.skills.procmem_scanner <PID> "pattern" --llm
```

## 2. Typical scenario: locate a struct or key piece of data
1. Identify a leading feature or known constant for the target data (e.g. a header or magic number).
2. Search the target process for it: `scan_memory(pid, "4D 5A 90 00", mode="hex", llm_mode=True)`.
3. Inspect the `context` field in the returned JSON to view the raw bytes and ASCII preview around the address.

## 3. Notes
- **Permissions**: not strictly admin, but you need `PROCESS_QUERY_INFORMATION` and `PROCESS_VM_READ` on the target process.
- **Efficiency**: when scanning large amounts of memory, prefer the most unique pattern possible to reduce false positives.

## 4. Cheat-Engine-style differential scanning to locate dynamic fields
Locate dynamic memory fields in self-rendered UIs (e.g. WeChat: the current chat title that changes with operations). Core idea: one full scan + multiple ReadProcessMemory passes to filter.
