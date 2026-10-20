# Eigene Hintergründe

Vier Originalmotive wurden am 18.10.2026 mit dem integrierten Imagegen-Werkzeug erstellt, visuell auf die Motivvorgaben geprüft und als platzsparende JPEGs in `assets/backgrounds/` übernommen. Keine Internet-Ersatzbilder, keine übernommenen Filmplakate. Die PNG-Ausgaben bleiben separat im lokalen Generierungsordner; sie sind nicht für die Runtime erforderlich.

Gemeinsame Promptvorgabe: „Use case: stylized-concept. Original cinematic desktop application background, wide 16:9. Restrained charcoal/petrol, soft teal and amber lighting, calm central negative space, details toward edges. No recognizable real movies, actors, characters, brands, logos, copyrighted posters, text or watermark. Intended behind opaque dark application controls.“

Motivzusätze (eingesetztes Promptset, inhaltlich vollständig):

1. `gallery.jpg`: Dark elegant cinema gallery with abstract completely invented poster artworks; warm gallery spotlights; high-quality atmospheric interior photography style.
2. `archive.jpg`: Dark film archive, shelves of unbranded DVD cases and VHS tapes, metal film reels, restrained warm practical lighting, realistic cinematic interior.
3. `studio.jpg`: Vintage projector with subtle soft beam, curling blank filmstrips, unmarked clapperboard, polished photorealistic cinematic still life.
4. `cinema.jpg`: Quiet empty modern cinema, blue/petrol seating toward edges, warm amber aisle and wall lighting, somewhat brighter inviting atmosphere, no screen content, calm central wall.

AP04 verwendet die vier unveränderten Motive optional im bestehenden Kopfbereich hinter Titel, Aktionen und vier Kennzahlen. Kein zusätzliches Panoramaband. „Ohne Hintergrundbild“ bleibt Standard. Vier Auswahltexte entsprechen den Dateien oben; das letzte Motiv heißt „Helleres Kino in Blau/Petrol/Warmlicht“.

Proportionaler Beschnitt mit mittigem Schwerpunkt, starke Abdunkelung und dezente Petroltönung. Bedienelemente bleiben deckend und lesbar. Resize wird um 100 ms verzögert; höchstens drei gerenderte Größen sowie ein dekodiertes Motiv bleiben im Cache. Fehlende oder beschädigte Bilder führen zur dunklen Fläche. Bestehende AP02-Einstellungen „Einfarbig“ und „Kino · Blau & warmes Licht“ werden den aktuellen Auswahltexten zugeordnet. Die Einstellung bleibt lokal in settings.json; keine Tabelle wird durch ein Bild ersetzt. Ein zusätzlicher Farbverlauf wurde mangels Mehrwert ohne zusätzlichen Layoutaufwand weggelassen.

## AP05: flache lokale Ableitungen

Die vier Dateien unter `assets/backgrounds/banners/` (je 1672×280 Pixel) sind lokale Pillow-Zuschnittmontagen der oben dokumentierten Originale, keine neue Bildgenerierung. Jeweils drei proportionale Detailausschnitte werden mit 64 Pixeln Überlappung weich verbunden, als JPEG mit Qualität 90 gespeichert und erst in der Oberfläche abgedunkelt/getönt. Beim Studio wandern Projektor, Klappe und Filmrollen über die Breite; im Kino werden Sitzreihen und Warmlicht betont. Galerie und Archiv nutzen die detailreichen Seitenteile. Die vier AP02-Originaldateien bleiben bytegleich erhalten.

Die Laufzeit lädt die flache Ableitung, beschneidet sie proportional für die tatsächliche Kopfgröße und nutzt weiterhin 100 ms Debounce sowie höchstens drei Cachegrößen. Es entsteht keine zusätzliche Bannerhöhe. Auch maximiert wird ein Ausschnitt verwendet; einzelne Randdetails können dabei weiterhin entfallen. Fehlende oder defekte Ableitungen fallen auf den Dark Mode zurück. Vorhandene Auswahltexte und gespeicherte AP02/AP04-Einstellungen bleiben gültig; „Helleres Kino“ wird ebenfalls als bisheriges Kino-Motiv erkannt.
