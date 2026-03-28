#!/usr/bin/env python3
from __future__ import annotations
"""
content_agent.py — Anthropic courses reposunu senkronize eder, notebook
içeriğini güvenli şekilde ayrıştırır, yerel medya dosyalarına taşır ve
`anthropic-tr/src/content/courses/*.json` çıktısını yeniden üretir.

Bu sürümde:
- kaynak gerçekliği notebook'lardır
- kod blokları ve inline code yapısı korunur
- notebook attachment / relative media referansları public altına taşınır
- mevcut Türkçe JSON sadece güvenli seed / cleanup kaynağı olarak kullanılır
"""

import argparse
import base64
import html
import json
import mimetypes
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote, unquote

import markdown as md_lib
import nbformat
from rich.console import Console
from rich.table import Table

console = Console()


@dataclass(frozen=True)
class CourseConfig:
    folder: str
    notebook_root: str = ""


SCRIPT_DIR = Path(__file__).parent
REPO_CACHE = SCRIPT_DIR / "_repo_cache"
REPO_URL = "https://github.com/anthropics/courses.git"
PROJECT_ROOT = SCRIPT_DIR.parent / "anthropic-tr"
CONTENT_DIR = PROJECT_ROOT / "src" / "content" / "courses"
PUBLIC_MEDIA_DIR = PROJECT_ROOT / "public" / "course-media"
GITHUB_BRANCH = "master"

COURSE_MAP: dict[str, CourseConfig] = {
    "api-temelleri": CourseConfig(folder="anthropic_api_fundamentals"),
    "prompt-muhendisligi": CourseConfig(
        folder="prompt_engineering_interactive_tutorial",
        notebook_root="Anthropic 1P",
    ),
    "gercek-dunya-prompting": CourseConfig(folder="real_world_prompting"),
    "prompt-degerlendirme": CourseConfig(folder="prompt_evaluations"),
    "arac-kullanimi": CourseConfig(folder="tool_use"),
}

SUPPORTED_MEDIA_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
}

