#!/usr/bin/env python3
from __future__ import annotations
"""
content_agent.py — Anthropic courses reposunu klonlar, deep-translator ile
EN→TR çevirir ve src/content/courses/*.json dosyalarına yazar.

Kullanım:
  python content_agent.py              # tüm kurslar
  python content_agent.py --course api-temelleri
  python content_agent.py --dry-run
  python content_agent.py --estimate
  python content_agent.py --clean      # önbelleği sil, yeniden çek
"""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import markdown as md_lib
import nbformat
from deep_translator import GoogleTranslator
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

load_dotenv(dotenv_path=Path(__file__).parent.parent / "anthropic-tr" / ".env")

console = Console()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
REPO_CACHE = SCRIPT_DIR / "_repo_cache"
REPO_URL = "https://github.com/anthropics/courses.git"
PROJECT_ROOT = SCRIPT_DIR.parent / "anthropic-tr"
CONTENT_DIR = PROJECT_ROOT / "src" / "content" / "courses"

COURSE_MAP: dict[str, str] = {
    "api-temelleri": "anthropic_api_fundamentals",
    "prompt-muhendisligi": "prompt_engineering_interactive_tutorial",
    "gercek-dunya-prompting": "real_world_prompting",
    "prompt-degerlendirme": "prompt_evaluations",
    "arac-kullanimi": "tool_use",
}

translator = GoogleTranslator(source="en", target="tr")

# ---------------------------------------------------------------------------
# Code block protection (çeviri öncesi kodları sakla, sonra geri koy)
# ---------------------------------------------------------------------------
_PLACEHOLDER = "XXCODEBLOCKXX{n}XX"


def _protect(text: str) -> tuple[str, dict[str, str]]:
    store: dict[str, str] = {}
    n = [0]

    def _sub(m: re.Match) -> str:
        key = _PLACEHOLDER.format(n=n[0])
        store[key] = m.group(0)
        n[0] += 1
        return key

    # Fenced code blocks (``` ... ```)
    protected = re.sub(r"```[\s\S]*?```", _sub, text)
    # Inline code (` ... `)
    protected = re.sub(r"`[^`\n]+`", _sub, protected)
    return protected, store


def _restore(text: str, store: dict[str, str]) -> str:
    for key, val in store.items():
        text = text.replace(key, val)
    return text


# ---------------------------------------------------------------------------
# Translation
# ---------------------------------------------------------------------------
_MAX_CHARS = 4500  # Google Translate limit per request


def translate_text(text: str) -> str:
    """EN → TR çeviri. Kod bloklarını korur, uzun metinleri böler."""
    if not text.strip():
        return text

    protected, store = _protect(text)

    # Çok uzunsa parçalara böl
    if len(protected) > _MAX_CHARS:
        paragraphs = protected.split("\n\n")
        translated_parts: list[str] = []
        chunk = ""
        for para in paragraphs:
            if len(chunk) + len(para) + 2 > _MAX_CHARS:
                if chunk:
                    try:
                        tr = translator.translate(chunk)
                        translated_parts.append(tr if tr is not None else chunk)
                        time.sleep(0.3)
                    except Exception:
                        translated_parts.append(chunk)
                    chunk = para
                else:
                    # Tek paragraf zaten çok uzun — olduğu gibi bırak
                    translated_parts.append(para)
            else:
                chunk = f"{chunk}\n\n{para}".strip() if chunk else para
        if chunk:
            try:
                tr = translator.translate(chunk)
                translated_parts.append(tr if tr is not None else chunk)
                time.sleep(0.3)
            except Exception:
                translated_parts.append(chunk)
        result = "\n\n".join(translated_parts)
    else:
        try:
            tr = translator.translate(protected)
            result = tr if tr is not None else protected
            time.sleep(0.2)  # rate-limit önlemi
        except Exception as exc:
            console.print(f"[yellow]Çeviri atlandı:[/yellow] {exc}")
            result = protected

    return _restore(result, store)


