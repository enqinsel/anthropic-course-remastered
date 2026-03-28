#!/usr/bin/env python3
"""
content_agent.py — Anthropic courses repo'sundan içerik çeker ve
src/content/courses/*.json dosyalarına aktarır.

Kullanım:
  python content_agent.py              # tüm kurslar
  python content_agent.py --course api-temelleri
  python content_agent.py --dry-run
  python content_agent.py --clean      # önbelleği sil, yeniden çek
  python content_agent.py --estimate   # hücre sayısını göster
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import nbformat
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

load_dotenv()

console = Console()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
REPO_CACHE = SCRIPT_DIR / "_repo_cache"
REPO_URL = "https://github.com/anthropics/courses.git"

# anthropic-tr project root (one level up from scripts/)
PROJECT_ROOT = SCRIPT_DIR.parent / "anthropic-tr"
CONTENT_DIR = PROJECT_ROOT / "src" / "content" / "courses"

# ---------------------------------------------------------------------------
# Kurs → GitHub klasör eşlemesi
# ---------------------------------------------------------------------------
COURSE_MAP: dict[str, str] = {
    "api-temelleri": "anthropic_api_fundamentals",
    "prompt-muhendisligi": "prompt_engineering_interactive_tutorial",
    "gercek-dunya-prompting": "real_world_prompting",
    "prompt-degerlendirme": "prompt_evaluations",
    "arac-kullanimi": "tool_use",
}


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------
def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def ensure_repo(clean: bool = False) -> None:
    """Repo yoksa klonla, varsa güncelle."""
    if clean and REPO_CACHE.exists():
        console.print("[yellow]Önbellek siliniyor...[/yellow]")
        import shutil
        shutil.rmtree(REPO_CACHE)

    if not REPO_CACHE.exists():
        console.print(f"[cyan]Repo klonlanıyor:[/cyan] {REPO_URL}")
        result = _run(["git", "clone", "--depth=1", REPO_URL, str(REPO_CACHE)])
        if result.returncode != 0:
            console.print(f"[red]Klonlama hatası:[/red] {result.stderr}")
            sys.exit(1)
        console.print("[green]Klonlama tamamlandı.[/green]")
    else:
        console.print("[cyan]Repo güncelleniyor (git pull)...[/cyan]")
        result = _run(["git", "pull", "--depth=1", "origin", "master"], cwd=REPO_CACHE)
        if result.returncode != 0:
            console.print(f"[yellow]git pull uyarısı:[/yellow] {result.stderr.strip()}")
        else:
            console.print("[green]Güncelleme tamamlandı.[/green]")


# ---------------------------------------------------------------------------
# Notebook helpers
# ---------------------------------------------------------------------------
def _notebook_title(nb: nbformat.NotebookNode, filename: str) -> str:
    """Notebook'taki ilk H1 başlığını döndür, yoksa dosya adını kullan."""
    for cell in nb.cells:
        if cell.cell_type == "markdown":
            for line in cell.source.splitlines():
                if line.startswith("# "):
                    return line[2:].strip()
    # Dosya adından temizle: "01_introduction.ipynb" → "01 introduction"
    name = Path(filename).stem
    name = re.sub(r"[_\-]+", " ", name)
    return name.title()


def _make_slug(filename: str, index: int) -> str:
    """Dosya adından URL-dostu slug üret."""
    stem = Path(filename).stem.lower()
    stem = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
    return stem or f"bolum-{index + 1}"


def extract_chapters(course_dir: Path) -> list[dict]:
    """Klasördeki .ipynb dosyalarını sıralı chapter listesine dönüştür."""
    notebooks = sorted(course_dir.glob("**/*.ipynb"))
    # __pycache__ veya .ipynb_checkpoints içindekiler hariç
    notebooks = [
        nb for nb in notebooks
        if ".ipynb_checkpoints" not in str(nb) and "__pycache__" not in str(nb)
    ]

    chapters = []
    for idx, nb_path in enumerate(notebooks):
        try:
            nb = nbformat.read(str(nb_path), as_version=4)
        except Exception as exc:
            console.print(f"[yellow]Atlandı ({nb_path.name}):[/yellow] {exc}")
            continue

        title = _notebook_title(nb, nb_path.name)
        slug = _make_slug(nb_path.name, idx)
        content_blocks: list[dict] = []

        for cell in nb.cells:
            source = cell.source.strip()
            if not source:
                continue
            if cell.cell_type == "markdown":
                content_blocks.append({"type": "markdown", "content": source})
            elif cell.cell_type == "code":
                content_blocks.append({"type": "code", "content": source})

        chapters.append({
            "title": title,
            "slug": slug,
            "order_index": idx + 1,
            "content_blocks": content_blocks,
        })

    return chapters


