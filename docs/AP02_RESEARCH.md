# AP02: Cover, Anmeldung und Importabgleich

> Historischer AP02-Prüfstand. AP03 ergänzt eine Miniaturansicht mit eigenen Genreillustrationen und optionalen ausdrücklich zugewiesenen Benutzerbildern. Die Entscheidung gegen automatische fremde Posterdownloads bleibt bestehen.

Prüfstand 18.10.2026. Technische Beobachtungen sind keine Rechtefreigabe.

## Cover

Eine aktuelle öffentliche Filmprofilseite lieferte 48 Einträge mit je einem eingebetteten `poster`-Objekt. Dieses enthält ID, Dateiname und einen relativen Moviepilot-Bilderseitenlink, zusammen mit dem jeweiligen Titelobjekt. In dieser Stichprobe fehlte kein Poster-Verweis. Das Objekt liefert weder eine bestätigte direkt nutzbare Bilddatei-URL noch Pixelmaße. Eine Bilderseite ist keine Bilddatei. Zuverlässige CDN-Varianten, Bildgrößen, tatsächliche Bildverfügbarkeit und fehlende Bilder sind damit nicht bestätigt. Keine Detail- oder Bildmassenabfragen durchgeführt.

Die [aktuellen Moviepilot-Nutzungsbedingungen, Abschnitt 3.3](https://www.moviepilot.de/pages/terms) schützen auch Abbildungen und erlauben deren sonstige Nutzung nicht pauschal. Eine passende Rechtefreigabe für den automatischen Coverabruf wurde nicht festgestellt. Daher kein automatischer Abruf, kein Covercache und keine Miniaturansicht. Keine fremden Cover im Paket. Die MIT-Lizenz des Managers umfasst keine fremden Filmbilder. Mögliche spätere Alternative: ausdrücklich lizenzierte Bildquelle oder vom Nutzer bereitgestellte, zur Nutzung freigegebene Bilder; derzeit nicht implementiert.

## Anmeldung

- **Aktuell bestätigt:** Eine öffentliche Filmprofilseite ist über den vorhandenen urllib-HTTPS-Pfad ohne Anmeldung/Cookies erreichbar (48 Einträge). Kein erneuter vollständiger Profilabruf.
- **Codepfad:** Der normale Abruf liest keine Browserprofile oder Browsercookies und speichert keine Zugangsdaten. Eine vorhandene oder abgelaufene Anmeldung im normalen Browser beeinflusst diesen Weg nicht.
- **Private Profile:** Der ausdrückliche `isPrivate`-Status führt zum Abbruch, mit kontrollierter Antwort getestet. Kein privates Nutzerkonto live untersucht. Weitere Zugriffssperren/fehlende Strukturdaten führen ebenfalls zum Abbruch. Es gibt keine Umgehung und keinen automatischen Login-Fallback.
- **Optionaler Adapter:** Playwright nutzt nur ein eigenes persistentes Appprofil. Eine fehlende/abgelaufene Sitzung kann manuelle Anmeldung in diesem separaten Browser erfordern; kein aktueller Live-Test solcher Sitzungen oder DOM-Layouts. Nicht Bestandteil der portablen EXE. Einrichtung über `exporter_einrichten_windows.bat`, benötigt Playwright und dessen Chromium; der normale HTTPS-Download benötigt beides nicht.
- **Frische Installation:** Startet mit leerer Bibliothek und braucht für öffentliche HTTPS-Profile keine vorbereitete Sitzung. Gebündelte Runtime und isolierter Erststart werden separat im Prüfbericht dokumentiert.

## Meldung „1702 neu“

Der unverändert und ausschließlich lesend untersuchte lokale Importverlauf enthält zunächst `(1702 neu, 0 geändert, 0 unverändert)`, danach `(0 neu, 0 geändert, 1702 unverändert)`. Das entspricht einem Erstimport mit anschließendem identischem Folgeimport. Ein aktueller Zählfehler ist damit nicht belegt; der konkrete frühere Benutzerablauf lässt sich nachträglich nicht vollständig rekonstruieren. Python und EXE verwenden standardmäßig denselben LOCALAPPDATA-Ordner. Ein anderer Datenordner, eine leere Datenbank oder andere URLs können neue Identitäten ergeben; dies wurde nicht als Ursache dieses Falls behauptet.

Gezielte Tests prüfen Erstimport, Folgeimport, neuen Titel, Bewertungsänderung, unveränderte und fehlende Titel in einer vorhandenen isolierten Datenbank. Der URL-basierte Vollständigkeitsschutz bleibt bestehen. Abschlussmeldungen nennen zusätzlich fehlende Titel. Nicht verfügbare Titel werden verborgen, nicht physisch gelöscht.

## Sechs-Spalten-Import

Exakte Kombination aus Typ, Titel (ohne Beachtung der Großschreibung) und Jahr. Ein eindeutiger vorhandener Treffer wird aktualisiert, mehrere Treffer führen zum vollständigen Abbruch vor Änderungen. Unbekannte Kombinationen erhalten einen stabilen lokalen Schlüssel ohne erfundenen Weblink. Fehlendes Jahr wird nicht zur unsicheren Verknüpfung mit einem bestehenden Webtitel genutzt. Zwei gleichnamige Werke desselben Typs und Jahres sind ohne weitere Identität nicht unterscheidbar: mehrfach vorkommende Kombinationen im Sechs-Spalten-Import werden abgelehnt. Ein einzelner gleichnamiger Datensatz kann diese Unterscheidung grundsätzlich nicht leisten; bei solchen Titeln URL-Export oder SQLite-Sicherung verwenden.

Ein späterer URL-Import übernimmt einen eindeutig passenden lokalen Schlüssel in die echte URL und erhält persönliche Angaben/Staffeln. Bei Mehrdeutigkeit wird abgebrochen. Ohne URLs importierte Dateien sind immer ergänzend: fehlende Titel werden nicht verborgen, weil es eine gefilterte Datei sein kann. Das schützt die bestehende Bibliothek. Sechs-Spalten-Dateien sind daher kein vollständiger Ersatz für die SQLite-Sicherung.
