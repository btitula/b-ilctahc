#!/usr/bin/env python3
"""
AI CLI — ?? command
Supports OpenAI and Claude (Anthropic) providers, projects, streaming,
persistent history, rich output, and semantic caching.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import time
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

# ──────────────────────────────────────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────────────────────────────────────
CONFIG_DIR   = Path.home() / ".config" / "chatgpt-cli"
CONFIG_FILE  = CONFIG_DIR / "config.yaml"
PROJECTS_DIR = CONFIG_DIR / "projects"
HISTORY_DIR  = CONFIG_DIR / "history"
CACHE_DIR    = CONFIG_DIR / "cache"
USAGE_FILE   = CONFIG_DIR / "usage.json"

# Price per 1M tokens (input, output) — update as providers change pricing
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o":                    (2.50,  10.00),
    "gpt-4o-mini":               (0.15,   0.60),
    "gpt-4-turbo":               (10.00, 30.00),
    "gpt-3.5-turbo":             (0.50,   1.50),
    # Anthropic Claude
    "claude-opus-4-6":           (15.00, 75.00),
    "claude-sonnet-4-6":         (3.00,  15.00),
    "claude-haiku-4-5-20251001": (0.80,   4.00),
}

# Maps provider name (used in CLI/defaults) → config section key
PROVIDER_CFG_KEY = {"openai": "openai", "claude": "anthropic"}

# ──────────────────────────────────────────────────────────────────────────────
# Defaults
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "openai": {
        "api_key": "your-key-here",  # pragma: allowlist secret
        "model": "gpt-4o",
        "max_tokens": 2048,
        "temperature": 0.7,
    },
    "anthropic": {
        "api_key": "your-key-here",  # pragma: allowlist secret
        "model": "claude-sonnet-4-6",
        "max_tokens": 2048,
        "temperature": 0.7,
    },
    "defaults": {
        "provider": "openai",        # openai | claude
        "project": "default",
        "history_limit": 20,
        "stream": True,
    },
    "display": {
        "markdown": True,
        "show_project_header": True,
        "show_timestamp": True,
    },
    "cache": {
        "enabled": True,
        "ttl_days": 7,
        "max_entries": 200,
        "similarity_threshold": 0.82,
    },
}

DEFAULT_PROJECTS: dict[str, dict] = {
    "default": {
        "description": "General helpful assistant",
        "system_prompt": "You are a helpful assistant. Be concise and precise.",
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# App / Console
# ──────────────────────────────────────────────────────────────────────────────
app     = typer.Typer(add_completion=False, invoke_without_command=True)
console = Console()


# ──────────────────────────────────────────────────────────────────────────────
# Config helpers
# ──────────────────────────────────────────────────────────────────────────────
def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG
    with open(CONFIG_FILE) as f:
        user_cfg = yaml.safe_load(f) or {}
    return _deep_merge(DEFAULT_CONFIG, user_cfg)


# ──────────────────────────────────────────────────────────────────────────────
# Project helpers
# ──────────────────────────────────────────────────────────────────────────────
def load_project(name: str) -> dict | None:
    path = PROJECTS_DIR / f"{name}.yaml"
    if path.exists():
        with open(path) as f:
            return yaml.safe_load(f)
    return DEFAULT_PROJECTS.get(name)


def list_projects() -> list[str]:
    names: set[str] = set(DEFAULT_PROJECTS.keys())
    if PROJECTS_DIR.exists():
        names.update(p.stem for p in PROJECTS_DIR.glob("*.yaml"))
    return sorted(names)


# ──────────────────────────────────────────────────────────────────────────────
# History helpers
# ──────────────────────────────────────────────────────────────────────────────
def load_history(project: str) -> list[dict]:
    path = HISTORY_DIR / f"{project}.json"
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def save_history(project: str, history: list[dict], limit: int = 20) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    trimmed = history[-limit:]
    with open(HISTORY_DIR / f"{project}.json", "w") as f:
        json.dump(trimmed, f, indent=2, ensure_ascii=False)


def clear_history(project: str) -> None:
    path = HISTORY_DIR / f"{project}.json"
    if path.exists():
        path.unlink()


def history_message_count(project: str) -> int:
    path = HISTORY_DIR / f"{project}.json"
    if not path.exists():
        return 0
    with open(path) as f:
        return len(json.load(f))


def history_search(project: str | None, keyword: str) -> list[dict]:
    """Search conversation history for keyword across one or all projects.
    Returns matched (project, role, timestamp, snippet) dicts, grouped by turn.
    """
    kw = keyword.lower()
    projects = [project] if project else (
        [p.stem for p in HISTORY_DIR.glob("*.json")] if HISTORY_DIR.exists() else []
    )
    results = []
    for proj in sorted(projects):
        messages = load_history(proj)
        # walk pairs: user[i] + assistant[i+1]
        for i in range(0, len(messages) - 1, 2):
            user_msg = messages[i]
            asst_msg = messages[i + 1] if i + 1 < len(messages) else {}
            q = user_msg.get("content", "")
            a = asst_msg.get("content", "")
            if kw in q.lower() or kw in a.lower():
                # truncate to first 120 chars for display
                snippet = q if len(q) <= 120 else q[:117] + "..."
                results.append({
                    "project":   proj,
                    "timestamp": user_msg.get("timestamp", ""),
                    "question":  snippet,
                    "matched":   "question" if kw in q.lower() else "answer",
                })
    return results


# ──────────────────────────────────────────────────────────────────────────────
# Cache helpers
# ──────────────────────────────────────────────────────────────────────────────
_STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "how", "what", "why", "when", "where", "which", "who", "do", "does",
    "did", "can", "could", "will", "would", "should", "i", "me", "my",
    "we", "our", "you", "your", "it", "its",
}


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, remove stop words, sort words.
    'how to check database size with mysql' → 'check database mysql size'
    'with mysql how to check database size' → 'check database mysql size'
    """
    text = re.sub(r"[^\w\s]", " ", text.lower())
    words = [w for w in text.split() if w and w not in _STOP_WORDS]
    return " ".join(sorted(words))