# ---------------------------------------------------------------------------
# JSON güncelleme
# ---------------------------------------------------------------------------
def load_existing(json_path: Path) -> dict:
    if json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def sync_course(slug: str, folder: str, dry_run: bool = False) -> bool:
    """Tek bir kursu senkronize et. Başarılıysa True döner."""
    course_dir = REPO_CACHE / folder
    if not course_dir.exists():
        console.print(f"[red]Klasör bulunamadı:[/red] {course_dir}")
        return False

    json_path = CONTENT_DIR / f"{slug}.json"
    existing = load_existing(json_path)

    if not existing:
        console.print(f"[red]JSON bulunamadı:[/red] {json_path}")
        return False

    chapters = extract_chapters(course_dir)
    if not chapters:
        console.print(f"[yellow]Hiç notebook bulunamadı:[/yellow] {course_dir}")
        return False

    updated = {
        **existing,
        "chapters": chapters,
        "last_synced_at": datetime.now(timezone.utc).isoformat(),
    }

    if dry_run:
        console.print(
            f"[dim]DRY-RUN[/dim] [bold]{slug}[/bold]: "
            f"{len(chapters)} bölüm bulundu, yazılmadı."
        )
        return True

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(updated, f, ensure_ascii=False, indent=2)
        f.write("\n")

    console.print(
        f"[green]✓[/green] [bold]{slug}[/bold]: "
        f"{len(chapters)} bölüm → {json_path.name}"
    )
    return True


# ---------------------------------------------------------------------------
# Dry-run summary table
# ---------------------------------------------------------------------------
def estimate_summary(courses: list[str]) -> None:
    """Her kurs için notebook ve toplam hücre sayısını göster."""
    table = Table(title="Tahmin: Notebook ve Hücre Sayıları", show_lines=True)
    table.add_column("Kurs", style="cyan")
    table.add_column("Notebook", justify="right")
    table.add_column("Markdown Hücresi", justify="right")
    table.add_column("Kod Hücresi", justify="right")

    total_nb = total_md = total_code = 0
    for slug in courses:
        folder = COURSE_MAP[slug]
        course_dir = REPO_CACHE / folder
        if not course_dir.exists():
            table.add_row(slug, "[red]bulunamadı[/red]", "-", "-")
            continue
        notebooks = sorted([
            nb for nb in course_dir.glob("**/*.ipynb")
            if ".ipynb_checkpoints" not in str(nb)
        ])
        nb_count = len(notebooks)
        md_count = code_count = 0
        for nb_path in notebooks:
            try:
                nb = nbformat.read(str(nb_path), as_version=4)
                for cell in nb.cells:
                    if cell.cell_type == "markdown":
                        md_count += 1
                    elif cell.cell_type == "code":
                        code_count += 1
            except Exception:
                pass
        table.add_row(slug, str(nb_count), str(md_count), str(code_count))
        total_nb += nb_count
        total_md += md_count
        total_code += code_count

    table.add_section()
    table.add_row("[bold]TOPLAM[/bold]", str(total_nb), str(total_md), str(total_code))
    console.print(table)


def dry_run_summary(courses: list[str]) -> None:
    table = Table(title="Dry-run: Bulunan Notebook'lar", show_lines=True)
    table.add_column("Kurs", style="cyan")
    table.add_column("GitHub Klasörü", style="dim")
    table.add_column("Notebook Sayısı", justify="right")

    for slug in courses:
        folder = COURSE_MAP[slug]
        course_dir = REPO_CACHE / folder
        if not course_dir.exists():
            table.add_row(slug, folder, "[red]bulunamadı[/red]")
            continue
        nb_count = len([
            nb for nb in course_dir.glob("**/*.ipynb")
            if ".ipynb_checkpoints" not in str(nb)
        ])
        table.add_row(slug, folder, str(nb_count))

    console.print(table)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Anthropic courses → JSON senkronizasyonu")
    parser.add_argument(
        "--course",
        choices=list(COURSE_MAP.keys()),
        help="Sadece belirtilen kursu senkronize et",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Değişiklik yapmadan ne yapılacağını göster",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Repo önbelleğini silip yeniden klonla",
    )
    parser.add_argument(
        "--estimate",
        action="store_true",
        help="Notebook ve hücre sayısını göster (değişiklik yok)",
    )
    args = parser.parse_args()

    console.rule("[bold cyan]Anthropic TR — Content Agent[/bold cyan]")

    # Repo hazırlığı
    ensure_repo(clean=args.clean)

    # Senkronize edilecek kursları belirle
    target_courses = [args.course] if args.course else list(COURSE_MAP.keys())

    if args.estimate:
        estimate_summary(target_courses)
        return

    if args.dry_run:
        dry_run_summary(target_courses)
        return

    # İçerik dizini var mı kontrol et
    if not CONTENT_DIR.exists():
        console.print(f"[red]İçerik dizini bulunamadı:[/red] {CONTENT_DIR}")
        console.print("anthropic-tr/src/content/courses/ klasörünün mevcut olduğundan emin olun.")
        sys.exit(1)

    success_count = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Senkronize ediliyor...", total=len(target_courses))
        for slug in target_courses:
            folder = COURSE_MAP[slug]
            progress.update(task, description=f"[cyan]{slug}[/cyan] işleniyor...")
            ok = sync_course(slug, folder, dry_run=False)
            if ok:
                success_count += 1
            progress.advance(task)

    console.rule()
    console.print(
        f"[bold green]{success_count}/{len(target_courses)}[/bold green] kurs senkronize edildi."
    )
    if success_count < len(target_courses):
        console.print("[yellow]Bazı kurslar atlandı — yukarıdaki uyarıları inceleyin.[/yellow]")


if __name__ == "__main__":
    main()
