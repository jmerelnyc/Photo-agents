"""skill_search — API client for the Photo Agents skill search service."""
from .engine import (
    SkillIndex, SearchResult, SkillSearchError,
    search, get_stats, detect_environment,
)

__all__ = [
    "SkillIndex", "SearchResult", "SkillSearchError",
    "search", "get_stats", "detect_environment",
]