def md_to_html(markdown_text: str) -> str:
    return md_lib.markdown(
        markdown_text,
        extensions=["fenced_code", "tables", "nl2br"],
    )


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------
def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def ensure_repo(clean: bool = False) -> None:
    if clean and REPO_CACHE.exists():
        import shutil
        console.print("[yellow]Önbellek siliniyor...[/yellow]")
        shutil.rmtree(REPO_CACHE)

    if not REPO_CACHE.exists():
        console.print(f"[cyan]Repo klonlanıyor:[/cyan] {REPO_URL}")
        result = _run(["git", "clone", "--depth=1", REPO_URL, str(REPO_CACHE)])
        if result.returncode != 0:
            console.print(f"[red]Hata:[/red] {result.stderr}")
            sys.exit(1)
        console.print("[green]Klonlama tamamlandı.[/green]")
    else:
        console.print("[cyan]Repo güncelleniyor...[/cyan]")
        result = _run(["git", "pull", "--depth=1", "origin", "master"], cwd=REPO_CACHE)
        if result.returncode != 0:
            _run(["git", "pull", "--depth=1", "origin", "main"], cwd=REPO_CACHE)
        console.print("[green]Güncelleme tamamlandı.[/green]")


# ---------------------------------------------------------------------------
# Notebook → Chapters
# ---------------------------------------------------------------------------
def _nb_title(nb: nbformat.NotebookNode, filename: str) -> str:
    for cell in nb.cells:
        if cell.cell_type == "markdown":
            for line in (cell.source or '').splitlines():
                if line.startswith("# "):
                    return line[2:].strip()
    stem = Path(filename).stem
    return re.sub(r"[_\-]+", " ", stem).title()


def _slug(filename: str, idx: int) -> str:
    stem = Path(filename).stem.lower()
    return re.sub(r"[^a-z0-9]+", "-", stem).strip("-") or f"bolum-{idx + 1}"


def process_notebook(nb_path: Path, idx: int) -> dict:
    nb = nbformat.read(str(nb_path), as_version=4)
    title_en = _nb_title(nb, nb_path.name)
    title_tr = translate_text(title_en)
    slug = _slug(nb_path.name, idx)

    blocks_en: list[dict] = []
    blocks_tr: list[dict] = []

    for cell in nb.cells:
        src = (cell.source or '').strip()
        if not src:
            continue
        if cell.cell_type == "markdown":
            html_en = md_to_html(src)
            html_tr = md_to_html(translate_text(src))
            blocks_en.append({"type": "html", "content": html_en})
            blocks_tr.append({"type": "html", "content": html_tr})
        elif cell.cell_type == "code":
            blocks_en.append({"type": "code", "content": src})
            blocks_tr.append({"type": "code", "content": src})  # kod değişmez

    return {
        "slug": slug,
        "order_index": idx + 1,
        "title": title_en,
        "title_tr": title_tr,
        "blocks_en": blocks_en,
        "blocks_tr": blocks_tr,
    }


def extract_chapters(course_dir: Path) -> list[dict]:
    notebooks = sorted([
        nb for nb in course_dir.glob("**/*.ipynb")
        if ".ipynb_checkpoints" not in str(nb) and "__pycache__" not in str(nb)
    ])
    chapters = []
    for idx, nb_path in enumerate(notebooks):
        try:
            console.print(f"  [dim]→[/dim] {nb_path.name}")
            chapter = process_notebook(nb_path, idx)
            chapters.append(chapter)
        except Exception as exc:
            console.print(f"  [yellow]Atlandı:[/yellow] {nb_path.name} — {exc}")
    return chapters