def _cache_path(project: str) -> Path:
    return CACHE_DIR / f"{project}.json"


def _load_cache_data(project: str) -> dict:
    path = _cache_path(project)
    if not path.exists():
        return {"stats": {"hits": 0, "misses": 0}, "entries": {}}
    with open(path) as f:
        return json.load(f)


def _save_cache_data(project: str, data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(_cache_path(project), "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _evict_lru(entries: dict, max_entries: int) -> dict:
    if len(entries) <= max_entries:
        return entries
    # remove oldest last_accessed entries until within limit
    sorted_keys = sorted(entries, key=lambda k: entries[k]["last_accessed"])
    for key in sorted_keys[: len(entries) - max_entries]:
        del entries[key]
    return entries


def cache_lookup(project: str, question: str, cfg: dict) -> dict | None:
    """Return cached entry dict (with 'entry' and 'score') or None on miss."""
    if not cfg.get("enabled", True):
        return None

    data     = _load_cache_data(project)
    entries  = data["entries"]
    norm_q   = _normalize(question)
    ttl_secs = cfg.get("ttl_days", 7) * 86400
    threshold = cfg.get("similarity_threshold", 0.82)
    now      = time.time()

    best_score, best_key = 0.0, None
    for key, entry in entries.items():
        if now - entry["created_at"] > ttl_secs:
            continue
        score = SequenceMatcher(None, norm_q, key).ratio()
        if score > best_score:
            best_score, best_key = score, key

    if best_key and best_score >= threshold:
        entries[best_key]["hit_count"]    += 1
        entries[best_key]["last_accessed"] = now
        data["stats"]["hits"]             += 1
        _save_cache_data(project, data)
        return {"entry": entries[best_key], "score": best_score}

    data["stats"]["misses"] += 1
    _save_cache_data(project, data)
    return None


def cache_store(project: str, question: str, answer: str, cfg: dict) -> None:
    if not cfg.get("enabled", True):
        return
    data    = _load_cache_data(project)
    entries = data["entries"]
    norm_q  = _normalize(question)
    now     = time.time()
    entries[norm_q] = {
        "question":     question,
        "answer":       answer,
        "created_at":   now,
        "last_accessed": now,
        "hit_count":    0,
    }
    data["entries"] = _evict_lru(entries, cfg.get("max_entries", 200))
    _save_cache_data(project, data)


def cache_delete_entry(project: str, question: str, cfg: dict) -> bool:
    """Delete the best-matching cache entry for question. Returns True if deleted."""
    data      = _load_cache_data(project)
    norm_q    = _normalize(question)
    threshold = cfg.get("similarity_threshold", 0.82)

    best_score, best_key = 0.0, None
    for key in data["entries"]:
        score = SequenceMatcher(None, norm_q, key).ratio()
        if score > best_score:
            best_score, best_key = score, key

    if best_key and best_score >= threshold:
        del data["entries"][best_key]
        _save_cache_data(project, data)
        return True
    return False


def cache_clear(project: str | None = None) -> None:
    if project:
        path = _cache_path(project)
        if path.exists():
            path.unlink()
    elif CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)


def cache_search(project: str | None, keyword: str) -> list[dict]:
    """Return cache entries whose original question contains keyword (case-insensitive)."""
    kw = keyword.lower()
    projects = [project] if project else (
        [p.stem for p in CACHE_DIR.glob("*.json")] if CACHE_DIR.exists() else []
    )
    results = []
    now = time.time()
    for proj in sorted(projects):
        data = _load_cache_data(proj)
        for key, entry in data["entries"].items():
            if kw in entry["question"].lower():
                age_days = (now - entry["created_at"]) / 86400
                results.append({
                    "project":   proj,
                    "question":  entry["question"],
                    "hit_count": entry["hit_count"],
                    "age_days":  round(age_days, 1),
                    "key":       key,
                })
    return results


def cache_get_stats(project: str | None = None) -> list[dict]:
    if not CACHE_DIR.exists():
        return []
    projects = [project] if project else [p.stem for p in CACHE_DIR.glob("*.json")]
    results  = []
    for proj in sorted(projects):
        data    = _load_cache_data(proj)
        entries = data["entries"]
        stats   = data["stats"]
        total   = stats["hits"] + stats["misses"]
        hit_rate = f"{stats['hits'] / total * 100:.0f}%" if total else "n/a"
        results.append({
            "project":  proj,
            "entries":  len(entries),
            "hits":     stats["hits"],
            "misses":   stats["misses"],
            "hit_rate": hit_rate,
        })
    return results


def cache_backup(dest: str) -> int:
    all_data: dict = {}
    if CACHE_DIR.exists():
        for p in CACHE_DIR.glob("*.json"):
            with open(p) as f:
                all_data[p.stem] = json.load(f)
    with open(dest, "w") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)
    return len(all_data)


