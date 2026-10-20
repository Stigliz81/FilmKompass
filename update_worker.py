"""Background update: each worker owns its SQLite connection; no Tk calls."""
from pathlib import Path

from manager_core import Catalog
from moviepilot_exporter import run_export


def update_library(username: str, root: Path, notify, progress=None):
    result = run_export(username, root / "exports", notify=notify, progress=progress)
    files = [path for path, count in zip(result.files[:2], (result.movies, result.series)) if count]
    summary = dict(added=0, changed=0, unchanged=0, unavailable=0, count=0)
    if files:
        database = Catalog(root / "manager.sqlite")
        try:
            summary = database.import_files(files, notify=notify)
        finally:
            database.close()
    warnings = []
    if not files:
        warnings.append("Moviepilot lieferte eine leere Bibliothek; vorhandene Daten wurden nicht verändert.")
    if summary["unavailable"]:
        warnings.append(f"{summary['unavailable']} Titel fehlen im neuen Export; persönliche Angaben bleiben gespeichert.")
    notify("Aktualisierung abgeschlossen")
    return dict(export=result, imported=summary, warnings=warnings)