# ---------------------------------------------------------------------------
# JSON güncelleme
# ---------------------------------------------------------------------------
def sync_course(slug: str, folder: str, dry_run: bool = False) -> bool:
    course_dir = REPO_CACHE / folder
    if not course_dir.exists():
        console.print(f"[red]Klasör yok:[/red] {course_dir}")
        return False

    json_path = CONTENT_DIR / f"{slug}.json"
    if not json_path.exists():
        console.print(f"[red]JSON yok:[/red] {json_path}")
        return False

    with open(json_path, encoding="utf-8") as f:
        existing = json.load(f)

    console.print(f"\n[bold cyan]{slug}[/bold cyan] işleniyor...")
    chapters = extract_chapters(course_dir)

    if not chapters:
        console.print(f"[yellow]Notebook bulunamadı:[/yellow] {course_dir}")
        return False

    if dry_run:
        console.print(f"[dim]DRY-RUN:[/dim] {len(chapters)} bölüm bulundu, yazılmadı.")
        return True

    updated = {**existing, "chapters": chapters, "last_synced_at": datetime.now(timezone.utc).isoformat()}
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(updated, f, ensure_ascii=False, indent=2)
        f.write("\n")

    console.print(f"[green]✓[/green] {len(chapters)} bölüm → [dim]{json_path.name}[/dim]")
    return True


# ---------------------------------------------------------------------------
# Estimate / Dry-run
# ---------------------------------------------------------------------------
def estimate_summary(courses: list[str]) -> None:
    table = Table(title="Tahmin", show_lines=True)
    table.add_column("Kurs", style="cyan")
    table.add_column("Notebook", justify="right")
    table.add_column("MD Hücre", justify="right")
    table.add_column("Kod Hücre", justify="right")
    t_nb = t_md = t_code = 0
    for slug in courses:
        cd = REPO_CACHE / COURSE_MAP[slug]
        if not cd.exists():
            table.add_row(slug, "[red]yok[/red]", "-", "-")
            continue
        nbs = [nb for nb in cd.glob("**/*.ipynb") if ".ipynb_checkpoints" not in str(nb)]
        md_c = code_c = 0
        for nb_path in nbs:
            try:
                nb = nbformat.read(str(nb_path), as_version=4)
                for cell in nb.cells:
                    if cell.cell_type == "markdown": md_c += 1
                    elif cell.cell_type == "code": code_c += 1
            except Exception:
                pass
        table.add_row(slug, str(len(nbs)), str(md_c), str(code_c))
        t_nb += len(nbs); t_md += md_c; t_code += code_c
    table.add_section()
    table.add_row("[bold]TOPLAM[/bold]", str(t_nb), str(t_md), str(t_code))
    console.print(table)


def dry_run_summary(courses: list[str]) -> None:
    table = Table(title="Dry-run", show_lines=True)
    table.add_column("Kurs", style="cyan")
    table.add_column("Klasör", style="dim")
    table.add_column("Notebook", justify="right")
    for slug in courses:
        cd = REPO_CACHE / COURSE_MAP[slug]
        if not cd.exists():
            table.add_row(slug, COURSE_MAP[slug], "[red]yok[/red]")
            continue
        n = len([nb for nb in cd.glob("**/*.ipynb") if ".ipynb_checkpoints" not in str(nb)])
        table.add_row(slug, COURSE_MAP[slug], str(n))
    console.print(table)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--course", choices=list(COURSE_MAP.keys()))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--estimate", action="store_true")
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    console.rule("[bold cyan]Anthropic TR — Content Agent[/bold cyan]")
    ensure_repo(clean=args.clean)

    target = [args.course] if args.course else list(COURSE_MAP.keys())

    if args.estimate:
        estimate_summary(target)
        return
    if args.dry_run:
        dry_run_summary(target)
        return

    if not CONTENT_DIR.exists():
        console.print(f"[red]İçerik dizini yok:[/red] {CONTENT_DIR}")
        sys.exit(1)

    ok = sum(sync_course(slug, COURSE_MAP[slug]) for slug in target)
    console.rule()
    console.print(f"[bold green]{ok}/{len(target)}[/bold green] kurs tamamlandı.")


if __name__ == "__main__":
    main()
