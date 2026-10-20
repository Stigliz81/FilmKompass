# AP03: Genreillustrationen und eigene Titelbilder

Produktversion 1.0. Keine automatische Filmcover-Erfassung, keine externen Film-APIs oder Schlüssel.

## Eigene Illustrationen

14 Genremotive und ein neutrales Standardmotiv wurden tatsächlich mit dem integrierten Imagegen-Werkzeug erzeugt, visuell geprüft und als 400×600-JPEGs unter `assets/genres/` gespeichert. Keine erkannten Filmfiguren, Markenlogos, Filmtitel oder übernommenen Poster. Einheitlicher Stil: dunkles Petrol/Blau, dezente warme Akzente, cineastische 2:3-Illustrationen. Das vollständige Promptset und die Dateipfade stehen in [GENRE_ART.json](GENRE_ART.json). Die Original-PNGs verbleiben im lokalen Generierungsordner; für die portable Anwendung genügen die verkleinerten, metadatenfreien JPEGs.

| Datei | Motivgruppe |
|---|---|
| `action.jpg` | Action – dynamische Straße/Stadt |
| `scifi.jpg` | Science Fiction – Raumschiff/Planet |
| `fantasy.jpg` | Fantasy – erfundene Burg/Bergpfad |
| `drama.jpg` | Drama – nachdenkliche Fensterszene |
| `thriller.jpg` | Thriller – spannungsvolle Gasse |
| `crime.jpg` | Krimi – Ermittlungsstillleben |
| `horror.jpg` | Horror – unheimliches Waldhaus |
| `comedy.jpg` | Komödie – Theatermasken |
| `romance.jpg` | Romanze – Begegnung/Brücke |
| `adventure.jpg` | Abenteuer – Kompass/Tal |
| `animation.jpg` | Animation – fantasievolle Miniaturstadt |
| `documentary.jpg` | Dokumentation – Kamera/Landschaft |
| `western.jpg` | Western – Reiter/Canyon |
| `history.jpg` | Historie und Krieg – Helm/Festung |
| `neutral.jpg` | Unbekanntes Genre – Filmrolle |

Die nur lesende Bestandsanalyse ergab 157 unterschiedliche Genrebezeichnungen. Die Quelle bleibt unverändert; `genre_art.TOKENS` und `PRIORITY` steuern ausschließlich die Illustration. Gruppenzuordnung über normalisierte Genrebegriffe: beispielsweise Film/Serie bei Science Fiction gleich, Zombie → Horror, Detektiv → Krimi, Coming of Age/Melodram → Drama. Keine Änderung an Datenbank oder Exportgenres.

**Reihenfolge bei Mehrfachgenres:** Dokumentation, Animation, Horror, Science Fiction, Fantasy, Western, Historie/Krieg, Thriller, Krimi, Action, Abenteuer, Komödie, Romanze, Drama. Erster Treffer gewinnt; unbekannt → neutral. Dokumentation/Animation beschreiben eine spezifische Darstellungsform, danach folgen spezifische Motive vor allgemeinen Kategorien. Ein Titel verwendet genau ein Grundmotiv, unabhängig von Film/Serie. Der Film-/Serienbadge wird nur auf der Miniaturkarte als Tk-Label überlagert; keine zweite Bildsammlung.

## Anzeige und Speichergrenzen

Listenansicht: eigene schmale Bildspalte links, 20×30-Pixel-Motive, Zeilenhöhe mindestens 36. Nur Zeilen am aktuellen Sichtbereich halten Bildreferenzen; Scrollen lädt verzögert nach. Titel und sechs Kernspalten bleiben erhalten, nur Genre wächst mit dem Fenster.

Miniaturansicht: 156×234-Pixel-Bilder, Titel mit Umbruch, Jahr, Note, Genres und Typbadge. Gemeinsame gefilterte/sortierte Datenliste, maximal 6/12/18/24 Karten pro Seite, Standard 12. Adaptive Spalten und vertikale Scrollleiste. Filter-/Suchänderungen starten auf Seite 1, ungültige Seiten werden geklemmt, Leerstand zeigt „Seite 1 von 1“. Ansicht und Seitengröße werden gespeichert. Der begrenzte Cache hält höchstens 48 wiederverwendbare Tk-Fotos; aktive Widgets halten zusätzlich nur ihre aktuellen Referenzen. Keine Neuberechnung bei jedem Karten-Scrollereignis.

