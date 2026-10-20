"""Explicit local preparation / allowlisted GitHub publication. No push on import."""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
from app_info import APP_VERSION, APP_TITLE, PACKAGE_STEM
from package_release import SOURCE_FILES, check_public_path

ROOT = Path(__file__).resolve().parent
REPO = "Stigliz81/FilmKompass"
OWNER = "Stigliz81"
TAG = "v" + APP_VERSION + ".0" if APP_VERSION.count(".") == 1 else "v" + APP_VERSION


def run(args, cwd=ROOT, capture=False, env=None):
    result = subprocess.run([str(x) for x in args], cwd=cwd, env=env,
                            capture_output=capture, text=True, encoding="utf-8")
    if result.returncode:
        raise RuntimeError("Command failed: " + str(args[0]) + " " + str(args[1]))
    return result.stdout.strip() if capture else ""


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def public_source_check():
    import re
    from PIL import Image
    for name in SOURCE_FILES:
        check_public_path(name)
        p = ROOT / name
        if not p.is_file() or p.is_symlink():
            raise RuntimeError("Missing or linked public file: " + name)
        if p.suffix.lower() in {".py", ".md", ".txt", ".ps1", ".bat", ".json", ".yml"}:
            text = p.read_text(encoding="utf-8-sig")
            # Construct markers at runtime; never embed local identities in public sources.
            if any(marker.casefold() in text.casefold() for marker in (str(ROOT), str(Path.home()))):
                raise RuntimeError("Private path in " + name)
            if re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{24,}", text):
                raise RuntimeError("Possible secret in " + name)
        if p.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            with Image.open(p) as im:
                if im.getexif():
                    raise RuntimeError("Unexpected image metadata: " + name)


def prepare():
    public_source_check()
    with tempfile.TemporaryDirectory(prefix="filmkompass-tests-") as data:
        env = dict(os.environ, MOVIEPILOT_MANAGER_DATA_DIR=data)
        run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], env=env)
    run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "build_windows.ps1"])
    run([sys.executable, "package_release.py"])
    print("Packages prepared. Native, archive/runtime privacy and name review must pass before publish.")


