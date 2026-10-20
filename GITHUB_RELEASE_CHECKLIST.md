# FilmKompass – Veröffentlichung

Ziel ist ausschließlich `Stigliz81/FilmKompass`. Produktversion und Paketnamen stammen aus `app_info.py`. Eine interne numerische Dateiversion ist eine technische Kennung, kein Bestandteil des öffentlichen Produktnamens.

## Lokal vorbereiten

```powershell
python publish_release.py prepare
```

Die Routine prüft die öffentliche Dateiliste, führt Tests aus und verwendet die bestehenden Build-/Paketwerkzeuge. Vorhandene Ausgabeordner werden nicht überschrieben. Neue Ausgabeordner für spätere Versionen bewusst in der Build-/Paketkonfiguration wählen. Kein automatischer Upload bei normalen Pushes; der Tests-Workflow veröffentlicht nichts.

Anschließend die tatsächliche Runtime mit isoliertem Datenordner nativ prüfen. ZIPs entpacken/starten, Quellcode/Runtime abgleichen, alle Payload-Hashes prüfen. Die ausdrückliche öffentliche Dateiliste ist `package_release.SOURCE_FILES`. Keine Datenbanken, Exporte, Backups, Einstellungen, Browserprofile, QA-Dateien, privaten Screenshots oder lokalen Entwicklungsrefs übernehmen. Der Freigabebericht bleibt lokal und muss die geprüften Quell-/Archivhashes enthalten.

Die dokumentierte Namensvorprüfung ersetzt keine juristische Markenfreigabe. Ein konkreter relevanter Konflikt oder kritischer Datenschutzbefund stoppt die Veröffentlichung.

## Konto und vorhandene Inhalte prüfen

```powershell
gh auth status
gh api user
```

Ausschließlich als **Stigliz81** veröffentlichen. Bei anderem Konto, fehlender Anmeldung oder Berechtigung stoppen und korrekt anmelden lassen. Kein Kontoersatz. Vorhandene Repositoryinhalte, Tags und Releases prüfen; keine automatische Überschreibung, kein Force-Push, kein Spiegeln lokaler Git-Refs.

## Ausdrücklich veröffentlichen

```powershell
python publish_release.py publish --report PFAD_ZUM_GEPRUEFTEN_LOKALEN_BERICHT --staging NEUER_LEERER_AUSGABEORDNER
```

`--gh` kann auf eine separat installierte offizielle GitHub CLI zeigen. `--report` muss eine erfolgreiche lokale `release_gate` mit Zielrepository, Version und aktuellen Quell-/Assethashes enthalten. Ohne diese Prüfung wird nichts hochgeladen. Keine Tokens in Dateien oder Kommandoargumenten hinterlegen.

Die Routine erstellt aus der Allowlist ein separates sauberes Repository und verwendet eine öffentliche GitHub-Noreply-Adresse. Zunächst private Stufe und Entwurfsrelease, anschließend Rückdownload und SHA-256-Vergleich. Erst danach öffentliche Sichtbarkeit und Release. Die Release-Assets sind Windows-ZIP, Quellcode-ZIP und SHA256SUMS.txt. Vorhandene Inhalte werden nicht ersetzt. Fehler nach einem Teilerfolg erfordern eine Prüfung des tatsächlichen Onlinezustands; nicht blind erneut starten.

Die README erhält erst danach die tatsächlich von GitHub gelieferten Asset-URLs. Öffentliche Downloads werden ohne Anmeldung erneut geladen und mit lokalen Hashes verglichen. Der tatsächliche Abschlussstatus liegt lokal in PUBLICATION.json. Ohne diesen Nachweis keine erfolgreiche Veröffentlichung behaupten.