## Eigene Bilder

Rechtsklick auf Listenzeile oder Karte: lokale Datei wählen, direkte HTTPS-Bildadresse eingeben oder eigene Zuordnung entfernen. Priorität: eigenes gültiges Titelbild → Genreillustration → neutrales Motiv. JPG, PNG und WebP werden nach tatsächlichem Dateiformat geprüft, keine SVG/GIF/aktiven Inhalte. Grenze 10 MiB und 20 Millionen Pixel; Orientierung berücksichtigt, lokale JPEG-Kopie höchstens 900×1350, Metadaten entfernt. Die Quelldatei wird weder verschoben noch verändert.

Private Kopien liegen unter `%LOCALAPPDATA%/MoviepilotManager/user-images/`. `user_images` ist eine additive SQLite-Tabelle mit Fremdschlüssel auf die bestehende URL-/lokale Identität. Eine eindeutige spätere URL-Übernahme erhält die Bildzuordnung; gleichnamige Werke werden nicht anhand des Titels allein verbunden. Keine Bildspalten im Sechs-Spalten-Export.

Das Entfernen löscht die Zuordnung und zeigt wieder das Genremotiv. Bildbytes bleiben für vorhandene SQLite-Backups erhalten; auch ein Bibliotheksreset entfernt die Zuordnungen, erhält aber vorhandene Bildbytes. Der ausdrücklich bestätigte vollständige Appdatenreset entfernt den eigenen Bilderordner unter denselben Pfad-/Linkschutzregeln. SQLite-Sicherungen enthalten Zuordnungen, keine Bilddateien: für einen PC-Wechsel den gesamten Appdatenordner separat sichern.

## Manueller HTTPS-Abruf

Ausschließlich ausdrücklich eingegebene direkte Bildadresse. Keine Suche, Authentifizierung, Cookies, regulären Browserprofile oder automatischen Massenabrufe. Keine Moviepilot-/TMDB-/OMDb-Integration. Ein kurzer Hinweis verlangt passende Nutzungsrechte; es wird keine Rechtefreigabe durch einen Haftungsausschluss behauptet.

HTTPS, Standardport 443, keine Zugangsdaten im URL. Alle aufgelösten IPs müssen global öffentlich sein; lokale/private/reservierte und IPv4-in-IPv6-Ziele werden geprüft. Die geprüfte IP wird für die Verbindung festgehalten, TLS-Zertifikat und SNI weiterhin gegen den ursprünglichen Hostnamen geprüft. Jede der höchstens drei Weiterleitungen wird erneut geprüft. Keine Übernahme von Cookies. 8 Sekunden je Netzwerkoperation, zusätzlich ungefähr 25 Sekunden Gesamtablaufprüfung zwischen Lese-/Weiterleitungsschritten; System-DNS und ein bereits laufender Lesevorgang können darüber hinausgehen. Größenlimit auch ohne Content-Length. Download im vorhandenen Worker, SQLite-Zuordnung im Hauptthread. Tatsächliches Bildformat wird nach Download erneut geprüft.

Tests verwenden kontrollierte DNS-/HTTP-Antworten; kein fremdes Live-Bild ohne konkrete Nutzerwahl geladen. Die Implementierung ist keine Zusage, dass jeder Bildhost dauerhaft erreichbar ist.

## Hintergrundentscheidung

Die ttk-Tabellen und Bedienflächen sind opak. Ein Bild hinter der gesamten vorhandenen Widgetfläche wäre größtenteils verdeckt; echte Bildtransparenz würde einen erheblichen Ersatzumbau verlangen. Deshalb wird die ausdrücklich erlaubte Rückfalllösung verwendet: **einfarbiger Dark Mode, Panoramaband entfernt**. Keine Vollflächenfunktion oder künstliche Transparenz behauptet. AP02-Motive und ältere Einstellungen bleiben erhalten, werden jedoch nicht angezeigt.
