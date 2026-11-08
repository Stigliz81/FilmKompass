# FilmKompass 1.1 – Onlinecover über fanart.tv

## Einrichtung

Unter **Einstellungen & Daten → Online Filmcover / Fanart.tv** einen persönlichen API Key von https://fanart.tv/get-an-api-key/ speichern und die Verbindung prüfen. **Der persönliche Key genügt allein; normale Nutzer benötigen keinen Project Key.** Die Schlüsselanzeige ist verdeckt. Der Schlüssel wird lokal in den privaten Einstellungen gespeichert, nicht verschlüsselt und nicht exportiert. Vollständige Profilsicherungen können ihn enthalten und dürfen nicht veröffentlicht werden.

Onlinecover bewusst aktivieren. Die Coverautomatik kann fehlende Cover der Bibliothek laden; Fortschritt, Pause/Abbruch und Fortsetzen sind verfügbar. Rechtsklick auf einen Titel beziehungsweise eine Karte → **Cover online suchen / ändern …** ermöglicht die Einzelzuordnung und Posterauswahl. Manuelle Bilder haben Vorrang und werden nicht ersetzt. Ohne Konfiguration funktioniert die übrige Anwendung vollständig weiter.

## Zuordnung und Grenzen

Vorhandene bestätigte externe IDs werden bevorzugt. Ohne ID sucht Wikidata anhand von Titel, Erscheinungsjahr und Film-/Serientyp. Nur eindeutige passende Treffer werden automatisch zugeordnet. Bei unklaren Treffern bleibt die Auswahl oder manuelle Eingabe erforderlich. IMDb, Wikidata, TVDB für Serien und bereits vorhandene TMDB-IDs werden unterstützt; es wird keine TMDB-API benutzt. Eine Moviepilot-ID wird niemals als fremde Datenbank-ID interpretiert.

Fanart.tv liefert `movieposter` beziehungsweise `tvposter`. Deutsche, danach englische und neutrale Poster werden bevorzugt; Likes und verfügbare Auflösung ordnen gleichsprachige Angebote. Gespeicherte Bilder nutzen die offizielle bigpreview-Variante. Nicht alle Titel besitzen IDs oder Poster. Fehlende Treffer werden nicht geschätzt.

## Cache, Netz und Datenschutz

Der private `fanart-cache` unter dem lokalen Appdatenordner hält IDs, Metadaten und Bilder getrennt von SQLite. Gecachte Bilder funktionieren offline. Positive API-Antworten können nach 90 Tagen bei einer erneuten Suche aktualisiert werden, fehlende Treffer nach einem Tag. Die Bildanzeige allein löst keine Netzabfrage aus; Automatik bleibt eine bewusste Einstellung.

Ein eigener Koordinator verwendet höchstens zwei Coverworker; Wikidata bleibt seriell. Fortschritt gelangt über die Queue in den Tk-Hauptthread. Timeouts, Verbindungsfehler, HTTP 401/404/429 und Retry-After werden behandelt. Abbruch wartet höchstens noch laufende begrenzte Anfragen ab. Erneuter Start überspringt bereits gespeicherte Cover. Bibliotheks- und Moviepilot-Listenjobs bleiben getrennt.

API-Keys werden über HTTPS-Header übertragen, nicht in URL-Parametern oder Logs. Öffentliche Pakete enthalten keine echten Schlüssel, privaten Einstellungen oder Fanart-Poster. Bildrechte und die Bedingungen von https://fanart.tv/ beachten. **Filmcover werden über fanart.tv bereitgestellt.**

## Optionale Entwicklerkonfiguration

Bestehende Project-Konfigurationen funktionieren zusätzlich: zuerst `FANART_TV_PROJECT_KEY`, andernfalls die ignorierte `fanart.local.json` im Projektordner beziehungsweise neben der EXE. Struktur siehe `fanart.local.example.json`. `api-key` transportiert den optionalen Project Key, `client-key` den persönlichen Key. Es wird kein echter Project Key mitgeliefert. Ein in einer Desktopanwendung verteilter Schlüssel wäre auslesbar; es wird keine Geheimhaltung durch Verschleierung behauptet.

## Teststand der Veröffentlichung

Die Schlüsselvarianten und Fehlerfälle wurden mit simulierten Antworten geprüft. Frühere echte Project-Key-Anfragen bestätigten Film-/Serienposter. Für AP16.09 war kein gültiger persönlicher Testkey verfügbar: ein Live-Test des persönlichen Keys allein wird ausdrücklich nicht behauptet. Die finale EXE wurde mit isolierten Testdaten und ohne Schlüssel geöffnet; die Einrichtung ist erreichbar. Weitere Ergebnisse: [Startanleitung](V1.1_START.md), [Abschluss](AP16.09_FINAL_RELEASE.md).
