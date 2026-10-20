# Datenschutz und lokale Datensicherung

[Zur Produktseite](../README.md) · [Funktionen](FUNKTIONEN.md) · [Technik und Python](TECHNIK.md)

Standard: `%LOCALAPPDATA%/MoviepilotManager/`. Python und EXE verwenden denselben Pfad. Programmdateien sind portabel, die Bibliothek liegt im Benutzerprofil. Für einen PC-Wechsel diesen Ordner einschließlich `user-images/` separat sichern. Das SQLite-Backup enthält Bildzuordnungen, keine Bilddateien. Entfernte Zuordnungen lassen Bilddateien für vorhandene Backups erhalten; der vollständige Appdatenreset entfernt auch diesen Bilderordner. `MOVIEPILOT_MANAGER_DATA_DIR` ermöglicht isolierte Testdaten.

| Datei/Ordner | Inhalt |
|---|---|
| `manager.sqlite` | Bewertungen, Metadaten und erhaltene alte persönliche Angaben |
| `backup/` | Sicherungen, keine automatische Löschung alter Backups |
| `settings.json` | Profilname, Ansicht, Seitengröße, Spaltenbreiten, Kinomotiv |
| `user-images/` | Private geprüfte Bildkopien; Zuordnungen in SQLite |
| `exports/` | heruntergeladene Exportdateien |
| `browser-profile/` | ausschließlich optionale separate Browsersitzung |

Bewertungen werden lokal gespeichert. Der freiwillige CSV-/Excel-Export enthält genau Typ, Titel, Jahr, Note, Bewertet am und Genre. Diese bewusst exportierten Bewertungen sind persönliche Informationen; alte Notizen, Favoriten, Staffelwerte, interne IDs und Bildpfade werden nicht mit exportiert. Für die vollständige Datensicherung dient separat SQLite. Moviepilot-Downloads benötigen eine Internetverbindung.

Nur der eingegebene Profilname wird beim Abruf an Moviepilot gesendet. Keine Rückschreibung, keine Cloudintegration, keine regulären Browsercookies. Öffentliche Pakete enthalten keine Bibliotheken, Exporte, Backups, Sitzungen, Einstellungen oder privaten Pfade. Spendeninformationen sind bewusst öffentlich.

**Bibliothek zurücksetzen** sichert und leert nach Bestätigung die Bibliothek einschließlich alter Zusatzdaten/Importverlauf. Einstellungen und bestehende Backups bleiben erhalten. **Alle lokalen Appdaten löschen** zeigt den Umfang und verlangt zusätzlich `ALLES LÖSCHEN`; berücksichtigt auch Einstellungen und private Benutzerbilder. Nur bekannte Appdateien im eigenen markierten Datenordner werden entfernt, fremde Dateien bleiben. Links/Junctions und aktive Browserprofile blockieren; gesperrte Dateien werden als Fehler gemeldet. Außerhalb liegende Exporte werden nicht gelöscht. Die App beendet sich danach. Während eines Downloads/Imports sind solche Änderungen gesperrt.

### Freiwillige KI-Nutzung

Du kannst die vollständige CSV-/Excel-Datei selbst bei ChatGPT oder einem anderen KI-Dienst hochladen: Filmgeschmack analysieren, Lieblingsgenres erkennen sowie Film- und Serienempfehlungen anhand deiner bisherigen Noten erhalten. Empfehlungen sind Vorschläge. **Keine automatische KI-Analyse oder Übertragung durch die App.**

Bei häufiger Nutzung kannst du die vollständige Datei selbst in einem **privaten** Cloudordner, etwa Google Drive, ablegen und später durch einen aktuellen Export ersetzen. Keine automatische Synchronisation oder garantierter dauerhafter Zugriff: Dateizugriff hängt von tatsächlich verbundenen Diensten und Berechtigungen ab. Persönliche Listen nicht über öffentliche Links teilen.

## Freiwillige Spenden und Feedback

[MIT-Lizenz](../LICENSE), **Copyright (c) 2026 Stigliz81**. [Fremdlizenzen](../THIRD_PARTY_NOTICES.md) bleiben erhalten. Die Projektlizenz umfasst keine fremden Filmbilder oder Marken. Spenden sind freiwillig. PayPal, Bitcoin Mainnet, Litecoin Mainnet, Litecoin BEP20, USDC BEP20 und Binance-App-Link bleiben getrennt beschriftet; aktuelle Empfänger-/Zahlungsdienstannahme ist nicht geprüft.

Feedback: **stigliz1981@gmail.com**. Unter **Einstellungen & Daten → Feedback & Verbesserungsvorschläge** öffnet „E-Mail schreiben“ das lokale Mailprogramm mit dem Betreff „FilmKompass 1.0 – Feedback“. Die App versendet nichts automatisch und fügt keine Dateien oder Nutzerdaten bei.
