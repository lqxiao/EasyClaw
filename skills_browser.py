import os
import subprocess

import gradio as gr


LANGUAGE_BY_EXT = {
    ".css": "css",
    ".html": "html",
    ".js": "javascript",
    ".json": "json",
    ".md": "markdown",
    ".py": "python",
    ".sh": "shell",
    ".sql": "sql",
    ".ts": "typescript",
    ".txt": "markdown",
    ".xml": "html",
    ".yaml": "yaml",
    ".yml": "yaml",
}

TEXT_EXTENSIONS = set(LANGUAGE_BY_EXT) | {
    ".csv",
    ".log",
    ".ini",
    ".cfg",
}

MAX_PREVIEW_BYTES = 200_000


def open_folder(path):
    try:
        subprocess.Popen(["open", path])
        return None
    except Exception as exc:
        return f"Failed to open Finder: {exc}"


def skills_enabled_to_markdown(path):
    try:
        import xml.etree.ElementTree as ET

        with open(path, "r", encoding="utf-8") as handle:
            raw = handle.read()
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return f"```xml\n{raw}\n```"
        lines = []
        for skill in root.findall("skill"):
            name = (skill.findtext("name") or "").strip()
            desc = (skill.findtext("description") or "").strip()
            location = (skill.findtext("location") or "").strip()
            title = name or "unnamed-skill"
            details = []
            if desc:
                details.append(desc)
            if location:
                details.append(f"`{location}`")
            if details:
                lines.append(f"- **{title}** — " + " · ".join(details))
            else:
                lines.append(f"- **{title}**")
        return "\n".join(lines) if lines else "_No skills enabled._"
    except FileNotFoundError:
        return f"Missing file: {path}"
    except Exception as exc:
        return f"Failed to parse {path}: {exc}"


def _normalize_selection(selection):
    if isinstance(selection, list):
        return selection[0] if selection else None
    return selection


def _relative_path(path, root_dir):
    return os.path.relpath(path, root_dir).replace(os.sep, "/")


def _language_for(path):
    return LANGUAGE_BY_EXT.get(os.path.splitext(path)[1].lower(), None)


def _is_probably_text(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in TEXT_EXTENSIONS:
        return True
    try:
        with open(path, "rb") as handle:
            chunk = handle.read(2048)
        return b"\x00" not in chunk
    except OSError:
        return False


def _directory_listing(path, root_dir):
    entries = []
    for name in sorted(os.listdir(path)):
        if name == ".DS_Store":
            continue
        full_path = os.path.join(path, name)
        suffix = "/" if os.path.isdir(full_path) else ""
        entries.append(f"- `{_relative_path(full_path, root_dir)}{suffix}`")
    if not entries:
        entries.append("_Empty directory._")
    return "\n".join(entries)


def load_skill_preview(selection, root_dir):
    selected = _normalize_selection(selection)
    if not selected:
        return (
            "## Skills Preview\nSelect a file or folder from `SKILLS/`.",
            gr.update(value="", language="markdown", label="Preview"),
        )

    root_dir = os.path.abspath(root_dir)
    selected = os.path.abspath(selected)
    if os.path.commonpath([root_dir, selected]) != root_dir:
        return (
            "## Skills Preview\nSelected path is outside `SKILLS/`.",
            gr.update(value="", language="markdown", label="Preview"),
        )

    relative = _relative_path(selected, root_dir)
    if os.path.isdir(selected):
        listing = _directory_listing(selected, root_dir)
        return (
            f"## {relative}/\nDirectory preview for `{relative}/`.",
            gr.update(
                value=listing,
                language="markdown",
                label=f"{relative}/",
            ),
        )

    if not os.path.exists(selected):
        return (
            f"## Skills Preview\nMissing path: `{relative}`",
            gr.update(value="", language="markdown", label="Preview"),
        )

    if not _is_probably_text(selected):
        return (
            f"## {relative}\nBinary file preview is not supported.",
            gr.update(value="", language="markdown", label=relative),
        )

    with open(selected, "r", encoding="utf-8", errors="replace") as handle:
        content = handle.read(MAX_PREVIEW_BYTES + 1)

    truncated = len(content) > MAX_PREVIEW_BYTES
    if truncated:
        content = content[:MAX_PREVIEW_BYTES]

    note = " (truncated)" if truncated else ""
    return (
        f"## {relative}\nPreviewing `{relative}`{note}.",
        gr.update(
            value=content,
            language=_language_for(selected),
            label=relative,
        ),
    )
