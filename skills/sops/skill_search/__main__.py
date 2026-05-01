"""CLI entry point: ``python -m photoagents.skills.sops.skill_search``."""
from __future__ import annotations

import argparse
import json
import sys

from .engine import SearchResult, SkillSearchError, detect_environment, search, get_stats


# ── Formatting ───────────────────────────────────────────

def format_results(results: list[SearchResult], env: dict, query: str) -> str:
    lines = [f'Search: "{query}"',
             f"Environment: {env.get('os','?')} / {env.get('shell','?')} / {', '.join(env.get('runtimes',[]))}",
             f"Found {len(results)} matching results\n"]
    if not results:
        lines.append("No matching skill found. Try different keywords.")
        return "\n".join(lines)
    for i, r in enumerate(results, 1):
        s = r.skill
        safe_icon = "[safe]" if s.autonomous_safe else "[risk]"
        score_bar = "#" * int(r.final_score * 10) + "." * (10 - int(r.final_score * 10))
        lines += [
            f"{'-' * 60}",
            f"#{i}  {safe_icon} {s.name}",
            f"    path: {s.key}",
            f"    category: {s.category} | tags: {', '.join(s.tags[:5])}",
            f"    summary: {s.one_line_summary}",
            f"    score: [{score_bar}] {r.final_score:.2f}  (relevance={r.relevance:.2f} quality={r.quality:.1f})",
            f"    clarity={s.clarity} completeness={s.completeness} actionability={s.actionability} | form={s.form}",
        ]
        if r.match_reasons:
            lines.append(f"    matched: {' | '.join(r.match_reasons[:3])}")
        if r.warnings:
            lines.extend(f"    {w}" for w in r.warnings)
        lines.append("")
    lines.append(f"{'-' * 60}")
    return "\n".join(lines)


def format_results_json(results: list[SearchResult]) -> list[dict]:
    out = []
    for r in results:
        s = r.skill
        out.append({
            "rank": len(out) + 1, "key": s.key, "name": s.name,
            "category": s.category, "tags": s.tags,
            "description": s.description, "one_line_summary": s.one_line_summary,
            "scores": {"final": round(r.final_score, 3), "relevance": round(r.relevance, 3),
                       "quality": round(r.quality, 1), "clarity": s.clarity,
                       "completeness": s.completeness, "actionability": s.actionability},
            "safety": {"autonomous_safe": s.autonomous_safe, "blast_radius": s.blast_radius,
                       "requires_credentials": s.requires_credentials,
                       "data_exposure": s.data_exposure, "effect_scope": s.effect_scope},
            "platform": {"os": s.os, "runtimes": s.runtimes, "tools": s.tools, "services": s.services},
            "warnings": r.warnings, "match_reasons": r.match_reasons,
        })
    return out


# ── CLI ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="skill_search",
        description="Skill search system — recommend skills based on environment and need (API client).",
    )
    parser.add_argument("query", nargs="?", help="search keywords (e.g. 'python testing')")
    parser.add_argument("--category", "-cat", help="restrict to a single category")
    parser.add_argument("--top", "-k", type=int, default=10, help="number of results to return (default 10)")
    parser.add_argument("--json", action="store_true", help="emit JSON output")
    parser.add_argument("--env", action="store_true", help="only print the detected environment")
    parser.add_argument("--stats", action="store_true", help="print index statistics")
    parser.add_argument("--api-url", help="override the API URL (also via SKILL_SEARCH_API env var)")
    args = parser.parse_args()

    if args.api_url:
        import os
        os.environ["SKILL_SEARCH_API"] = args.api_url

    env = detect_environment()

    if args.env:
        print("Current environment:")
        print(f"  OS:           {env['os']}")
        print(f"  Shell:        {env['shell']}")
        print(f"  Runtimes:     {', '.join(env['runtimes'])}")
        print(f"  Tools:        {', '.join(env['tools'])}")
        print(f"  Model caps:   tool_calling={env['model']['tool_calling']}, "
              f"reasoning={env['model']['reasoning']}, context={env['model']['context_window']}")
        return

    if args.stats:
        try:
            stats = get_stats(env)
            print("Index statistics:")
            print(f"  Total: {stats.get('total', '?')} skills")
            print(f"  Autonomous-safe: {stats.get('safe_count', '?')}")
            if 'categories' in stats:
                print("  Categories:")
                for cat, cnt in sorted(stats['categories'].items(), key=lambda x: -x[1]):
                    print(f"    {cat:15s} {cnt:4d}")
        except SkillSearchError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    if not args.query:
        parser.print_help()
        return

    try:
        results = search(query=args.query, env=env, category=args.category, top_k=args.top)
    except SkillSearchError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(format_results_json(results), indent=2, ensure_ascii=False))
    else:
        print(format_results(results, env, args.query))


if __name__ == "__main__":
    main()