def cache_restore(src: str) -> int:
    with open(src) as f:
        all_data: dict = json.load(f)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for proj, data in all_data.items():
        with open(CACHE_DIR / f"{proj}.json", "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    return len(all_data)


# ──────────────────────────────────────────────────────────────────────────────
# Init
# ──────────────────────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────────────
# Usage / cost tracking
# ──────────────────────────────────────────────────────────────────────────────
def _calc_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    input_price, output_price = MODEL_PRICING.get(model, (0.0, 0.0))
    return (prompt_tokens * input_price + completion_tokens * output_price) / 1_000_000


def _load_usage() -> dict:
    if not USAGE_FILE.exists():
        return {"total_calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
                "cost_usd": 0.0, "cache_hits": 0, "by_project": {}, "by_model": {},
                "by_provider": {}}
    data = json.load(open(USAGE_FILE))
    data.setdefault("by_provider", {})   # migrate old files
    return data


def _save_usage(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(USAGE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def record_usage(project: str, model: str, prompt_tokens: int, completion_tokens: int,
                 provider: str = "openai") -> float:
    cost = _calc_cost(model, prompt_tokens, completion_tokens)
    data = _load_usage()

    data["total_calls"]        += 1
    data["prompt_tokens"]      += prompt_tokens
    data["completion_tokens"]  += completion_tokens
    data["cost_usd"]           += cost

    p = data["by_project"].setdefault(project, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0})
    p["calls"]             += 1
    p["prompt_tokens"]     += prompt_tokens
    p["completion_tokens"] += completion_tokens
    p["cost_usd"]          += cost

    m = data["by_model"].setdefault(model, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0})
    m["calls"]             += 1
    m["prompt_tokens"]     += prompt_tokens
    m["completion_tokens"] += completion_tokens
    m["cost_usd"]          += cost

    pr = data["by_provider"].setdefault(provider, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0})
    pr["calls"]             += 1
    pr["prompt_tokens"]     += prompt_tokens
    pr["completion_tokens"] += completion_tokens
    pr["cost_usd"]          += cost

    _save_usage(data)
    return cost


def record_cache_hit() -> None:
    data = _load_usage()
    data["cache_hits"] += 1
    _save_usage(data)


def show_usage_report(project: str | None = None) -> None:
    data = _load_usage()
    total   = data["total_calls"]
    hits    = data["cache_hits"]
    api_calls = total - hits if total > hits else total

    console.print()
    console.print(Panel(
        f"[bold]Total API calls:[/bold] {api_calls}   "
        f"[bold]Cache hits:[/bold] [green]{hits}[/green]   "
        f"[bold]Total cost:[/bold] [yellow]${data['cost_usd']:.4f}[/yellow]\n"
        f"[dim]Prompt tokens: {data['prompt_tokens']:,}   "
        f"Completion tokens: {data['completion_tokens']:,}   "
        f"Total: {data['prompt_tokens'] + data['completion_tokens']:,}[/dim]",
        title="Usage Report",
        border_style="cyan",
    ))

    if project:
        proj_data = data["by_project"].get(project)
        if not proj_data:
            console.print(f"[dim]No usage data for project: {project}[/dim]")
            return
        breakdown = {project: proj_data}
    else:
        breakdown = data["by_project"]

    if breakdown:
        table = Table(title="By Project", box=box.ROUNDED, border_style="cyan")
        table.add_column("Project",    style="bold green", no_wrap=True)
        table.add_column("API Calls",  justify="right")
        table.add_column("Prompt",     justify="right", style="dim")
        table.add_column("Completion", justify="right", style="dim")
        table.add_column("Cost (USD)", justify="right", style="yellow")
        for proj, d in sorted(breakdown.items()):
            table.add_row(proj, str(d["calls"]),
                          f"{d['prompt_tokens']:,}", f"{d['completion_tokens']:,}",
                          f"${d['cost_usd']:.4f}")
        console.print(table)

    if not project and data.get("by_provider"):
        table_pr = Table(title="By Provider", box=box.ROUNDED, border_style="cyan")
        table_pr.add_column("Provider",   style="bold green", no_wrap=True)
        table_pr.add_column("API Calls",  justify="right")
        table_pr.add_column("Prompt",     justify="right", style="dim")
        table_pr.add_column("Completion", justify="right", style="dim")
        table_pr.add_column("Cost (USD)", justify="right", style="yellow")
        for prov, d in sorted(data["by_provider"].items()):
            table_pr.add_row(prov, str(d["calls"]),
                             f"{d['prompt_tokens']:,}", f"{d['completion_tokens']:,}",
                             f"${d['cost_usd']:.4f}")
        console.print(table_pr)

    if data["by_model"] and not project:
        table2 = Table(title="By Model", box=box.ROUNDED, border_style="cyan")
        table2.add_column("Model",     style="bold green", no_wrap=True)
        table2.add_column("API Calls", justify="right")
        table2.add_column("Cost (USD)", justify="right", style="yellow")
        for mdl, d in sorted(data["by_model"].items()):
            table2.add_row(mdl, str(d["calls"]), f"${d['cost_usd']:.4f}")
        console.print(table2)

    console.print()


