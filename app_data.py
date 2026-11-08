"""Explicitly scoped local reset operations; never follow links or unknown entries."""
from __future__ import annotations

import json
import stat
from pathlib import Path

from manager_core import APP_NAME, data_directory

MARKER = ".moviepilot-manager-owned.json"
FILES = {"manager.sqlite", "manager.sqlite-wal", "manager.sqlite-shm", "manager.sqlite-journal",
         "settings.json", "settings.tmp", MARKER}
DIRECTORIES = {"backup", "backups", "exports", "diagnose", "browser-profile", "tmp", "temp", "user-images", "fanart-cache"}


def automatic_backup_directory():
    """Resolve redirected Windows Documents via its known-folder identity, fail closed."""
    import sys
    if sys.platform != 'win32':
        raise OSError('Der Windows-Dokumenteordner konnte nicht ermittelt werden.')
    import ctypes
    from ctypes import wintypes
    import uuid
    folder_id = (ctypes.c_byte * 16).from_buffer_copy(uuid.UUID('FDD39AD0-238F-46AF-ADB4-6C85480369C7').bytes_le)
    value = ctypes.c_void_p()
    shell = ctypes.windll.shell32
    shell.SHGetKnownFolderPath.argtypes = [ctypes.c_void_p,wintypes.DWORD,wintypes.HANDLE,ctypes.POINTER(ctypes.c_void_p)]
    shell.SHGetKnownFolderPath.restype = ctypes.c_long
    if shell.SHGetKnownFolderPath(ctypes.byref(folder_id),0,None,ctypes.byref(value)) != 0:
        raise OSError('Windows-Dokumenteordner nicht verfügbar. Keine Daten gelöscht.')
    try:
        documents = Path(ctypes.wstring_at(value))
    finally:
        ctypes.windll.ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        ctypes.windll.ole32.CoTaskMemFree(value)
    if not documents.is_absolute():
        raise ValueError('Windows meldet keinen absoluten Dokumenteordner.')
    return documents / 'FilmKompass' / 'Sicherungen'


def verified_backup(catalog, folder=None):
    import sqlite3
    backup = catalog.backup(folder)
    from contextlib import closing
    with closing(sqlite3.connect(backup)) as con:
        if con.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('Sicherung konnte nicht geprüft werden. Nichts gelöscht.')
        if list(con.iterdump()) != list(catalog.con.iterdump()):
            raise ValueError('Sicherung stimmt nicht mit der Datenbank überein. Nichts gelöscht.')
    return backup


def backup_managed_data(catalog, destination):
    import zipfile
    import hashlib
    root = catalog.db_path.parent
    preview = managed_data_preview(root)
    destination = Path(destination).absolute()
    for part in (destination, *destination.parents):
        _not_link(part)
    if destination.resolve().is_relative_to(root.resolve()):
        raise ValueError('Sicherung muss außerhalb des Appdatenordners liegen.')
    destination.mkdir(parents=True, exist_ok=True)
    # Probe actual write access, not just permission bits; never replace an existing file.
    import tempfile
    with tempfile.TemporaryFile(dir=destination) as probe:
        probe.write(b'FilmKompass backup probe');probe.flush()
    snapshot = verified_backup(catalog, destination)
    target = snapshot.with_suffix('.zip')
    hashes = {}
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in preview['entries']:
            if not path.is_file() or path.name in ('manager.sqlite-wal','manager.sqlite-shm','manager.sqlite-journal'):
                continue
            _not_link(path)
            source = snapshot if path == catalog.db_path else path
            data = source.read_bytes()
            name = path.relative_to(root).as_posix()
            archive.writestr(name, data)
            hashes[name] = hashlib.sha256(data).hexdigest()
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() or any(hashlib.sha256(archive.read(n)).hexdigest()!=h for n,h in hashes.items()):
            raise ValueError('Appdatensicherung nicht verifiziert. Nichts gelöscht.')
    return target


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
