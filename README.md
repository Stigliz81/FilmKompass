# FilmKompass 1.1

**Deine Filme. Deine Bewertungen. Deine Filmlisten.** Kostenloser, quelloffener Windows-Filmmanager für öffentlich sichtbare Moviepilot-Bewertungen.

## Download

- [Windows x64 – portables ZIP](https://github.com/Stigliz81/FilmKompass/releases/download/v1.1.2/FilmKompass-1.1-Windows-portabel.zip)
- [Python-Quellcode](https://github.com/Stigliz81/FilmKompass/releases/download/v1.1.2/FilmKompass-1.1-Quellcode.zip)
- [SHA-256-Prüfsummen](https://github.com/Stigliz81/FilmKompass/releases/download/v1.1.2/SHA256SUMS.txt)
- [Webseite](https://stigliz81.github.io/FilmKompass/) · [Releasehistorie einschließlich 1.0](https://github.com/Stigliz81/FilmKompass/releases)

ZIP vollständig in einen beschreibbaren Ordner entpacken und FilmKompass.exe starten. Der komplette `_internal`-Ordner gehört dazu. Keine separate Python-Installation oder Administratorrechte erforderlich. EXE unsigniert; offizielle Quelle und Prüfsummen verwenden, Windows-Sicherheitsfunktionen eingeschaltet lassen.

## Funktionen

- Film-/Serienbewertungen und vorhandenes Bewertungsdatum herunterladen, lokal durchsuchen, sortieren und filtern.
- Unterstützte öffentliche Filmlisten separat speichern und mit der eigenen Bibliothek abgleichen. Empfehlungsabgleich für eingefügte Titel. Zugriffssperren werden respektiert; Katalogabrufe sind auf 200 Titel begrenzt.
- Listenansicht und Miniaturen in Klein, Mittel und Groß; 15 Genreillustrationen als Ersatzmotive.
- Optionale Fanart.tv-Coverautomatik mit persönlichem API Key, Pause/Fortsetzen und lokalem Cache. Eigene Bilder haben Vorrang. Keine echten Cover im Paket.
- XLSX/CSV importieren und gesamte/gefilterte Bewertungen exportieren; Halbnoten bleiben Zahlen.
- Statistik, lokale Sicherungen und kontrollierter Reset einschließlich Filmlisten. Vollständiges Appdatenlöschen erstellt vorher eine geprüfte externe Sicherung.
- Direkte Moviepilot-Links, Kurzanleitung und freiwillige Versionsprüfung, standardmäßig aus. Keine automatische Updateinstallation.

Keine Filme oder Videos werden heruntergeladen, keine Bibliotheken automatisch in Cloud-/KI-Dienste übertragen und keine Zugriffssperren umgangen. Ein freier Vergleich zweier beliebiger Listen ist nicht enthalten.

## Cover und persönliche Daten

Persönlichen API Key unter https://fanart.tv/get-an-api-key/ erhalten und in Einstellungen & Daten speichern/prüfen. Kein Project API Key für normale Nutzer erforderlich. Bestehende Entwicklerkonfiguration optional unterstützt. **Keine echten Schlüssel in Git oder Paketen.** Bilder über [fanart.tv](https://fanart.tv/), Zuordnung gegebenenfalls über Wikidata. Bildrechte beachten.

Daten liegen standardmäßig unter `%LOCALAPPDATA%/MoviepilotManager`. SQLite-Sicherungen enthalten Bildzuordnungen; Bilder für einen Gerätewechsel zusätzlich sichern. Komplettsicherungen können private Keys enthalten: nicht veröffentlichen. Zwei Instanzen nicht auf dasselbe Profil richten.

## Systeme und Hinweise

Windows 10/11 x64. Hauptfunktionen und korrigiertes Taskleistensymbol wurden vom Nutzer praktisch bestätigt. Keine erneute Windows-10-Prüfung des finalen Pakets behauptet. Persönlicher Fanart-Key allein technisch/simuliert geprüft; mangels persönlichem Testkey kein bestätigter Live-Test dieses Modus.

[Start und Sicherung](docs/V1.1_START.md) · [Fanart-Hinweise](docs/FANART.md) · [Datenschutz](docs/DATENSCHUTZ.md) · [MIT-Lizenz](LICENSE) · [Fremdlizenzen](THIRD_PARTY_NOTICES.md)

Unabhängiges Projekt, nicht offiziell mit Moviepilot verbunden. Copyright (c) 2026 Stigliz81. Projektunterstützung ist freiwillig; bestehende Zahlungswege stehen auf der Webseite.

[Veröffentlichungsbericht AP16.09 mit Prüfsummen und Prüfgrenzen](docs/AP16.09_FINAL_RELEASE.md) · [Arbeitspaketübersicht](docs/ARBEITSPAKETE.md)
