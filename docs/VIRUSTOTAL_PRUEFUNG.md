# Explizite VirusTotal-Prüfung vor einer FilmKompass-Freigabe

Die Routine `tools/virustotal_check.py` wird ausschließlich bewusst von der Kommandozeile aufgerufen. Keine Einbindung in Programmstart, Git-Hooks oder GitHub Actions. Keine zusätzliche Bibliothek.

Einmalig einen eigenen kostenlosen VirusTotal-API-Schlüssel lokal als **VIRUSTOTAL_API_KEY** setzen. Er wird nur als HTTPS-Header `x-apikey` verwendet. Nicht in Konfigurationsdateien, Kommandozeilenargumente, Protokolle oder Git schreiben. Ohne Schlüssel erzeugt die Routine Hashes und den Status `missing_api_key`; es findet keinerlei API-Aufruf statt.

Beispiel (Pfade durch die exakten finalen Dateien ersetzen):

```powershell
py -3.13 tools/virustotal_check.py --exe "dist/.../FilmKompass.exe" --zip "release/.../FilmKompass-privat.zip" --report "qa/.../virustotal.json"
```

Zuerst erfolgt jeweils eine Hashabfrage, unabhängig für EXE und ZIP. Vollständige auswertbare Ergebnisse werden mit Erkennungen, verdächtigen Ergebnissen, auswertbaren und ausgeschlossenen Engines, UTC-Zeit, Dateiname, SHA-256 und Berichtsadresse gespeichert. Frischegrenze standardmäßig sieben Tage (`--max-age-days`). Nicht auswertbare Engines umfassen Timeout, Fehler und nicht unterstützte Dateitypen. Keine Scanergebnisse schätzen.

## Uploadfreigabe

Erst nach Prüfung sämtlicher Buildinhalte eine **lokale**, hashgebundene Gate-Datei erstellen:

```json
{"privacy_reviewed": true, "files": {"FilmKompass.exe": "EXAKTER_EXE_SHA256", "FilmKompass-privat.zip": "EXAKTER_ZIP_SHA256"}}
```

Dann dem Aufruf `--upload --gate "qa/.../upload-gate.json"` hinzufügen. Diese Freigabe gilt nur für genau die beiden geprüften Dateien. Es dürfen ausschließlich ausdrücklich freigegebene Programmdateien hochgeladen werden. Standard-VirusTotal ist kein privater Ablageort; übermittelte Dateien können Sicherheitsanbietern zugänglich werden.

Die Routine prüft vor jedem Upload beide Hashes, ZIP-Manifest und alle Nutzdateihashes, private Dateikategorien, die exakte Übereinstimmung von EXE und ZIP-EXE sowie bekannte lokale Fanart-/VirusTotal-Schlüssel. Die Gate-Freigabe ersetzt diese Prüfungen nicht und umgekehrt ersetzt ein automatischer Dateiscan keine inhaltliche Privacyprüfung beliebiger Dateien. Fremde Gate-Dateien nicht ungeprüft übernehmen. Nach jeder Dateiänderung neu bauen/prüfen und Freigabe neu erstellen.

API v3: `GET /files/{sha256}`, optional `POST /files`, für Dateien über 32 MB zuvor `GET /files/upload_url`, anschließend `GET /analyses/{id}` und erneuter dateigebundener Bericht. Höchstens ein Aufruf alle 16 Sekunden, maximal 30 Anfragen pro Lauf. Die tatsächlichen Konto-/Tageslimits gelten zusätzlich. HTTP 429 einschließlich numerischem Retry-After wird als Fehler gespeichert; kein automatisches Wiederholen. Auch 401, Verbindungsfehler und unvollständige Analysen sind kein Erfolg. Maximale Pollzeit 300 Sekunden; spätere Wiederholung ist möglich.

Exitcode 0 nur bei zwei abgeschlossenen, vollständigen, aktuellen Berichten ohne malicious/suspicious; sonst 2. Positive oder verdächtige Ergebnisse werden offen gespeichert und müssen vor einer Veröffentlichung untersucht werden. Kein automatisches Hochstufen zum Fehlalarm. Ein ZIP-Bericht ersetzt den EXE-Bericht nicht.

## Website erst nach Freigabe

Nur Ergebnisse zu den **exakt öffentlich herunterladbaren** Bytes übernehmen. Version/Release, Dateiname, UTC-Prüfdatum, SHA-256, Erkennungen, verdächtige und auswertbare Engines sowie vollständigen Berichtslink nennen. Private Kandidatenberichte bleiben lokal. Es gibt weder eine Sicherheitsgarantie noch ein VirusTotal-/Microsoft-Zertifikat. Bei null Erkennungen: „Bei dieser Prüfung wurden von den auswertbaren Virenscannern keine Bedrohungen erkannt.“

Offizielle Quellen: [API](https://docs.virustotal.com/reference/overview), [Limits](https://docs.virustotal.com/reference/public-vs-premium-api), [Upload](https://docs.virustotal.com/reference/files-scan), [Analysen](https://docs.virustotal.com/reference/analysis).
