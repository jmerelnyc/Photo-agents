# Skill Search — 105K skill cards

> Semantic search over 105K+ skill cards for the best-matching skill. Zero dependencies, ships with a default API URL, works out of the box.

## Minimal use

```python
from photoagents.skills.sops.skill_search import search

results = search("python send email")  # WARNING: queries must be in English; Chinese matches very poorly.
for r in results:
    s = r.skill
    print(f"[{r.final_score:.2f}] {s.name} - {s.one_line_summary}")
    print(f"  key: {s.key}  category: {s.category}  tags: {s.tags[:3]}")
```

## API signature

```python
search(query, env=None, category=None, top_k=10) -> list[SearchResult]
#  env: auto-detected; do not pass usually
#  category: optional filter, e.g. "devops"
#  top_k: number of results, default 10
```

## Return shape

```
SearchResult
  .final_score    float     overall score (0..1)
  .relevance      float     semantic relevance
  .quality        float     quality score
  .match_reasons  list[str] reasons for the match
  .warnings       list[str] warnings
  .skill          SkillIndex (below)

SkillIndex (commonly used fields)
  .key              str       unique identifier / path
  .name             str       name
  .one_line_summary str       one-line summary
  .description      str       detailed description
  .category         str       category
  .tags             list[str] tags
  .form             str       form (sop/script/...)
  .autonomous_safe  bool      whether it is safe to run autonomously
```

## CLI

```bash
python -m photoagents.skills.sops.skill_search "python testing"
python -m photoagents.skills.sops.skill_search "docker deployment" --category devops --top 5
python -m photoagents.skills.sops.skill_search "git" --json
python -m photoagents.skills.sops.skill_search --stats
python -m photoagents.skills.sops.skill_search --env
```

## Configuration

| Item | Default | Notes |
|------|---------|-------|
| API URL | `http://www.fudankw.cn:58787` | Override with env var `SKILL_SEARCH_API` |
| API key | None (optional) | Env var `SKILL_SEARCH_KEY` |
