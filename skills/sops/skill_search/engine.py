"""Skill search engine — API client (data model and environment detection included)."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field


# ── Data model ─────────────────────────────────────────────

@dataclass
class SkillIndex:
    """A single skill index entry (mirrors the server-side schema)."""
    key: str
    name: str = ""
    description: str = ""
    one_line_summary: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    language: str = "en"
    os: list[str] = field(default_factory=list)
    shell: list[str] = field(default_factory=list)
    runtimes: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    needs_tool_calling: bool = False
    needs_reasoning: bool = False
    min_context_window: str = "standard"
    decay_risk: str = "low"
    clarity: int = 0
    completeness: int = 0
    actionability: int = 0
    autonomous_safe: bool = True
    blast_radius: str = "low"
    requires_credentials: bool = False
    data_exposure: str = "none"
    effect_scope: str = "local"
    form: str = ""
    estimated_tokens: str = "medium"
    capabilities: list[str] = field(default_factory=list)
    github_stars: int = 0
    github_url: str = ""

    @property
    def quality_score(self):
        return self.clarity * 0.3 + self.completeness * 0.3 + self.actionability * 0.4

    @classmethod
    def from_dict(cls, d):
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class SearchResult:
    """A single search result."""
    skill: SkillIndex
    relevance: float = 0.0
    quality: float = 0.0
    final_score: float = 0.0
    match_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d):
        skill = SkillIndex.from_dict(d.get("skill", d))
        return cls(skill=skill, relevance=d.get("relevance", 0.0),
                   quality=d.get("quality", 0.0), final_score=d.get("final_score", 0.0),
                   match_reasons=d.get("match_reasons", []), warnings=d.get("warnings", []))


# ── Environment detection ─────────────────────────────────

def _run(cmd):
    try:
        r = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _detect_os():
    s = platform.system().lower()
    return {"darwin": "macos", "linux": "linux", "windows": "windows"}.get(s, s)


def _detect_shell():
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        return "zsh"
    if "bash" in shell:
        return "bash"
    if platform.system() == "Windows":
        return "powershell"
    return os.path.basename(shell) if shell else "unknown"


def _detect_runtimes():
    checks = {"python": ["python3", "python"], "node": ["node"], "go": ["go"],
              "rust": ["rustc"], "java": ["java"], "ruby": ["ruby"],
              "php": ["php"], "dotnet": ["dotnet"]}
    found = []
    for name, cmds in checks.items():
        for cmd in cmds:
            if shutil.which(cmd):
                found.append(name)
                break
    return found


def _detect_tools():
    tools = ["git", "docker", "npm", "pip", "curl", "wget", "kubectl",
             "terraform", "aws", "gcloud", "az", "brew", "cargo", "make", "cmake"]
    return [t for t in tools if shutil.which(t)]


def detect_environment():
    """Collect a complete description of the current environment."""
    return {"os": _detect_os(), "shell": _detect_shell(),
            "runtimes": _detect_runtimes(), "tools": _detect_tools(),
            "model": {"tool_calling": True, "reasoning": True, "context_window": "large"}}


# ── API configuration and HTTP plumbing ────────────────────

DEFAULT_API_URL = "http://www.fudankw.cn:58787"


def _get_api_url():
    return os.environ.get("SKILL_SEARCH_API", DEFAULT_API_URL)


def _get_api_key():
    return os.environ.get("SKILL_SEARCH_KEY")


class SkillSearchError(Exception):
    pass


def _api_request(endpoint, payload):
    url = f"{_get_api_url()}/{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    api_key = _get_api_key()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise SkillSearchError(f"API error {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise SkillSearchError(f"cannot connect to service: {e.reason}") from e
    except Exception as e:
        raise SkillSearchError(f"request failed: {e}") from e


# ── Public surface ────────────────────────────────────────

def search(query, env=None, category=None, top_k=10):
    if env is None:
        env = detect_environment()
    payload = {"query": query, "env": env, "top_k": top_k}
    if category:
        payload["category"] = category
    resp = _api_request("search", payload)
    return [SearchResult.from_dict(r) for r in resp.get("results", [])]


def get_stats(env=None):
    if env is None:
        env = detect_environment()
    return _api_request("stats", {"env": env})
