# Python, Entwicklung und technische Grenzen

[Zur Produktseite](../README.md) · [Funktionen](FUNKTIONEN.md) · [Datenschutz](DATENSCHUTZ.md)

## Python und lokaler Build

Die vollständige Python-Fassung enthält Module, Assets, Tests, Startskripte und Abhängigkeiten. Mit Python 3.13 zuerst `python_einrichten_windows.bat`, danach `starten_windows.bat` ausführen. Alternativ:

```powershell
python -m pip install -r requirements.txt
python moviepilot_manager.py
```

Pillow ist die einzige notwendige Fremdabhängigkeit. Optionales Playwright/Chromium ist separat einzurichten und nicht Teil des Windows-Pakets.

Die Anwendung verwendet Tkinter/ttk, SQLite und die Python-Standardbibliothek für HTTPS, CSV und XLSX. Öffentliche Version: **FilmKompass 1.0**. Die Versionskonfiguration liegt zentral in `app_info.py`; interne technische Versionswerte werden nicht automatisch erhöht.

```powershell
python -m unittest discover -s tests -v
powershell -ExecutionPolicy Bypass -File build_windows.ps1
python package_release.py
```

Vorhandene Ausgabeordner werden geschützt. Das Windows-Paket benötigt den vollständigen `_internal`-Ordner neben `FilmKompass.exe`. Hinweise zur geprüften manuellen Veröffentlichungsroutine: [Veröffentlichungsanleitung](../GITHUB_RELEASE_CHECKLIST.md).

## Bildfunktionen und Sicherheit

Die detaillierte Bildverarbeitung, Cache-/Anzeigegrenzen sowie DNS-/TLS-Prüfungen stehen bereits unter [Genreillustrationen und eigenen Titelbildern](AP03_IMAGES.md). Die Kopfbereichsmotive und ihre Ableitungen beschreibt [Eigene Hintergründe](BACKGROUNDS.md).

## Abruf, optionaler Browseradapter und Importzuordnung

Die [historische Untersuchung und Importregeln](AP02_RESEARCH.md) dokumentieren Profilzugriff, Grenzen des optionalen Playwright-Adapters, fehlende Poster-Rechtefreigabe und die Zuordnung URL-freier Importe. Der Browseradapter bleibt separat einzurichten; ein aktueller Live-Login-/DOM-Test ist nicht bestätigt.

## Kompatibilität und häufige Detailfragen

**Brauche ich eine Browseranmeldung?** Nein. Der Standarddownload ruft öffentlich sichtbare Profilbewertungen per HTTPS ab. Aktiviere bei Bedarf „Meine Bewertungen öffentlich zeigen“ in deinen Moviepilot-Profileinstellungen. Nach dem Download kannst du deine Bewertungen wieder privat stellen. Während der Freigabe können auch andere deine Bewertungen sehen. Ein normaler Browserlogin macht private Bewertungen für den Standarddownload nicht abrufbar.

**Wie kann ich Moviepilot-Bewertungen als Excel speichern?** Öffne „Filmdatenbank exportieren“, wähle die gesamte Bibliothek oder gefilterte Treffer und XLSX. Der Moviepilot Excel Export enthält numerische Noten und echte Datumszellen. Für den Moviepilot CSV Export wählst du CSV; Halbnoten und Umlaute bleiben erhalten.

**Was bedeutet Moviepilot-Filmliste exportieren?** FilmKompass 1.0 exportiert deine persönliche Bewertungsliste. Beliebige öffentliche Bestenlisten oder thematische Moviepilot-Filmlisten werden derzeit nicht heruntergeladen. Eine spätere Erweiterung ist möglich, gehört aber nicht zu Version 1.0. Die App lädt keine Filme oder Videos herunter.

**Wie sichere ich meine Moviepilot-Bewertungen?** CSV/XLSX exportieren bewusst sechs Bewertungsfelder. Ein vollständiges persönliches Moviepilot-Backup ist separat als SQLite-Sicherung möglich und enthält zusätzliche persönliche Informationen. Benutzerbilder beim Gerätewechsel zusätzlich sichern. Keine automatische KI-Übertragung oder Cloud-Synchronisation.

**Bleiben vorhandene Bibliotheken erhalten?** Ja. Der interne Datenordner `%LOCALAPPDATA%/MoviepilotManager` bleibt aus Kompatibilitätsgründen erhalten. Die Namensänderung erzeugt keine Ersatzbibliothek und löst keine automatische Datenmigration aus.

## Programm-Icon

<img src="../assets/filmkompass.png" width="128" alt="Filmrollen- und Downloadsymbol des FilmKompasss">

Das vom Nutzer bereitgestellte Filmrollenbild ist die Vorlage für Header und Windows-Symbol. Alte Screenshots mit dem früheren Produktnamen werden nicht als aktuelle FilmKompass-Oberfläche mitgeliefert.

## Veröffentlichung

Der [Veröffentlichungsablauf](../GITHUB_RELEASE_CHECKLIST.md) bleibt getrennt von der Produktseite. Für künftige Veröffentlichungen den aktuellen Helfer aus dem main-Branch verwenden. Release v1.0.0 und seine ZIPs sind eingefroren; die nachfolgenden README-/Veröffentlichungshelferkorrekturen gehören zum Entwicklungsstand auf main.
