# AP16.01 – öffentliche Moviepilot-Filmlisten

Prüfstand: 7. November 2026. Implementierung im lokalen Quellcode, kein neuer EXE-Build und keine Veröffentlichung.

## Ergebnis und Abrufregeln

Die untersuchten öffentlichen Listen lassen sich per HTTPS ohne Anmeldung oder Browserlaufzeit zuverlässig auslesen. Wie beim vorhandenen Bewertungsdownload stehen die strukturierten Daten im `__NEXT_DATA__`-Block des normalen Seiten-HTML unter `props.initialProps.pageProps`.

Die [Nutzungsbedingungen](https://www.moviepilot.de/pages/terms) nennen in Ziffer 3.5 private, nicht-kommerzielle Nutzung einschließlich Abrufen und Speichern im Rahmen der Zweckbindung. Ziffer 3.3 schützt Inhalte, Ziffer 3.6 untersagt beeinträchtigende Eingriffe. Daraus wird hier der auf einzelne Listen begrenzte private Gebrauch abgeleitet, keine allgemeine Freigabe zur Weiterveröffentlichung fremder Listen oder Medien. Rechte an fremden Beschreibungen und Bildern werden nicht übernommen.

Die am Prüftag abgerufene [robots.txt](https://www.moviepilot.de/robots.txt) sperrt unter anderem `/lists/*`, `/api/` und `/liste/*/comments/`, nicht die öffentliche Ansicht `/liste/<slug>`. Sie enthält für diese Ansicht keine konkrete Frequenzangabe. Der Import nutzt ausschließlich deren HTML-Seiten, sequenziell mit einer Sekunde Pause zwischen Folgeseiten, maximal 10.000 Quellpositionen pro einzelnem Auftrag. Es gibt keinen Hintergrundabgleich und keine Stapelverarbeitung. HTTP 401, 403, 404 oder 429 beendet den Abruf unmittelbar. Nur vorübergehende Netzwerk-/Serverfehler werden höchstens dreimal versucht. Zugriffssperren werden nicht umgangen. Diese Regeln und die Seitenstruktur können sich künftig ändern.

## Daten und Vollständigkeit

- Listenname/ID: `title`, `id`; Öffentlichkeit: `public`.
- Gesamtumfang: `totalListItemCount`; Pagination: `page`, `itemsPerPage`, derzeit 25.
- Eintragsreihenfolge: Reihenfolge von `listItems`, fortgesetzt über die Seiten. `itemId` ist die ID des **Listeneintrags**, nicht die Film-ID.
- Film-/Serienreferenz: `itemType` und `itemData.type`, Titel aus `itemData.title`, Jahr aus `productionYear`, Film-/Serien-ID aus `itemData.id`, URL aus `itemData.path`.
- Die öffentliche Seitennavigation der 100er-Liste verwendet `?page=2&itemsPerPage=25` bis Seite 4. Dynamisches Nachladen ist für die untersuchten Listen nicht erforderlich.
- Jede Seite muss die erwartete Anzahl liefern. Listenidentität, Gesamtzahl und Änderungsstand müssen gleich bleiben. Wiederholte Listeneintrags-IDs führen zum Abbruch. Eine Filmreferenz darf an mehreren verschiedenen Quellpositionen vorkommen.
- Nicht-mediale Einträge, etwa Personen, werden gezählt und ausdrücklich als ausgelassen gemeldet. Die ursprünglichen Positionen bleiben erhalten. Fehlende Jahre werden leer gespeichert und gemeldet. Fehlende Pflichtdaten eines Films/einer Serie führen zum Abbruch statt zu einem stillen Teilimport.
- Eine teilweise geladene Liste wird nicht gespeichert. Erneuter Import derselben URL ersetzt nach Bestätigung nur deren lokale Kopie in einer Transaktion.

## Bedienung und Speicherung

Im Tab **Filmlisten** eine öffentliche `https://www.moviepilot.de/liste/…`-URL eingeben und **Liste importieren** wählen. Über die Auswahl lassen sich gespeicherte Listen öffnen. **Excel / CSV …** exportiert die ausgewählte lokale Liste. **Lokal entfernen** entfernt sie nach Bestätigung.

Die beiden additiven Tabellen `movie_lists` und `movie_list_entries` liegen in der vorhandenen `manager.sqlite`. Sie besitzen keine Fremdschlüssel zu persönlichen Bewertungen. Bewertungs-, Notiz-, Staffel-, Import- und Änderungsdaten werden beim Listenimport nicht geschrieben. Die vorhandene SQLite-Sicherung umfasst auch die neuen Tabellen. „Bibliothek zurücksetzen“ betrifft weiterhin die Bewertungsbibliothek; „Alle lokalen Appdaten löschen“ umfasst wie bisher die gesamte Datenbank.

Der Listenexport enthält Position, Typ, Titel, Erscheinungsjahr, Moviepilot-ID, Moviepilot-URL, Listenname und Listen-URL. Reihenfolge und Quelladresse werden erhalten. XLSX speichert Position und vorhandenes Jahr numerisch, Referenz-IDs und Titel als Text. CSV ist UTF-8 mit BOM und Semikolon. CSV-Text, der als Excel-Formel interpretiert werden könnte, erhält ein führendes Apostroph. Es werden keine persönlichen oder fremden Bewertungswerte als eigene Bewertungen exportiert.

## Gezielte Prüfungen

Live geprüft, alle mit erfolgreicher lokaler Speicherung und XLSX-/CSV-Export in isolierter Testdatenbank:

| Öffentliche Liste | Quellpositionen | Importierte Filme/Serien | Seiten |
| --- | ---: | ---: | ---: |
| [Top-10-Liste-DrBlues](https://www.moviepilot.de/liste/top-10-liste-drblues-drblues) | 10 | 10 | 1 |
| [100 Filme, die man kennen sollte](https://www.moviepilot.de/liste/100-filme-die-man-kennen-sollte-teo) | 100 | 100 | 4 |
| [Meine 10 emotional intensivsten Serien](https://www.moviepilot.de/liste/meine-10-emotional-intensivsten-serien-codebreaker) | 10 | 10 | 1 |
| [Gewinnspiele powered by MP](https://www.moviepilot.de/liste/liste-gewinnspiele-powered-by-mp-leinzi) | 8 | 7; eine Person ausgelassen | 1 |

Die 100er-Liste beginnt mit „Nosferatu, eine Symphonie des Grauens“ und endet mit „Inception“. Seitenübergänge wurden gegen die Quellreihenfolge geprüft. Die kleine Filmliste beginnt mit „Easy Rider“ und endet mit „Papillon“, die Serienliste mit „Breaking Bad“ bzw. „One Piece“.

Automatisiert bestanden: acht neue gezielte Tests, insgesamt 70 Tests einschließlich bestehender Bewertungs-, Import-, Export- und Schutztests. Abgedeckt sind URL-Grenzen, Pagination, Reihenfolge, Film-/Serientypen, fehlende Jahre, andere Eintragstypen, unvollständige/geänderte/wiederholte Seiten, private Listen, sofortiger Abbruch bei Zugriffsbeschränkung, wiederholter Import, Transaktions-Rollback, unveränderte persönliche Daten und beide Exportformate einschließlich Überschreibschutz.

Native Quellcode-GUI mit isolierten Daten geprüft: Tab öffnen, lokale Liste anzeigen, fremde URL mit Fehlermeldung ablehnen und kleine Liste erneut herunterladen/speichern. Nativer Speicherdialog geöffnet. Das zuverlässige Ausfüllen dieses Dialogs war mit dem Computer-Use-Adapter nicht möglich; der vollständige native Speichervorgang wurde nicht abgenommen. Ein nativer Resize-Versuch änderte die Fenstergröße nicht und zählt nicht als erfolgreiche Resize-Abnahme. Keine OneDir-/EXE-Prüfung, da ein neuer Build nicht freigegeben ist. Keine Excel-Desktop-Abnahme.

Zusätzliche technische Tk-Integration mit synthetischen Daten bestanden: sechs Tabs, Worker-Erfolg, Worker-Fehler mit Erhalt der vorherigen Liste, beide Exportaktionen und Geometrieaufrufe 980×580 sowie 1360×810. Diese programmatischen Geometrieaufrufe sind keine native Resize-Abnahme. Fünf erzeugte XLSX-Dateien wurden zusätzlich mit einem unabhängigen Leser (openpyxl, nur Testwerkzeug; keine neue Programmabhängigkeit) erfolgreich geöffnet und auf Zeilenzahl und numerische Positionszellen geprüft. Abschließende Regression: 70/70 Tests bestanden.

## Dateien

- `moviepilot_lists.py`: begrenzter HTTPS-Import, Datenprüfung, separate Tabellen und Listenexport.
- `movie_lists_view.py`: eigener GUI-Bereich.
- `moviepilot_manager.py`: Tab und Einbindung in vorhandenen Worker-/Queue-Ablauf.
- `tests/test_moviepilot_lists.py`: gezielte isolierte Tests.
- `package_release.py`: neue benötigte Quellen in der bestehenden Allowlist, ohne Paketbau.
- `README.md`: lokaler Entwicklungsstand und Verweis auf diese Anleitung.