ATTACHMENT_PREFIXES = ("attachment:", "ek:")
PLACEHOLDER_FMT = "XXCODEBLOCKXX{n}XX"
PLACEHOLDER_RE = re.compile(r"XXCODEBLOK(?:C?K)?XX(\d+)XX", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
PARAGRAPH_RE = re.compile(r"<p>(.*?)</p>", re.IGNORECASE | re.DOTALL)
SRC_ATTR_RE = re.compile(r'((?:src|href)=["\'])([^"\']+)(["\'])', re.IGNORECASE)
IMG_MARKDOWN_RE = re.compile(r"(!?\[[^\]]*\]\()([^)]+)(\))")
HTML_IMG_RE = re.compile(r'(<img\b[^>]*\bsrc=["\'])([^"\']+)(["\'])', re.IGNORECASE)
FENCED_CODE_RE = re.compile(r"```([^\n`]*)\n([\s\S]*?)```")
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")

TAG_REPLACEMENTS = {
    "<detaylar>": "<details>",
    "</detaylar>": "</details>",
    "<özet>": "<summary>",
    "</özet>": "</summary>",
    "<ozet>": "<summary>",
    "</ozet>": "</summary>",
    "<başlık>": "<summary>",
    "</başlık>": "</summary>",
    "<baslik>": "<summary>",
    "</baslik>": "</summary>",
}

TRANSLATION_REPLACEMENTS: list[tuple[str, str]] = [
    (r"\bAntropik\b", "Anthropic"),
    (r"\bANTROPIK\b", "Anthropic"),
    (r"\bYüksek Lisans'lar\b", "LLM'ler"),
    (r"\bYüksek Lisanslar\b", "LLM'ler"),
    (r"\bYüksek Lisans\b", "LLM"),
    (r"\bhızlı mühendislik\b", "prompt mühendisliği"),
    (r"\bHızlı mühendislik\b", "Prompt mühendisliği"),
    (r"\bhızlı değerlendirme(ler)?\b", r"prompt değerlendirme\1"),
    (r"\bHızlı değerlendirme(ler)?\b", r"Prompt değerlendirme\1"),
    (r"\bbilgi istemi oluşturucu\b", "prompt oluşturucu"),
    (r"\bBilgi istemi oluşturucu\b", "Prompt oluşturucu"),
    (r"\bbilgi istemine\b", "prompt'a"),
    (r"\bBilgi istemine\b", "Prompt'a"),
    (r"\bbilgi isteminde\b", "prompt'ta"),
    (r"\bBilgi isteminde\b", "Prompt'ta"),
    (r"\bbilgi isteminin\b", "prompt'un"),
    (r"\bBilgi isteminin\b", "Prompt'un"),
    (r"\bbilgi istemini\b", "prompt'u"),
    (r"\bBilgi istemini\b", "Prompt'u"),
    (r"\bbilgi istemleri\b", "prompt'lar"),
    (r"\bBilgi istemleri\b", "Prompt'lar"),
    (r"\bbilgi istemi\b", "prompt"),
    (r"\bBilgi istemi\b", "Prompt"),
    (r"\bkomut istemimize\b", "prompt'umuza"),
    (r"\bKomut istemimize\b", "Prompt'umuza"),
    (r"\bkomut istemimizin\b", "prompt'umuzun"),
    (r"\bKomut istemimizin\b", "Prompt'umuzun"),
    (r"\bkomut isteminizde\b", "prompt'unuzda"),
    (r"\bKomut isteminizde\b", "Prompt'unuzda"),
    (r"\bkomut istemine\b", "prompt'a"),
    (r"\bKomut istemine\b", "Prompt'a"),
    (r"\bkomut isteminde\b", "prompt'ta"),
    (r"\bKomut isteminde\b", "Prompt'ta"),
    (r"\bkomut istemini\b", "prompt'u"),
    (r"\bKomut istemini\b", "Prompt'u"),
    (r"\bkomut istemi\b", "prompt"),
    (r"\bKomut istemi\b", "Prompt"),
    (r"\balet kullanımımızı\b", "araç kullanımını"),
    (r"\bAlet kullanımımızı\b", "Araç kullanımını"),
    (r"\balet kullanımı\b", "araç kullanımı"),
    (r"\bAlet kullanımı\b", "Araç kullanımı"),
    (r"\bbir araç araçlar\b", "birden fazla araç"),
    (r"\bBir araç araçlar\b", "Birden fazla araç"),
    (r"Şimdi araç kullanımını başka bir düzeye taşıyacağız!", "Şimdi araç kullanımını bir seviye daha ileri taşıyacağız!"),
    (r"Şimdi alet kullanımımızı başka bir düzeye taşıyacağız!", "Şimdi araç kullanımını bir seviye daha ileri taşıyacağız!"),
    (r"Üçüncü bir komut istemine ekleme", "Üçüncü bir prompt ekleme"),
    (r"başka bir komut istemine aktaralım", "başka bir prompt'a aktaralım"),
    (r"Claude komut istemine girmeye hazır", "Claude prompt'a eklenmeye hazır"),
    (r"\bUstalar Turnuvası\b", "Masters Turnuvası"),
    (r"\bUzun bağlamlı ipucu\b", "Uzun bağlam ipuçları"),
    (r"\bBelgelere kadar\b", "Önce belgeler"),
    (r"\bdeğişimler\b", "etkileşimler"),
    (r"\bİngilizce orijinal ifadeyi ve İspanyolca, Fransızca, Japonca ve Arapça olarak çevrilmiş ifadeyi\b", "İngilizce özgün ifadeyi ve İspanyolca, Fransızca, Japonca ve Arapça çeviri karşılıklarını"),
    (r"\bher istekte istemine ileteceğimiz\b", "her istekte prompt'a ileteceğimiz"),
    (r"\bhavuzu\b", "repoyu"),
    (r"\bHavuzu\b", "Repoyu"),
    (r"\bhavuz\b", "repo"),
    (r"\bHavuz\b", "Repo"),
    (r"\bnot defteri\b", "notebook"),
    (r"\bNot defteri\b", "Notebook"),
    (r"\bçalışma tezgahı\b", "Workbench"),
    (r"\bÇalışma tezgahı\b", "Workbench"),
    (r"\btakım kodunu\b", "araç kodunu"),
    (r"\bTakım kodunu\b", "Araç kodunu"),
    (r"\btakım\b", "araç"),
    (r"\bTakım\b", "Araç"),
]


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def ensure_repo(clean: bool = False) -> None:
    if clean and REPO_CACHE.exists():
        console.print("[yellow]Önbellek siliniyor...[/yellow]")
        shutil.rmtree(REPO_CACHE)

    if not REPO_CACHE.exists():
        console.print(f"[cyan]Repo klonlanıyor:[/cyan] {REPO_URL}")
        result = _run(["git", "clone", "--depth=1", REPO_URL, str(REPO_CACHE)])
        if result.returncode != 0:
            console.print(f"[red]Hata:[/red] {result.stderr}")
            sys.exit(1)
        console.print("[green]Klonlama tamamlandı.[/green]")
        return

    console.print("[cyan]Repo güncelleniyor...[/cyan]")
    result = _run(["git", "pull", "--depth=1", "origin", GITHUB_BRANCH], cwd=REPO_CACHE)
    if result.returncode != 0:
        fallback = _run(["git", "pull", "--depth=1", "origin", "main"], cwd=REPO_CACHE)
        if fallback.returncode != 0:
            console.print(f"[yellow]Güncelleme atlandı:[/yellow] {fallback.stderr.strip() or result.stderr.strip()}")
            return
    console.print("[green]Güncelleme tamamlandı.[/green]")


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def source_url_for_path(config: CourseConfig, relative_path: str | None = None) -> str:
    base_parts = [config.folder]
    if config.notebook_root:
        base_parts.append(config.notebook_root)
    if relative_path:
        base_parts.append(relative_path)
    joined = "/".join(quote(part, safe="/-_. ") for part in base_parts).replace(" ", "%20")
    return f"https://github.com/anthropics/courses/tree/{GITHUB_BRANCH}/{joined}"


def html_escape(text: str) -> str:
    return html.escape(text, quote=False)


def fence_to_html(language: str, code: str) -> str:
    lang = slugify(language) if language else ""
    class_attr = f' class="language-{lang}"' if lang else ""
    return f"<pre><code{class_attr}>{html_escape(code.rstrip())}\n</code></pre>"


def inline_code_to_html(code: str) -> str:
    return f"<code>{html_escape(code)}</code>"


def placeholder_html_map(markdown_text: str) -> dict[int, str]:
    replacements: dict[int, str] = {}
    counter = 0

    def replace_fence(match: re.Match[str]) -> str:
        nonlocal counter
        language = (match.group(1) or "").strip()
        code = match.group(2)
        replacements[counter] = fence_to_html(language, code)
        token = PLACEHOLDER_FMT.format(n=counter)
        counter += 1
        return token

    protected = FENCED_CODE_RE.sub(replace_fence, markdown_text)

    def replace_inline(match: re.Match[str]) -> str:
        nonlocal counter
        replacements[counter] = inline_code_to_html(match.group(1))
        token = PLACEHOLDER_FMT.format(n=counter)
        counter += 1
        return token

    INLINE_CODE_RE.sub(replace_inline, protected)
    return replacements


def normalize_markdown(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    output: list[str] = []
    in_fence = False

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```"):
            if output and output[-1].strip() and not in_fence:
                output.append("")
            output.append(line)
            in_fence = not in_fence
            continue

        if in_fence:
            output.append(line)
            continue

        starts_list = bool(re.match(r"(?:[*+-]|\d+\.)\s+", stripped))
        starts_quote = stripped.startswith(">")
        if (starts_list or starts_quote) and output and output[-1].strip():
            previous = output[-1].lstrip()
            previous_is_list = bool(re.match(r"(?:[*+-]|\d+\.)\s+", previous))
            if not previous_is_list and not previous.startswith(">"):
                output.append("")
        output.append(line)

    return "\n".join(output).strip()


def markdown_to_html(markdown_text: str) -> str:
    return md_lib.markdown(
        normalize_markdown(markdown_text),
        extensions=[
            "fenced_code",
            "tables",
            "sane_lists",
            "md_in_html",
        ],
    )


def normalize_escaped_xml_literals(html_text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return f"&lt;{match.group(1)}&gt;"

    normalized = re.sub(r"\\<(/?[A-Za-z_][A-Za-z0-9_:-]*)>", replace, html_text)
    normalized = normalized.replace("\\&gt;", "&gt;").replace("\\&lt;", "&lt;")
    return normalized


def copy_course_media(course_slug: str, course_dir: Path) -> None:
    target_dir = PUBLIC_MEDIA_DIR / course_slug
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    for path in course_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_MEDIA_EXTENSIONS:
            continue
        destination = target_dir / path.relative_to(course_dir)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


def attachment_public_path(course_slug: str, chapter_slug: str, filename: str) -> str:
    return f"/course-media/{course_slug}/attachments/{chapter_slug}/{filename}"


def write_attachments(
    course_slug: str,
    chapter_slug: str,
    attachments: dict[str, dict[str, str]],
) -> dict[str, str]:
    attachment_paths: dict[str, str] = {}
    if not attachments:
        return attachment_paths

    base_dir = PUBLIC_MEDIA_DIR / course_slug / "attachments" / chapter_slug
    base_dir.mkdir(parents=True, exist_ok=True)

    for original_name, payloads in attachments.items():
        mime_type, encoded = next(iter(payloads.items()))
        extension = Path(original_name).suffix or mimetypes.guess_extension(mime_type) or ""
        filename = original_name if Path(original_name).suffix else f"{original_name}{extension}"
        destination = base_dir / filename
        destination.write_bytes(base64.b64decode(encoded))
        public_path = attachment_public_path(course_slug, chapter_slug, filename)
        attachment_paths[original_name] = public_path
        attachment_paths[filename] = public_path

    return attachment_paths


def candidate_public_paths_for_attachment(
    course_slug: str,
    attachment_name: str,
    nb_path: Path,
    course_dir: Path,
) -> list[str]:
    attachment_name = unquote(attachment_name)
    candidates = [
        nb_path.parent / attachment_name,
        nb_path.parent / "images" / attachment_name,
        nb_path.parent / "prompting_images" / attachment_name,
        course_dir / "images" / attachment_name,
        course_dir / "prompting_images" / attachment_name,
    ]

    public_paths: list[str] = []
    for candidate in candidates:
        if candidate.exists():
            rel = candidate.relative_to(course_dir)
            public_paths.append(f"/course-media/{course_slug}/{rel.as_posix()}")
    return public_paths


def rewrite_asset_url(
    url: str,
    course_slug: str,
    nb_path: Path,
    course_dir: Path,
    attachment_paths: dict[str, str],
) -> str:
    if not url:
        return url

    normalized = url.strip()
    lower = normalized.lower()
    if lower.startswith(("http://", "https://", "/", "#", "mailto:", "data:")):
        return normalized

    for prefix in ATTACHMENT_PREFIXES:
        if lower.startswith(prefix):
            name = normalized.split(":", 1)[1]
            if name in attachment_paths:
                return attachment_paths[name]
            fallback_paths = candidate_public_paths_for_attachment(
                course_slug=course_slug,
                attachment_name=name,
                nb_path=nb_path,
                course_dir=course_dir,
            )
            if fallback_paths:
                return fallback_paths[0]
            return normalized

    candidate = (nb_path.parent / unquote(normalized)).resolve()
    course_root = course_dir.resolve()
    try:
        relative = candidate.relative_to(course_root)
    except ValueError:
        return normalized

    if candidate.suffix.lower() not in SUPPORTED_MEDIA_EXTENSIONS:
        return normalized

    return f"/course-media/{course_slug}/{relative.as_posix()}"


def rewrite_markdown_media(
    markdown_text: str,
    course_slug: str,
    nb_path: Path,
    course_dir: Path,
    attachment_paths: dict[str, str],
) -> str:
    def replace_markdown(match: re.Match[str]) -> str:
        prefix, url, suffix = match.groups()
        rewritten = rewrite_asset_url(
            url=url,
            course_slug=course_slug,
            nb_path=nb_path,
            course_dir=course_dir,
            attachment_paths=attachment_paths,
        )
        return f"{prefix}{rewritten}{suffix}"

    rewritten = IMG_MARKDOWN_RE.sub(replace_markdown, markdown_text)

    def replace_html(match: re.Match[str]) -> str:
        prefix, url, suffix = match.groups()
        rewritten = rewrite_asset_url(
            url=url,
            course_slug=course_slug,
            nb_path=nb_path,
            course_dir=course_dir,
            attachment_paths=attachment_paths,
        )
        return f"{prefix}{rewritten}{suffix}"

    return HTML_IMG_RE.sub(replace_html, rewritten)


def normalize_html_for_match(value: str) -> str:
    compact = re.sub(r">\s+<", "><", value.strip())
    compact = re.sub(r"\s+", " ", compact)
    return html.unescape(compact).strip()


def cleanup_translation_plain_text(text: str) -> str:
    cleaned = text
    for pattern, replacement in TRANSLATION_REPLACEMENTS:
        cleaned = re.sub(pattern, replacement, cleaned)
    return cleaned.strip()


def cleanup_translation_html(html_text: str) -> str:
    cleaned = html_text
    for old_tag, new_tag in TAG_REPLACEMENTS.items():
        cleaned = cleaned.replace(old_tag, new_tag).replace(old_tag.upper(), new_tag)
    for pattern, replacement in TRANSLATION_REPLACEMENTS:
        cleaned = re.sub(pattern, replacement, cleaned)
    return normalize_escaped_xml_literals(cleaned)


def restore_placeholders(seed_html: str, code_map: dict[int, str]) -> str:
    restored = seed_html

    for index, fragment in code_map.items():
        token_variants = [
            f"XXCODEBLOCKXX{index}XX",
            f"XXCODEBLOKXX{index}XX",
        ]
        for token in token_variants:
            restored = re.sub(
                rf"<p>\s*{re.escape(token)}\s*</p>",
                lambda _: fragment,
                restored,
                flags=re.IGNORECASE,
            )
            restored = restored.replace(token, fragment)

    restored = re.sub(r"<p>\s*(<details>)\s*(?:<br\s*/?>\s*)*", r"\1", restored, flags=re.IGNORECASE)
    restored = re.sub(r"(?:<br\s*/?>\s*)*(</details>)\s*</p>", r"\1", restored, flags=re.IGNORECASE)
    restored = re.sub(r"<p>\s*(<summary>.*?</summary>)\s*</p>", r"\1", restored, flags=re.IGNORECASE | re.DOTALL)
    restored = re.sub(r"<p>\s*(</?details>)\s*</p>", r"\1", restored, flags=re.IGNORECASE)
    restored = re.sub(r"<p>\s*(<pre>[\s\S]*?</pre>)\s*</p>", r"\1", restored, flags=re.IGNORECASE)
    return restored


def rewrite_seed_media_urls(
    seed_html: str,
    course_slug: str,
    nb_path: Path,
    course_dir: Path,
    attachment_paths: dict[str, str],
) -> str:
    def replace(match: re.Match[str]) -> str:
        prefix, url, suffix = match.groups()
        rewritten = rewrite_asset_url(
            url=url,
            course_slug=course_slug,
            nb_path=nb_path,
            course_dir=course_dir,
            attachment_paths=attachment_paths,
        )
        return f"{prefix}{rewritten}{suffix}"

    return SRC_ATTR_RE.sub(replace, seed_html)


def extract_first_paragraph(html_text: str) -> str | None:
    for match in PARAGRAPH_RE.finditer(html_text):
        plain = html.unescape(TAG_RE.sub(" ", match.group(1)))
        plain = re.sub(r"\s+", " ", plain).strip()
        if plain:
            return plain
    return None


def is_primary_heading_html(html_text: str, title_en: str) -> bool:
    compact = normalize_html_for_match(html_text)
    heading = normalize_html_for_match(f"<h1>{html_escape(title_en)}</h1>")
    return compact == heading


def strip_leading_h1(html_text: str) -> str:
    return re.sub(r"^\s*<h1[^>]*>.*?</h1>\s*", "", html_text, count=1, flags=re.IGNORECASE | re.DOTALL).strip()


def notebook_cell_source(cell: nbformat.NotebookNode) -> str:
    source = cell.source or ""
    if isinstance(source, list):
        return "".join(source)
    return str(source)


def notebook_title(nb: nbformat.NotebookNode, filename: str) -> str:
    for cell in nb.cells:
        if cell.cell_type != "markdown":
            continue
        for raw_line in notebook_cell_source(cell).splitlines():
            if raw_line.startswith("# "):
                return raw_line[2:].strip()
    stem = Path(filename).stem
    return re.sub(r"[_\-]+", " ", stem).title()


def build_chapter_slug(relative_nb_path: Path, index: int) -> str:
    parent_slug = slugify(relative_nb_path.parent.name) if relative_nb_path.parent != Path(".") else ""
    stem_slug = slugify(relative_nb_path.stem)

    if stem_slug in {"lesson", "index"} and parent_slug:
        return parent_slug
    if parent_slug and parent_slug != stem_slug:
        return f"{parent_slug}-{stem_slug}"
    return stem_slug or f"bolum-{index + 1}"


def code_cell_language(cell: nbformat.NotebookNode, nb: nbformat.NotebookNode) -> str | None:
    metadata = getattr(cell, "metadata", {}) or {}
    vscode_meta = metadata.get("vscode", {})
    if isinstance(vscode_meta, dict) and vscode_meta.get("languageId"):
        return str(vscode_meta["languageId"])

    language_info = getattr(nb, "metadata", {}).get("language_info", {})
    if isinstance(language_info, dict) and language_info.get("name"):
        return str(language_info["name"])
    return None


def load_existing_course(slug: str) -> dict:
    json_path = CONTENT_DIR / f"{slug}.json"
    if not json_path.exists():
        return {}
    with open(json_path, encoding="utf-8") as handle:
        return json.load(handle)


def find_seed_chapter(existing_course: dict, slug: str, title_en: str) -> dict | None:
    chapters = existing_course.get("chapters", [])
    normalized_title = title_en.strip().lower()

    for chapter in chapters:
        if chapter.get("slug") == slug and str(chapter.get("title", "")).strip().lower() == normalized_title:
            return chapter
    for chapter in chapters:
        if str(chapter.get("title", "")).strip().lower() == normalized_title:
            return chapter
    for chapter in chapters:
        if chapter.get("slug") == slug:
            return chapter
    return None


def match_seed_html_block(seed_blocks_en: list[dict], seed_blocks_tr: list[dict], html_en: str) -> str | None:
    normalized_target = normalize_html_for_match(html_en)
    best_match: tuple[float, str] | None = None

    for index, block in enumerate(seed_blocks_en):
        if block.get("type") != "html":
            continue
        if index >= len(seed_blocks_tr):
            continue
        tr_block = seed_blocks_tr[index]
        if tr_block.get("type") != "html":
            continue

        normalized_seed = normalize_html_for_match(block.get("content", ""))
        if normalized_seed == normalized_target:
            return tr_block.get("content", "")

        score = SequenceMatcher(None, normalized_target, normalized_seed).ratio()
        if best_match is None or score > best_match[0]:
            best_match = (score, tr_block.get("content", ""))

    if best_match and best_match[0] >= 0.74:
        return best_match[1]
    return None


def cleaned_translation_html(
    html_en: str,
    markdown_source: str,
    seed_html: str | None,
    course_slug: str,
    nb_path: Path,
    course_dir: Path,
    attachment_paths: dict[str, str],
) -> str:
    if not seed_html:
        return html_en

    cleaned = cleanup_translation_html(seed_html)
    cleaned = rewrite_seed_media_urls(
        seed_html=cleaned,
        course_slug=course_slug,
        nb_path=nb_path,
        course_dir=course_dir,
        attachment_paths=attachment_paths,
    )
    cleaned = restore_placeholders(
        seed_html=cleaned,
        code_map=placeholder_html_map(markdown_source),
    )
    if PLACEHOLDER_RE.search(cleaned):
        return html_en
    return cleaned


def process_notebook(
    course_slug: str,
    config: CourseConfig,
    course_dir: Path,
    nb_path: Path,
    index: int,
    existing_course: dict,
) -> dict:
    nb = nbformat.read(str(nb_path), as_version=4)
    notebook_root = (course_dir / config.notebook_root) if config.notebook_root else course_dir
    relative_notebook_path = nb_path.relative_to(notebook_root)
    chapter_slug = build_chapter_slug(relative_notebook_path, index)
    title_en = notebook_title(nb, nb_path.name)

    seed_chapter = find_seed_chapter(existing_course=existing_course, slug=chapter_slug, title_en=title_en)
    seed_blocks_en = seed_chapter.get("blocks_en", []) if seed_chapter else []
    seed_blocks_tr = seed_chapter.get("blocks_tr", []) if seed_chapter else []

    title_tr = cleanup_translation_plain_text(seed_chapter.get("title_tr", title_en) if seed_chapter else title_en)

    blocks_en: list[dict] = []
    blocks_tr: list[dict] = []
    summary_en: str | None = None
    summary_tr: str | None = None

    for cell in nb.cells:
        source = notebook_cell_source(cell).strip()
        if not source:
            continue

        if cell.cell_type == "markdown":
            attachment_paths = write_attachments(
                course_slug=course_slug,
                chapter_slug=chapter_slug,
                attachments=getattr(cell, "attachments", {}) or {},
            )
            rewritten_markdown = rewrite_markdown_media(
                markdown_text=source,
                course_slug=course_slug,
                nb_path=nb_path,
                course_dir=course_dir,
                attachment_paths=attachment_paths,
            )
            html_en = normalize_escaped_xml_literals(markdown_to_html(rewritten_markdown))
            html_tr = cleaned_translation_html(
                html_en=html_en,
                markdown_source=rewritten_markdown,
                seed_html=match_seed_html_block(seed_blocks_en, seed_blocks_tr, html_en),
                course_slug=course_slug,
                nb_path=nb_path,
                course_dir=course_dir,
                attachment_paths=attachment_paths,
            )

            if is_primary_heading_html(html_en, title_en):
                continue

            if not blocks_en and html_en.lstrip().lower().startswith("<h1"):
                html_en = strip_leading_h1(html_en)
                html_tr = strip_leading_h1(html_tr)
                if not strip_leading_h1(html_en):
                    continue

            if summary_en is None:
                summary_en = extract_first_paragraph(html_en)
            if summary_tr is None:
                summary_tr = extract_first_paragraph(html_tr)

            blocks_en.append({"type": "html", "content": html_en})
            blocks_tr.append({"type": "html", "content": html_tr})
            continue

        if cell.cell_type == "code":
            language = code_cell_language(cell, nb)
            block = {
                "type": "code",
                "content": notebook_cell_source(cell).rstrip(),
            }
            if language:
                block["language"] = language
            blocks_en.append(block)
            blocks_tr.append(dict(block))

    return {
        "slug": chapter_slug,
        "order_index": index + 1,
        "title": title_en,
        "title_tr": title_tr,
        "summary_en": summary_en,
        "summary_tr": summary_tr or summary_en,
        "source_path": relative_notebook_path.as_posix(),
        "source_url": source_url_for_path(config=config, relative_path=relative_notebook_path.as_posix()),
        "blocks_en": blocks_en,
        "blocks_tr": blocks_tr,
    }


def extract_chapters(slug: str, config: CourseConfig, existing_course: dict) -> list[dict]:
    course_dir = REPO_CACHE / config.folder
    notebook_root = (course_dir / config.notebook_root) if config.notebook_root else course_dir
    if not notebook_root.exists():
        console.print(f"[red]Notebook kökü yok:[/red] {notebook_root}")
        return []

    copy_course_media(course_slug=slug, course_dir=course_dir)

    notebooks = sorted(
        [
            path
            for path in notebook_root.rglob("*.ipynb")
            if ".ipynb_checkpoints" not in str(path) and "__pycache__" not in str(path)
        ]
    )

    chapters: list[dict] = []
    for index, nb_path in enumerate(notebooks):
        console.print(f"  [dim]→[/dim] {nb_path.relative_to(course_dir)}")
        chapter = process_notebook(
            course_slug=slug,
            config=config,
            course_dir=course_dir,
            nb_path=nb_path,
            index=index,
            existing_course=existing_course,
        )
        chapters.append(chapter)
    return chapters


def sync_course(slug: str, config: CourseConfig, dry_run: bool = False) -> bool:
    course_dir = REPO_CACHE / config.folder
    if not course_dir.exists():
        console.print(f"[red]Klasör yok:[/red] {course_dir}")
        return False

    json_path = CONTENT_DIR / f"{slug}.json"
    if not json_path.exists():
        console.print(f"[red]JSON yok:[/red] {json_path}")
        return False

    existing = load_existing_course(slug)
    console.print(f"\n[bold cyan]{slug}[/bold cyan] işleniyor...")
    chapters = extract_chapters(slug=slug, config=config, existing_course=existing)

    if not chapters:
        console.print(f"[yellow]Notebook bulunamadı:[/yellow] {course_dir}")
        return False

    if dry_run:
        console.print(f"[dim]DRY-RUN:[/dim] {len(chapters)} bölüm bulundu, yazılmadı.")
        return True

    updated = {
        **existing,
        "course_id": existing.get("course_id", slug),
        "slug": slug,
        "source_url": source_url_for_path(config=config),
        "chapters": chapters,
        "last_synced_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(updated, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    console.print(f"[green]✓[/green] {len(chapters)} bölüm → [dim]{json_path.name}[/dim]")
    return True


def estimate_summary(courses: list[str]) -> None:
    table = Table(title="Tahmin", show_lines=True)
    table.add_column("Kurs", style="cyan")
    table.add_column("Notebook", justify="right")
    table.add_column("Görsel", justify="right")

    total_nb = 0
    total_media = 0

    for slug in courses:
        config = COURSE_MAP[slug]
        course_dir = REPO_CACHE / config.folder
        notebook_root = (course_dir / config.notebook_root) if config.notebook_root else course_dir
        notebooks = [
            path
            for path in notebook_root.rglob("*.ipynb")
            if ".ipynb_checkpoints" not in str(path)
        ]
        media_count = len(
            [
                path
                for path in course_dir.rglob("*")
                if path.is_file() and path.suffix.lower() in SUPPORTED_MEDIA_EXTENSIONS
            ]
        )
        table.add_row(slug, str(len(notebooks)), str(media_count))
        total_nb += len(notebooks)
        total_media += media_count

    table.add_section()
    table.add_row("[bold]TOPLAM[/bold]", str(total_nb), str(total_media))
    console.print(table)


def dry_run_summary(courses: list[str]) -> None:
    table = Table(title="Dry-run", show_lines=True)
    table.add_column("Kurs", style="cyan")
    table.add_column("Notebook kökü", style="dim")
    table.add_column("Notebook", justify="right")

    for slug in courses:
        config = COURSE_MAP[slug]
        course_dir = REPO_CACHE / config.folder
        notebook_root = (course_dir / config.notebook_root) if config.notebook_root else course_dir
        notebooks = [
            path
            for path in notebook_root.rglob("*.ipynb")
            if ".ipynb_checkpoints" not in str(path)
        ]
        table.add_row(slug, str(notebook_root.relative_to(REPO_CACHE)), str(len(notebooks)))

    console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--course", choices=list(COURSE_MAP.keys()))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--estimate", action="store_true")
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    console.rule("[bold cyan]Anthropic TR — Content Agent[/bold cyan]")
    ensure_repo(clean=args.clean)

    targets = [args.course] if args.course else list(COURSE_MAP.keys())

    if args.estimate:
        estimate_summary(targets)
        return
    if args.dry_run:
        dry_run_summary(targets)
        return

    if not CONTENT_DIR.exists():
        console.print(f"[red]İçerik dizini yok:[/red] {CONTENT_DIR}")
        sys.exit(1)

    ok = sum(sync_course(slug, COURSE_MAP[slug]) for slug in targets)
    console.rule()
    console.print(f"[bold green]{ok}/{len(targets)}[/bold green] kurs tamamlandı.")


if __name__ == "__main__":
    main()
