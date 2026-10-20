"""Explicitly scoped local reset operations; never follow links or unknown entries."""
from __future__ import annotations

import json
import stat
from pathlib import Path

from manager_core import APP_NAME, data_directory

MARKER = ".moviepilot-manager-owned.json"
FILES = {"manager.sqlite", "manager.sqlite-wal", "manager.sqlite-shm", "manager.sqlite-journal",
         "settings.json", "settings.tmp", MARKER}
DIRECTORIES = {"backup", "backups", "exports", "diagnose", "browser-profile", "tmp", "temp", "user-images"}


def _not_link(path: Path):
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except FileNotFoundError:
        attributes = 0
    if path.is_symlink() or attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400) or (hasattr(path, "is_junction") and path.is_junction()):
        raise ValueError(f"Verknüpfung wird aus Sicherheitsgründen nicht bearbeitet: {path.name}")


def _root(path: Path) -> Path:
    path = path.absolute()
    for part in (path, *path.parents):
        _not_link(part)
    root = path.resolve()
    if root != data_directory().resolve() or root == Path(root.anchor) or root == Path.home():
        raise ValueError("Löschen ist nur im eigenen Appdatenverzeichnis erlaubt.")
    return root


def register_data_directory(path: Path):
    root = _root(path)
    marker = root / MARKER
    _not_link(marker)
    if marker.exists():
        if json.loads(marker.read_text(encoding="utf-8")).get("application") != APP_NAME:
            raise ValueError("Appdatenverzeichnis ist nicht eindeutig zugeordnet.")
    else:
        marker.write_text(json.dumps({"application": APP_NAME}), encoding="utf-8")


def managed_data_preview(path: Path) -> dict:
    root = _root(path)
    marker = root / MARKER
    _not_link(marker)
    if not marker.is_file() or json.loads(marker.read_text(encoding="utf-8")).get("application") != APP_NAME:
        raise ValueError("Eigentumsmarkierung fehlt; Appdaten werden nicht gelöscht.")
    for name in (".moviepilot-browser-active", "SingletonLock", "lockfile"):
        if (root / "browser-profile" / name).exists():
            raise ValueError("Browserprofil ist möglicherweise geöffnet. Browserexport und externe Browser zuerst schließen; Appdaten wurden nicht gelöscht.")
    entries, foreign = [], []
    for child in root.iterdir():
        _not_link(child)
        owned = child.name in FILES if child.is_file() else child.name in DIRECTORIES and child.is_dir()
        if not owned:
            foreign.append(child.name)
            continue
        entries.append(child)
        if child.is_dir():
            for item in child.rglob("*"):
                _not_link(item)
                if item.resolve().is_relative_to(root):
                    entries.append(item)
                else:
                    raise ValueError("Datei liegt außerhalb des Appdatenbereichs.")
    files = [p for p in entries if p.is_file()]
    return dict(root=root, entries=entries, files=len(files), bytes=sum(p.stat().st_size for p in files), foreign=foreign)


def delete_managed_data(path: Path) -> dict:
    """UI must close DB and stop its worker before calling. Partial failure is an error."""
    preview = managed_data_preview(path)
    failures = []
    # Keep the marker until the final step so partial cleanup can be retried safely.
    entries = sorted((p for p in preview["entries"] if p.name != MARKER), key=lambda p:len(p.parts), reverse=True)
    for item in entries:
        try:
            for ancestor in (item, *item.parents):
                _not_link(ancestor)
                if ancestor == preview["root"]:
                    break
            if not item.resolve().is_relative_to(preview["root"]):
                raise ValueError("Pfad außerhalb des Appdatenbereichs")
            item.rmdir() if item.is_dir() else item.unlink(missing_ok=True)
        except (OSError, ValueError) as exc:
            failures.append(f"{item.relative_to(preview['root'])}: {exc}")
    if failures:
        raise OSError("Appdaten nur teilweise gelöscht. Dateien möglicherweise gesperrt; externe Browser/Instanzen schließen.\n" + "\n".join(failures[:8]))
    remaining = managed_data_preview(path)
    if any(p.name != MARKER for p in remaining["entries"]):
        raise OSError("Es sind noch verwaltete Appdaten vorhanden. Keine vollständige Löschung bestätigt.")
    (preview["root"] / MARKER).unlink()
    return dict(foreign=preview["foreign"])