def run_init() -> None:
    for d in (CONFIG_DIR, PROJECTS_DIR, HISTORY_DIR, CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)

    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False, sort_keys=False)
        CONFIG_FILE.chmod(0o600)
        console.print(f"[green]Config created:[/green] {CONFIG_FILE}")
    else:
        console.print(f"[dim]Config already exists:[/dim] {CONFIG_FILE}")

    for name, data in DEFAULT_PROJECTS.items():
        project_file = PROJECTS_DIR / f"{name}.yaml"
        if not project_file.exists():
            with open(project_file, "w") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    console.print(f"[green]Projects:[/green]  {PROJECTS_DIR}")
    console.print(f"[green]History:[/green]   {HISTORY_DIR}")
    console.print(f"[green]Cache:[/green]     {CACHE_DIR}")
    console.print()
    console.print(f"[bold yellow]Add your OpenAI API key to:[/bold yellow]")
    console.print(f"   [bold]{CONFIG_FILE}[/bold]")
    console.print()
    console.print("[dim]Then run:[/dim]  [bold]?? devops how do I drain an ECS task?[/bold]")


# ──────────────────────────────────────────────────────────────────────────────
# Project detection from positional args
# (if first word matches a known project, treat it as project name)
# ──────────────────────────────────────────────────────────────────────────────
def _parse_project_and_question(
    args: list[str],
    default_project: str,
) -> tuple[str, str]:
    if not args:
        return default_project, ""

    first = args[0].lower()
    if first in list_projects():
        return first, " ".join(args[1:])

    return default_project, " ".join(args)


