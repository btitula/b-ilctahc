#!/usr/bin/env python3
"""
ChatGPT CLI — ?? command
Supports projects, streaming, persistent history, rich output.
"""

from __future__ import annotations

import json
from datetime import datetime
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
    "defaults": {
        "project": "default",
        "history_limit": 20,
        "stream": True,
    },
    "display": {
        "markdown": True,
        "show_project_header": True,
        "show_timestamp": True,
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


# ──────────────────────────────────────────────────────────────────────────────
# Init
# ──────────────────────────────────────────────────────────────────────────────
def run_init() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

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
    ctx:       typer.Context,
    args:      Optional[list[str]] = typer.Argument(None),
    project:   Optional[str]       = typer.Option(None,   "--project",   "-p",  help="Project/persona to use"),
    clear:     bool                = typer.Option(False,  "--clear",     "-c",  help="Clear history for the active project"),
    list_proj: bool                = typer.Option(False,  "--list",      "-l",  help="List available projects"),
    show_hist: bool                = typer.Option(False,  "--history",   "-H",  help="Show conversation history for the active project"),
    new:       bool                = typer.Option(False,  "--new",       "-n",  help="Start fresh (ignore history for this turn only)"),
    no_stream: bool                = typer.Option(False,  "--no-stream",        help="Disable token streaming"),
    init:      bool                = typer.Option(False,  "--init",             help="Initialise config and project files"),
) -> None:
    # ── Init ──────────────────────────────────────────────────────────────────
    if init:
        run_init()
        return

    config = load_config()
    default_project = config["defaults"]["project"]

    # ── Resolve project + question from positional args ───────────────────────
    args = args or []
    if project:
        # --project flag explicitly set → all positional args = question
        resolved_project = project
        question_text    = " ".join(args)
    else:
        resolved_project, question_text = _parse_project_and_question(args, default_project)

    # ── List projects ─────────────────────────────────────────────────────────
    if list_proj:
        table = Table(title="Available Projects", box=box.ROUNDED, border_style="cyan")
        table.add_column("Project",     style="bold green",  no_wrap=True)
        table.add_column("Description", style="white")
        table.add_column("History",     style="dim",         justify="right")

        for name in list_projects():
            proj = load_project(name)
            desc  = proj.get("description", "—") if proj else "custom"
            count = history_message_count(name)
            hist_label = f"{count // 2} turns" if count else "empty"
            table.add_row(name, desc, hist_label)

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
            role      = msg["role"]
            content   = msg["content"]
            ts        = msg.get("timestamp", "")

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
        console.print("  [bold]??[/bold] [dim]your question here[/dim]")
        console.print("  [bold]?? devops[/bold] [dim]how do I drain an ECS task?[/dim]")
        console.print("  [bold]?? --project python[/bold] [dim]write a boto3 s3 lister[/dim]")
        console.print("  [bold]?? --list[/bold]       [dim]show all projects[/dim]")
        console.print("  [bold]?? --init[/bold]       [dim]set up config files[/dim]")
        raise typer.Exit(1)

    # ── Load project ──────────────────────────────────────────────────────────
    proj = load_project(resolved_project)
    if not proj:
        console.print(f"[red]Error: project not found:[/red] [bold]{resolved_project}[/bold]")
        console.print("Run [bold]?? --list[/bold] to see available projects")
        raise typer.Exit(1)

    system_prompt = proj["system_prompt"]

    # ── Build messages ────────────────────────────────────────────────────────
    conv_history = [] if new else load_history(resolved_project)

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    for m in conv_history:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": question_text})

    # ── Header ────────────────────────────────────────────────────────────────
    if config["display"]["show_project_header"]:
        turns_label = f"{len(conv_history)//2} prior turns" if conv_history else "new conversation"
        console.print()
        console.print(Panel(
            Text(question_text, style="bold yellow"),
            title=f"[cyan] {resolved_project} [/cyan]  [dim]{turns_label}[/dim]",
            border_style="dim blue",
            padding=(0, 1),
        ))

    # ── API key guard ─────────────────────────────────────────────────────────
    api_key = config["openai"]["api_key"]
    if api_key.startswith("sk-your-key"):
        console.print(f"\n[red]Error: API key not configured.[/red]")
        console.print(f"   Edit: [bold]{CONFIG_FILE}[/bold]")
        raise typer.Exit(1)

    # ── OpenAI call ───────────────────────────────────────────────────────────
    try:
        from openai import OpenAI  # lazy import — faster startup when using --list/--history
        client = OpenAI(api_key=api_key)
    except ImportError:
        console.print("[red]Error: openai package not installed.[/red]")
        console.print("   Run: [bold]pip install openai[/bold]")
        raise typer.Exit(1)

    stream_enabled = config["defaults"]["stream"] and not no_stream

    try:
        full_response = ""
        console.print()

        if stream_enabled:
            # ── Streaming: render markdown live as tokens arrive ───────────
            stream = client.chat.completions.create(
                model       = config["openai"]["model"],
                max_tokens  = config["openai"]["max_tokens"],
                temperature = config["openai"]["temperature"],
                messages    = messages,
                stream      = True,
            )
            render_md = config["display"]["markdown"]
            with console.status("[dim]thinking...[/dim]", spinner="dots"):
                for chunk in stream:
                    delta = chunk.choices[0].delta.content or ""
                    full_response += delta
            if render_md:
                console.print(Markdown(full_response))
            else:
                console.print(full_response)
            console.print()

        else:
            # ── Non-streaming: render with rich Markdown ───────────────────
            response = client.chat.completions.create(
                model       = config["openai"]["model"],
                max_tokens  = config["openai"]["max_tokens"],
                temperature = config["openai"]["temperature"],
                messages    = messages,
            )
            full_response = response.choices[0].message.content
            if config["display"]["markdown"]:
                console.print(Markdown(full_response))
            else:
                console.print(full_response)

        console.print()

    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
        if full_response:
            console.print("[dim](Partial response not saved to history)[/dim]")
        raise typer.Exit(0)

    except Exception as e:
        console.print(f"\n[red]API Error:[/red] {e}")
        raise typer.Exit(1)

    # ── Save to history ───────────────────────────────────────────────────────
    ts = datetime.now().strftime("%Y-%m-%d %H:%M") if config["display"]["show_timestamp"] else ""
    conv_history.append({"role": "user",      "content": question_text,  "timestamp": ts})
    conv_history.append({"role": "assistant", "content": full_response,  "timestamp": ts})
    save_history(resolved_project, conv_history, limit=config["defaults"]["history_limit"])


if __name__ == "__main__":
    app()