def publish(gh, report_path, staging):
    # Always verify the real CLI account before any upload. Never auto-switch accounts.
    run([gh, "auth", "status"])
    user = json.loads(run([gh, "api", "user"], capture=True))
    if user["login"].casefold() != OWNER.casefold():
        raise RuntimeError("Wrong GitHub account. Sign in as " + OWNER + "; nothing uploaded.")
    public_source_check()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    gate = report.get("release_gate", {})
    if gate.get("passed") is not True or gate.get("repository") != REPO or gate.get("version") != APP_VERSION:
        raise RuntimeError("Missing approved technical/privacy/native/name verification report.")
    out = report_path.parent
    packages = [out / (PACKAGE_STEM + "-Windows-portabel.zip"),
                out / (PACKAGE_STEM + "-Quellcode.zip"), out / "SHA256SUMS.txt"]
    for p in packages:
        if digest(p) != gate.get("assets", {}).get(p.name):
            raise RuntimeError("Missing/changed release asset: " + p.name)
    if gate.get("sources") != {name: digest(ROOT / name) for name in SOURCE_FILES}:
        raise RuntimeError("Sources changed after release review.")
    # Inspect an existing repository without hiding authorization/network failures as absence.
    listing = json.loads(run([gh, "api", "user/repos?per_page=100", "--paginate", "--slurp"], capture=True))
    existing = [repo for page in listing for repo in page if repo["full_name"].casefold() == REPO.casefold()]
    if existing:
        repo = json.loads(run([gh, "api", "repos/" + REPO], capture=True))
        if not repo.get("permissions", {}).get("admin"):
            raise RuntimeError("Repository administration rights required for " + REPO)
        refs = json.loads(run([gh, "api", "repos/" + REPO + "/git/matching-refs/"], capture=True))
        releases = json.loads(run([gh, "api", "repos/" + REPO + "/releases"], capture=True))
        if refs or releases:
            raise RuntimeError("Repository already has content/tags/releases. Inspect it before continuing; no overwrite.")
    if staging.exists():
        raise RuntimeError("Staging directory exists; preserve it and inspect previous publication status.")
    staging.mkdir(parents=True)
    for name in SOURCE_FILES:
        dest = staging / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, dest)
    run(["git", "init", "-b", "main"], cwd=staging)
    run(["git", "config", "user.name", OWNER], cwd=staging)
    run(["git", "config", "user.email", str(user["id"]) + "+" + user["login"] + "@users.noreply.github.com"], cwd=staging)
    run(["git", "add", "--"] + list(SOURCE_FILES), cwd=staging)
    staged = run(["git", "diff", "--cached", "--name-only"], cwd=staging, capture=True).splitlines()
    if set(staged) != set(SOURCE_FILES):
        raise RuntimeError("Staged file boundary differs from SOURCE_FILES.")
    run(["git", "commit", "-m", "Release " + APP_TITLE], cwd=staging)
    if not existing:
        run([gh, "repo", "create", REPO, "--private", "--description",
             "FilmKompass â€“ kostenloses Windows-Tool zum Herunterladen, Archivieren und Exportieren von Moviepilot-Bewertungen als Excel/CSV."])
    run(["git", "remote", "add", "origin", "https://github.com/" + REPO + ".git"], cwd=staging)
    run([gh, "auth", "setup-git", "--hostname", "github.com"])
    run(["git", "push", "-u", "origin", "main"], cwd=staging)
    run(["git", "tag", TAG], cwd=staging)
    run(["git", "push", "origin", TAG], cwd=staging)
    notes = out / "RELEASE_NOTES.md"
    notes.write_text("# " + APP_TITLE + "\n\nMoviepilot-Bewertungen lokal herunterladen, filtern, sichern und als Excel/CSV exportieren.\n\nWindows: ZIP vollstÃ¤ndig entpacken und FilmKompass.exe mit dem gesamten _internal-Ordner verwenden. Keine Python-Installation oder Administratorrechte erforderlich. EXE unsigniert; SHA256SUMS.txt prÃ¼fen.\n\nBewertungen mÃ¼ssen fÃ¼r den Standarddownload Ã¶ffentlich sichtbar sein. Keine automatische KI- oder CloudÃ¼bertragung. MIT-Lizenz.\n", encoding="utf-8")
    run([gh, "release", "create", TAG, *packages, "--repo", REPO, "--draft", "--title", APP_TITLE, "--notes-file", notes])
    drafts = json.loads(run([gh, "api", "repos/" + REPO + "/releases"], capture=True))
    release = next(item for item in drafts if item["tag_name"] == TAG and item["draft"])
    if {x["name"] for x in release["assets"]} != {p.name for p in packages}:
        raise RuntimeError("Draft asset list mismatch; repository/release left for inspection.")
    # Download draft assets through authenticated CLI and check actual hosted bytes before exposure.
    with tempfile.TemporaryDirectory(prefix="filmkompass-draft-") as target:
        run([gh, "release", "download", TAG, "--repo", REPO, "--dir", target])
        for p in packages:
            if digest(Path(target) / p.name) != digest(p):
                raise RuntimeError("Hosted draft asset hash mismatch.")
    run([gh, "repo", "edit", REPO, "--add-topic", "moviepilot,movie-ratings,csv-export,excel-export,python,windows,sqlite,filmkompass"])
    run([gh, "repo", "edit", REPO, "--visibility", "public", "--accept-visibility-change-consequences"])
    run([gh, "release", "edit", TAG, "--repo", REPO, "--draft=false", "--latest"])
    release = json.loads(run([gh, "api", "repos/" + REPO + "/releases/tags/" + TAG], capture=True))
    urls = {a["name"]: a["browser_download_url"] for a in release["assets"]}
    readme = (staging / "README.md").read_text(encoding="utf-8")
    start, end = readme.index("## Downloads"), readme.index("## Startanleitung")
    section = "## Downloads\n\n**Windows 11 x64 Â· keine Python-Installation Â· keine Administratorrechte**\n\n"
    section += "- [FilmKompass 1.0 fÃ¼r Windows herunterladen](" + urls[packages[0].name] + ")\n"
    section += "- [VollstÃ¤ndigen Python-Quellcode herunterladen](" + urls[packages[1].name] + ")\n"
    section += "- [SHA-256-PrÃ¼fsummen](" + urls[packages[2].name] + ")\n\n"
    section += "Die EXE ist derzeit **nicht digital signiert**. Verwende diese offizielle Bezugsquelle und prÃ¼fe SHA256SUMS.txt. Windows-Sicherheitsfunktionen mÃ¼ssen nicht pauschal deaktiviert werden.\n\n"
    readme = readme[:start] + section + readme[end:]
    (staging / "README.md").write_text(readme, encoding="utf-8")
    (ROOT / "README.md").write_text(readme, encoding="utf-8")
    run(["git", "add", "README.md"], cwd=staging)
    run(["git", "commit", "-m", "Link verified release downloads"], cwd=staging)
    run(["git", "push", "origin", "main"], cwd=staging)
    # Public, unauthenticated download check; exact final asset hashes.
    import urllib.request
    for p in packages:
        with urllib.request.urlopen(urls[p.name]) as response:
            if hashlib.sha256(response.read()).hexdigest() != digest(p):
                raise RuntimeError("Public download hash mismatch.")
    status = {"repository": "https://github.com/" + REPO, "release": release["html_url"],
              "tag": TAG, "published": not release["draft"], "urls": urls, "public_download_hashes_match": True}
    (out / "PUBLICATION.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "publish"])
    parser.add_argument("--gh", default="gh")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--staging", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    else:
        if not args.report or not args.staging:
            parser.error("publish requires --report and a new --staging directory")
        publish(args.gh, args.report.resolve(), args.staging.resolve())

if __name__ == "__main__":
    main()
