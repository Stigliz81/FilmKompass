"""Create local release archives from an explicit public-file allowlist. No upload."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

from app_info import APP_VERSION, BUILD_NUMBER, FILE_VERSION, PACKAGE_STEM, EXE_STEM, APP_TITLE

ROOT = Path(__file__).resolve().parent
SOURCE_FILES = (
    "AGENTS.md", ".gitignore", ".gitattributes", ".github/workflows/tests.yml",
    "README.md", "GITHUB_RELEASE_CHECKLIST.md", "THIRD_PARTY_NOTICES.md", "LICENSE",
    "app_info.py", "manager_core.py", "moviepilot_manager.py", "moviepilot_exporter.py",
    "genre_art.py", "thumbnail_view.py", "user_images.py", "tests/test_ap03.py", "docs/GENRE_ART.json", "docs/AP03_IMAGES.md",
    "assets/genres/action.jpg", "assets/genres/scifi.jpg", "assets/genres/fantasy.jpg", "assets/genres/drama.jpg", "assets/genres/thriller.jpg", "assets/genres/crime.jpg", "assets/genres/horror.jpg", "assets/genres/comedy.jpg", "assets/genres/romance.jpg", "assets/genres/adventure.jpg", "assets/genres/animation.jpg", "assets/genres/documentary.jpg", "assets/genres/western.jpg", "assets/genres/history.jpg", "assets/genres/neutral.jpg",
    "tests/test_ap11.py", "tests/test_ap10.py", "tests/test_ap08.py", "tests/test_ap07.py", "tests/test_ap06.py", "tests/test_ap05.py", "header_backdrop.py", "tests/test_ap04.py", "catalog_view.py", "compact_widgets.py", "tests/test_ap02.py", "docs/screenshots/filmkompass-1.0-library.png", "docs/screenshots/filmkompass-1.0-profile.png", "docs/AP02_RESEARCH.md", "docs/BACKGROUNDS.md",
    "assets/backgrounds/banners/gallery.jpg", "assets/backgrounds/banners/archive.jpg", "assets/backgrounds/banners/studio.jpg", "assets/backgrounds/banners/cinema.jpg", "assets/backgrounds/gallery.jpg", "assets/backgrounds/archive.jpg", "assets/backgrounds/studio.jpg", "assets/backgrounds/cinema.jpg",
    "donation_assets.py", "app_data.py", "update_worker.py", "starten_windows.bat", "python_einrichten_windows.bat",
    "exporter_einrichten_windows.bat", "requirements.txt", "requirements-export.txt",
    "requirements-build.txt", "build_windows.ps1", "windows_version_info.txt", "package_release.py", "publish_release.py", "tests/test_release.py",
    "tests/test_core.py", "tests/test_exporter.py", "tests/test_direct_download.py", "tests/test_ap01.py",
    "assets/filmkompass.ico", "assets/filmkompass.png",
    "assets/donations/originals/paypal.jpg", "assets/donations/originals/btc.png",
    "assets/donations/originals/ltc-mainnet.jpg", "assets/donations/originals/ltc-bep20.png", "assets/donations/originals/usdc.png",
    "assets/donations/originals/binance.png",
    "third_party/CPython-LICENSE.txt", "third_party/Pillow-LICENSE.txt", "third_party/Tk-LICENSE.txt",
)
PRIVATE_PARTS = {"data", "exports", "browser-profile", "backup", "backups", "diagnose", "qa", ".git", ".venv", "user-images"}
PRIVATE_SUFFIXES = {".csv", ".xlsx", ".xls", ".sqlite", ".sqlite3", ".db", ".log", ".har", ".jsonl"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_public_path(path: str):
    parts = Path(path).parts
    if any(part.lower() in PRIVATE_PARTS for part in parts) or Path(path).suffix.lower() in PRIVATE_SUFFIXES:
        raise ValueError(f"Private file category in release payload: {path}")
    if Path(path).name.lower() in {"settings.json", "personal_seed.json", "cookies.json"}:
        raise ValueError(f"Private settings in release payload: {path}")


def create_archive(target: Path, entries: dict[str, Path], top: str) -> dict:
    manifest = {name: sha256(path) for name, path in sorted(entries.items())}
    for name in entries:
        check_public_path(name)
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(entries.items()):
            archive.write(path, f"{top}/{name}")
        archive.writestr(f"{top}/MANIFEST.sha256.json", json.dumps(manifest, indent=2) + "\n")
    # Check both compressed integrity and exact published bytes, independently of extraction.
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP integrity check failed")
        for name, digest in manifest.items():
            if hashlib.sha256(archive.read(f"{top}/{name}")).hexdigest() != digest:
                raise ValueError(f"ZIP payload mismatch: {name}")
    return {"file": target.name, "sha256": sha256(target), "files": len(manifest), "bytes": target.stat().st_size}


def main():
    runtime = ROOT / "dist" / "AP12" / APP_VERSION / f"Build{BUILD_NUMBER}" / EXE_STEM
    if not (runtime / (EXE_STEM+".exe")).is_file():
        raise SystemExit("Build is missing; run build_windows.ps1 first.")
    source = {name: ROOT / name for name in SOURCE_FILES}
    missing = [name for name, path in source.items() if not path.is_file()]
    if missing:
        raise SystemExit(f"Required public files missing: {missing}")
    output = ROOT / "release" / "AP12" / APP_VERSION / f"Build{BUILD_NUMBER}"
    output.mkdir(parents=True, exist_ok=False)
    portable = {p.relative_to(runtime).as_posix(): p for p in runtime.rglob("*") if p.is_file()}
    for name in ("README.md", "GITHUB_RELEASE_CHECKLIST.md", "THIRD_PARTY_NOTICES.md", "LICENSE", "docs/screenshots/filmkompass-1.0-library.png", "docs/screenshots/filmkompass-1.0-profile.png", "docs/AP02_RESEARCH.md", "docs/BACKGROUNDS.md", "docs/AP03_IMAGES.md", "docs/GENRE_ART.json", ):
        portable[name] = ROOT / name
    for path in (ROOT / "third_party").glob("*.txt"):
        portable["third_party/" + path.name] = path
    results = [
        create_archive(output / f"{PACKAGE_STEM}-Windows-portabel.zip", portable, EXE_STEM),
        create_archive(output / f"{PACKAGE_STEM}-Quellcode.zip", source, f"{PACKAGE_STEM}-Quellcode"),
    ]
    (output / "SHA256SUMS.txt").write_text("".join(f"{r['sha256']}  {r['file']}\n" for r in results), encoding="utf-8")
    (output / "PACKAGE_REPORT.json").write_text(json.dumps({"product": APP_TITLE, "version": APP_VERSION, "build": BUILD_NUMBER, "file_version": FILE_VERSION, "work_package": "AP12", "status": "release_candidate", "published": False, "archives": results}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