# ──────────────────────────────────────────────────────────────────────────────
# CLI Entry
# ──────────────────────────────────────────────────────────────────────────────
@app.callback(invoke_without_command=True)
def main(
    ctx:            typer.Context,
    args:           Optional[list[str]] = typer.Argument(None),
    project:        Optional[str]       = typer.Option(None,   "--project",        "-p", help="Project/persona to use"),
    clear:          bool                = typer.Option(False,  "--clear",          "-c", help="Clear conversation history for the active project"),
    list_proj:      bool                = typer.Option(False,  "--list",           "-l", help="List available projects"),
    show_hist:      bool                = typer.Option(False,  "--history",        "-H", help="Show conversation history for the active project"),
    hist_search_kw: Optional[str]      = typer.Option(None,   "--history-search",       help="Search conversation history by keyword"),
    copy_last:      bool                = typer.Option(False,  "--copy",                 help="Copy last answer to clipboard"),
    new:            bool                = typer.Option(False,  "--new",            "-n", help="Start fresh (ignore history for this turn only)"),
    no_stream:      bool                = typer.Option(False,  "--no-stream",            help="Disable token streaming"),
    provider:       Optional[str]       = typer.Option(None,   "--provider",      "-P",  help="AI provider: openai or claude (overrides config)"),
    init:           bool                = typer.Option(False,  "--init",                 help="Initialise config and project files"),
    no_cache:       bool                = typer.Option(False,  "--no-cache",       "-C", help="Bypass cache for this query"),
    show_cache:     bool                = typer.Option(False,  "--cache-stats",          help="Show cache hit/miss statistics"),
    clear_cache:    bool                = typer.Option(False,  "--clear-cache",          help="Clear cache (all projects, or use -p for one)"),
    cache_delete:   Optional[str]       = typer.Option(None,   "--cache-delete",         help="Delete cache entry matching this question"),
    backup_file:    Optional[str]       = typer.Option(None,   "--cache-backup",         help="Backup all cache to a JSON file"),
    restore_file:   Optional[str]       = typer.Option(None,   "--cache-restore",        help="Restore cache from a backup JSON file"),
    cache_search_kw: Optional[str]     = typer.Option(None,   "--cache-search",          help="Search cached questions by keyword"),
    usage:          bool                = typer.Option(False,  "--usage",                 help="Show token usage and cost report"),
    set_provider:   Optional[str]       = typer.Option(None,   "--set",                   help="Set default provider in config: openai or claude"),
    show_status:    bool                = typer.Option(False,  "--status",                help="Show current provider, model, and config settings"),
) -> None:
    # ── Init ──────────────────────────────────────────────────────────────────
    if init:
        run_init()
        return

    config = load_config()

    # ── Set provider ──────────────────────────────────────────────────────────
    if set_provider:
        if set_provider not in ("openai", "claude"):
            console.print(f"[red]Error: unknown provider:[/red] [bold]{set_provider}[/bold]  (use openai or claude)")
            raise typer.Exit(1)
        cfg = load_config()
        cfg["defaults"]["provider"] = set_provider
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
        console.print(f"[green]Default provider set to:[/green] [bold]{set_provider}[/bold]")
        console.print(f"[dim]Edit model/key: {CONFIG_FILE}[/dim]")
        return

    # ── Status ────────────────────────────────────────────────────────────────
    if show_status:
        cur_provider = config["defaults"].get("provider", "openai")
        rows = []
        for prov in ("openai", "claude"):
            prov_cfg = config.get(PROVIDER_CFG_KEY[prov], {})
            key = prov_cfg.get("api_key", "")
            key_status = "[green]set[/green]" if key and "your-key" not in key else "[red]not set[/red]"
            model_val  = prov_cfg.get("model", DEFAULT_CONFIG.get(prov, {}).get("model", "?"))
            active     = "[bold cyan]* active[/bold cyan]" if prov == cur_provider else ""
            rows.append((prov, key_status, model_val, active))

        table = Table(title="Current Settings", box=box.ROUNDED, border_style="cyan")
        table.add_column("Provider",  style="bold green", no_wrap=True)
        table.add_column("API Key",   justify="center")
        table.add_column("Model",     style="dim")
        table.add_column("",          justify="left")
        for prov, ks, mdl, active in rows:
            table.add_row(prov, ks, mdl, active)
        console.print()
        console.print(table)
        console.print(
            f"\n[dim]Default project:[/dim] {config['defaults'].get('project', 'default')}  "
            f"[dim]History limit:[/dim] {config['defaults'].get('history_limit', 20)}  "
            f"[dim]Stream:[/dim] {config['defaults'].get('stream', True)}  "
            f"[dim]Cache:[/dim] {config.get('cache', {}).get('enabled', True)}"
        )
        console.print(f"[dim]Config:[/dim] {CONFIG_FILE}\n")
        return
    cache_cfg = config.get("cache", DEFAULT_CONFIG["cache"])
    default_project = config["defaults"]["project"]

    # ── Resolve project + question from positional args ───────────────────────
    args = args or []
    if project:
        resolved_project = project
        question_text    = " ".join(args)
    else:
        resolved_project, question_text = _parse_project_and_question(args, default_project)

    # ── Piped stdin ───────────────────────────────────────────────────────────
    piped_input = ""
    if not sys.stdin.isatty():
        piped_input = sys.stdin.read().strip()
        if piped_input:
            question_text = f"{question_text}\n\n{piped_input}" if question_text.strip() else piped_input

    # ── Cache stats ───────────────────────────────────────────────────────────
    if show_cache:
        stats = cache_get_stats(resolved_project if project else None)
        if not stats:
            console.print("[dim]No cache data found.[/dim]")
            return
        table = Table(title="Cache Statistics", box=box.ROUNDED, border_style="cyan")
        table.add_column("Project",  style="bold green",  no_wrap=True)
        table.add_column("Entries",  justify="right")
        table.add_column("Hits",     style="green",  justify="right")
        table.add_column("Misses",   style="yellow", justify="right")
        table.add_column("Hit Rate", style="cyan",   justify="right")
        for s in stats:
            table.add_row(s["project"], str(s["entries"]), str(s["hits"]), str(s["misses"]), s["hit_rate"])
        console.print()
        console.print(table)
        console.print()
        return

    # ── Clear cache ───────────────────────────────────────────────────────────
    if clear_cache:
        proj = resolved_project if project else None
        cache_clear(proj)
        label = f"[bold]{proj}[/bold]" if proj else "all projects"
        console.print(f"[green]Cache cleared:[/green] {label}")
        return

    # ── Cache delete entry ─────────────────────────────────────────────────────
    if cache_delete:
        deleted = cache_delete_entry(resolved_project, cache_delete, cache_cfg)
        if deleted:
            console.print(f"[green]Cache entry deleted:[/green] [bold]{resolved_project}[/bold]")
        else:
            console.print(f"[yellow]No matching cache entry found in[/yellow] [bold]{resolved_project}[/bold]")
        return

    # ── Cache backup ───────────────────────────────────────────────────────────
    if backup_file:
        n = cache_backup(backup_file)
        console.print(f"[green]Cache backed up:[/green] {n} project(s) → [bold]{backup_file}[/bold]")
        return

    # ── Cache restore ──────────────────────────────────────────────────────────
    if restore_file:
        n = cache_restore(restore_file)
        console.print(f"[green]Cache restored:[/green] {n} project(s) from [bold]{restore_file}[/bold]")
        return

    # ── Cache search ──────────────────────────────────────────────────────────
    if cache_search_kw:
        results = cache_search(resolved_project if project else None, cache_search_kw)
        if not results:
            console.print(f"[dim]No cached entries matching:[/dim] [bold]{cache_search_kw}[/bold]")
            return
        table = Table(
            title=f"Cache search: \"{cache_search_kw}\"",
            box=box.ROUNDED, border_style="cyan",
        )
        table.add_column("Project",   style="bold green", no_wrap=True)
        table.add_column("Question",  style="white")
        table.add_column("Hits",      justify="right", style="cyan")
        table.add_column("Age (days)", justify="right", style="dim")
        for r in results:
            table.add_row(r["project"], r["question"], str(r["hit_count"]), str(r["age_days"]))
        console.print()
        console.print(table)
        console.print()
        return

    # ── Usage report ──────────────────────────────────────────────────────────
    if usage:
        show_usage_report(resolved_project if project else None)
        return

    # ── Copy last answer to clipboard ─────────────────────────────────────────
    if copy_last:
        hist = load_history(resolved_project)
        last = next((m["content"] for m in reversed(hist) if m["role"] == "assistant"), None)
        if not last:
            console.print(f"[yellow]No answer in history for[/yellow] [bold]{resolved_project}[/bold]")
            return
        try:
            import subprocess
            subprocess.run("pbcopy", input=last.encode(), check=True)
            preview = last[:80].replace("\n", " ")
            console.print(f"[green]Copied to clipboard:[/green] [dim]{preview}...[/dim]")
        except FileNotFoundError:
            console.print("[red]pbcopy not found.[/red] Only supported on macOS.")
        return

    # ── History search ────────────────────────────────────────────────────────
    if hist_search_kw:
        results = history_search(resolved_project if project else None, hist_search_kw)
        if not results:
            console.print(f"[dim]No history matching:[/dim] [bold]{hist_search_kw}[/bold]")
            return
        table = Table(
            title=f"History search: \"{hist_search_kw}\"",
            box=box.ROUNDED, border_style="cyan",
        )
        table.add_column("Project",   style="bold green", no_wrap=True)
        table.add_column("When",      style="dim",        no_wrap=True)
        table.add_column("Matched in", style="dim",       no_wrap=True)
        table.add_column("Question",  style="white")
        for r in results:
            table.add_row(r["project"], r["timestamp"], r["matched"], r["question"])
        console.print()
        console.print(table)
        console.print()
        return

    # ── List projects ─────────────────────────────────────────────────────────
    if list_proj:
        table = Table(title="Available Projects", box=box.ROUNDED, border_style="cyan")
        table.add_column("Project",     style="bold green",  no_wrap=True)
        table.add_column("Description", style="white")
        table.add_column("History",     style="dim",         justify="right")
        table.add_column("Cache",       style="dim",         justify="right")

        for name in list_projects():
            proj  = load_project(name)
            desc  = proj.get("description", "—") if proj else "custom"
            count = history_message_count(name)
            hist_label  = f"{count // 2} turns" if count else "empty"
            cache_data  = _load_cache_data(name)
            cache_label = f"{len(cache_data['entries'])} entries" if cache_data["entries"] else "empty"
            table.add_row(name, desc, hist_label, cache_label)

        console.print()
        console.print(table)
        console.print()
        return

    # ── Clear history ─────────────────────────────────────────────────────────
    if clear:
        clear_history(resolved_project)
        console.print(f"[green]History cleared:[/green] [bold]{resolved_project}[/bold]")
        return

    # ── Show history ──────────────────────────────────────────────────────────
    if show_hist:
        hist = load_history(resolved_project)
        if not hist:
            console.print(f"[dim]No history for[/dim] [bold]{resolved_project}[/bold]")
            return

        console.print()
        console.print(Panel(
            f"[bold cyan]{resolved_project}[/bold cyan]  [dim]({len(hist)//2} turns)[/dim]",
            title="Conversation History",
            border_style="cyan",
        ))

        for msg in hist:
            role    = msg["role"]
            content = msg["content"]
            ts      = msg.get("timestamp", "")

            if role == "user":
                console.print(f"\n[bold yellow]  You[/bold yellow]  [dim]{ts}[/dim]")
                console.print(f"  {content}")
            else:
                console.print(f"\n[bold blue]  Assistant[/bold blue]  [dim]{ts}[/dim]")
                if config["display"]["markdown"]:
                    console.print(Markdown(content))
                else:
                    console.print(content)

        console.print()
        return

    # ── Validate question ─────────────────────────────────────────────────────
    if not question_text.strip():
        console.print("[red]Error: no question provided.[/red]\n")
        console.print("Usage:")
        console.print("  [bold]??[/bold] [dim]your question[/dim]")
        console.print("  [bold]?? devops[/bold] [dim]how do I drain an ECS task?[/dim]")
        console.print("  [bold]?? nodejs[/bold] [dim]NestJS CRUD endpoint with Prisma[/dim]")
        console.print("  [bold]?? reactjs[/bold] [dim]login form with react-hook-form and zod[/dim]")
        console.print("  [bold]?? frontend[/bold] [dim]responsive card grid with CSS Grid and dark mode[/dim]")
        console.print("  [bold]cat file.sql | ?? sql[/bold] [dim]review this query[/dim]")
        console.print()
        console.print("Projects:")
        console.print("  [dim]devops[/dim]     AWS — ECS Fargate, EKS, Aurora, ElastiCache, CloudFront")
        console.print("  [dim]python[/dim]     FastAPI, Pydantic v2, SQLAlchemy, boto3, Lambda")
        console.print("  [dim]nodejs[/dim]     NestJS / Express, TypeScript, Prisma, Zod, REST/GraphQL")
        console.print("  [dim]reactjs[/dim]    React 18, TypeScript, TanStack Query, Tailwind, shadcn/ui")
        console.print("  [dim]frontend[/dim]   HTML5, CSS3, vanilla JS, responsive, accessibility (WCAG)")
        console.print("  [dim]sql[/dim]        Aurora MySQL/PG, ElastiCache Valkey, RDS Proxy")
        console.print("  [dim]monitoring[/dim] Prometheus, Grafana, Thanos, Alertmanager, CloudWatch")
        console.print("  [dim]pipeline[/dim]   Bitbucket Pipelines, Jenkins, ECS/EKS deployments")
        console.print("  [dim]review[/dim]     Code review — security, IaC, Dockerfiles, SOC2")
        console.print("  [dim]security[/dim]   IAM, KMS, GuardDuty, Security Hub, SOC2")
        console.print("  [bold]?? -l[/bold]              [dim]full list with history + cache counts[/dim]")
        console.print()
        console.print("Conversations:")
        console.print("  [bold]?? -H[/bold]                        [dim]show history (current project)[/dim]")
        console.print("  [bold]?? -c[/bold]                        [dim]clear history (current project)[/dim]")
        console.print("  [bold]?? -n devops[/bold] [dim]...[/dim]        [dim]start fresh (ignore history this turn)[/dim]")
        console.print("  [bold]?? --history-search[/bold] [dim]KEYWORD  search history across projects[/dim]")
        console.print("  [bold]?? --copy[/bold]                    [dim]copy last answer to clipboard[/dim]")
        console.print()
        console.print("Provider:")
        console.print("  [bold]?? --status[/bold]                  [dim]show active provider, model, API key status[/dim]")
        console.print("  [bold]?? --set claude[/bold]              [dim]switch default provider to Claude[/dim]")
        console.print("  [bold]?? --set openai[/bold]              [dim]switch default provider to OpenAI[/dim]")
        console.print("  [bold]?? -P claude[/bold] [dim]...[/dim]        [dim]use Claude for this query only[/dim]")
        console.print()
        console.print("Cache:")
        console.print("  [bold]?? --cache-stats[/bold]             [dim]hit/miss stats per project[/dim]")
        console.print("  [bold]?? --cache-search[/bold] [dim]KEYWORD     search cached questions[/dim]")
        console.print("  [bold]?? --clear-cache[/bold]             [dim]clear cache (add -p for one project)[/dim]")
        console.print("  [bold]?? --cache-delete[/bold] [dim]QUESTION    delete matching cache entry[/dim]")
        console.print("  [bold]?? --cache-backup[/bold] [dim]FILE        backup cache to JSON[/dim]")
        console.print("  [bold]?? --cache-restore[/bold] [dim]FILE       restore cache from JSON[/dim]")
        console.print("  [bold]?? -C[/bold] [dim]...[/dim]               [dim]bypass cache for this query[/dim]")
        console.print()
        console.print("Usage & setup:")
        console.print("  [bold]?? --usage[/bold]                   [dim]token usage and cost report (by provider/project)[/dim]")
        console.print("  [bold]?? --init[/bold]                    [dim]set up config and project files[/dim]")
        raise typer.Exit(1)

    # ── Load project ──────────────────────────────────────────────────────────
    proj = load_project(resolved_project)
    if not proj:
        console.print(f"[red]Error: project not found:[/red] [bold]{resolved_project}[/bold]")
        console.print("Run [bold]?? --list[/bold] to see available projects")
        raise typer.Exit(1)

    # ── Resolve provider: project yaml → CLI flag → config default ───────────
    effective_provider = proj.get("provider") or provider or config["defaults"].get("provider", "openai")
    if effective_provider not in ("openai", "claude"):
        console.print(f"[red]Error: unknown provider:[/red] [bold]{effective_provider}[/bold]  (use openai or claude)")
        raise typer.Exit(1)
    provider_cfg = config.get(PROVIDER_CFG_KEY[effective_provider], config["openai"])

    system_prompt = proj["system_prompt"]
    model       = proj.get("model",       provider_cfg["model"])
    temperature = proj.get("temperature", provider_cfg["temperature"])
    max_tokens  = provider_cfg.get("max_tokens", 2048)

    # ── Build conversation history ────────────────────────────────────────────
    conv_history = [] if new else load_history(resolved_project)

    # ── Header ────────────────────────────────────────────────────────────────
    if config["display"]["show_project_header"]:
        turns_label = f"{len(conv_history)//2} prior turns" if conv_history else "new conversation"
        pipe_label  = "  · piped input" if piped_input else ""
        display_text = question_text if not piped_input else (
            question_text[: question_text.index(piped_input)].strip() or "[piped input]"
        )
        console.print()
        console.print(Panel(
            Text(display_text, style="bold yellow"),
            title=f"[cyan] {resolved_project} [/cyan]  [dim]{turns_label} · {effective_provider} · {model}{pipe_label}[/dim]",
            border_style="dim blue",
            padding=(0, 1),
        ))

    # ── Cache lookup ──────────────────────────────────────────────────────────
    if not no_cache:
        hit = cache_lookup(resolved_project, question_text, cache_cfg)
        if hit:
            pct = int(hit["score"] * 100)
            original = hit["entry"]["question"]
            record_cache_hit()
            console.print(f"\n[dim]cached · {pct}% match — \"{original}\"[/dim]\n")
            if config["display"]["markdown"]:
                console.print(Markdown(hit["entry"]["answer"]))
            else:
                console.print(hit["entry"]["answer"])
            console.print()
            return

    # ── API key guard ─────────────────────────────────────────────────────────
    api_key = provider_cfg["api_key"]
    if api_key in ("your-key-here",) or api_key.startswith("sk-your-key"):  # pragma: allowlist secret
        console.print(f"\n[red]Error: {effective_provider} API key not configured.[/red]")
        console.print(f"   Edit: [bold]{CONFIG_FILE}[/bold]")
        raise typer.Exit(1)

    stream_enabled = config["defaults"]["stream"] and not no_stream
    render_md      = config["display"]["markdown"]

    full_response     = ""
    prompt_tokens     = 0
    completion_tokens = 0
    console.print()

    try:
        if effective_provider == "claude":
            # ── Anthropic Claude ──────────────────────────────────────────
            try:
                from anthropic import Anthropic  # lazy import
            except ImportError:
                console.print("[red]Error: anthropic package not installed.[/red]")
                console.print("   Run: [bold]pip install anthropic[/bold]")
                raise typer.Exit(1)

            client = Anthropic(api_key=api_key)
            anth_messages = [{"role": m["role"], "content": m["content"]} for m in conv_history]
            anth_messages.append({"role": "user", "content": question_text})

            if stream_enabled:
                with console.status("[dim]thinking...[/dim]", spinner="dots"):
                    with client.messages.stream(
                        model      = model,
                        max_tokens = max_tokens,
                        temperature = temperature,
                        system     = system_prompt,
                        messages   = anth_messages,
                    ) as stream:
                        for text in stream.text_stream:
                            full_response += text
                        final = stream.get_final_message()
                        prompt_tokens     = final.usage.input_tokens
                        completion_tokens = final.usage.output_tokens
            else:
                response = client.messages.create(
                    model       = model,
                    max_tokens  = max_tokens,
                    temperature = temperature,
                    system      = system_prompt,
                    messages    = anth_messages,
                )
                full_response     = response.content[0].text
                prompt_tokens     = response.usage.input_tokens
                completion_tokens = response.usage.output_tokens

        else:
            # ── OpenAI ────────────────────────────────────────────────────
            try:
                from openai import OpenAI  # lazy import — faster startup for non-API commands
            except ImportError:
                console.print("[red]Error: openai package not installed.[/red]")
                console.print("   Run: [bold]pip install openai[/bold]")
                raise typer.Exit(1)

            client = OpenAI(api_key=api_key)
            messages: list[dict] = [{"role": "system", "content": system_prompt}]
            for m in conv_history:
                messages.append({"role": m["role"], "content": m["content"]})
            messages.append({"role": "user", "content": question_text})

            if stream_enabled:
                stream = client.chat.completions.create(
                    model          = model,
                    max_tokens     = max_tokens,
                    temperature    = temperature,
                    messages       = messages,
                    stream         = True,
                    stream_options = {"include_usage": True},
                )
                with console.status("[dim]thinking...[/dim]", spinner="dots"):
                    for chunk in stream:
                        if chunk.choices:
                            delta = chunk.choices[0].delta.content or ""
                            full_response += delta
                        if chunk.usage:
                            prompt_tokens     = chunk.usage.prompt_tokens
                            completion_tokens = chunk.usage.completion_tokens
            else:
                response = client.chat.completions.create(
                    model       = model,
                    max_tokens  = max_tokens,
                    temperature = temperature,
                    messages    = messages,
                )
                full_response     = response.choices[0].message.content
                prompt_tokens     = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens

        if render_md:
            console.print(Markdown(full_response))
        else:
            console.print(full_response)
        console.print()

    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
        if full_response:
            console.print("[dim](Partial response not saved)[/dim]")
        raise typer.Exit(0)

    except Exception as e:
        console.print(f"\n[red]API Error:[/red] {e}")
        raise typer.Exit(1)

    # ── Record usage + display token line ─────────────────────────────────────
    if prompt_tokens or completion_tokens:
        cost = record_usage(resolved_project, model, prompt_tokens, completion_tokens,
                            provider=effective_provider)
        total_tokens = prompt_tokens + completion_tokens
        console.print(
            f"[dim]tokens: {prompt_tokens:,} prompt · {completion_tokens:,} completion"
            f" · {total_tokens:,} total · ${cost:.4f}[/dim]"
        )
        console.print()

    # ── Save to history ───────────────────────────────────────────────────────
    ts = datetime.now().strftime("%Y-%m-%d %H:%M") if config["display"]["show_timestamp"] else ""
    conv_history.append({"role": "user",      "content": question_text,  "timestamp": ts})
    conv_history.append({"role": "assistant", "content": full_response,  "timestamp": ts})
    save_history(resolved_project, conv_history, limit=config["defaults"]["history_limit"])

    # ── Store in cache ─────────────────────────────────────────────────────────
    if not no_cache:
        cache_store(resolved_project, question_text, full_response, cache_cfg)


if __name__ == "__main__":
    app()
