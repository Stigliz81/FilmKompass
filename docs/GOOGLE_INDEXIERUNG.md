# FilmKompass – Google-Indexierung nach AP16.10.2

Die technische Erreichbarkeit einer Seite bestätigt weder ihre Google-Indexierung noch eine bestimmte Platzierung. Eine öffentlich lesbare Google-Verifizierungsdatei bestätigt ihrerseits keinen erfolgreichen authentifizierten Zugriff auf die Property.

Der authentifizierte Search-Console-Status konnte in diesem Arbeitspaket nicht ausgelesen werden: Die Browseranbindung brach beim Öffnen mit „Detached while handling command“ ab. Es wurde keine Sitemap eingereicht und keine Indexierung beantragt. Historische Statusangaben werden nicht als aktuelle Ergebnisse übernommen.

## Wenige manuelle Schritte

1. In der [Google Search Console](https://search.google.com/search-console) die vorhandene Property `https://stigliz81.github.io/FilmKompass/` auswählen. Falls eine passende Domain-Property verwendet wird, dort dieselben vollständigen URLs prüfen.
2. Unter **Sitemaps** den tatsächlichen Verarbeitungsstatus von `https://stigliz81.github.io/FilmKompass/sitemap.xml` ansehen. Falls noch nicht eingereicht oder nach einem Fehler erneut erforderlich, genau diese XML-Adresse einreichen. Nicht die HTML-Startseite als Sitemap einreichen.
3. Unter **URL-Prüfung** die Startseite sowie die Export- und KI-Anleitung prüfen. Indexstatus und von Google gewählte kanonische URL lesen. Bei Bedarf einen Live-Test durchführen und für die aktualisierte Startseite **Indexierung beantragen** wählen.
4. Später den tatsächlichen Status erneut prüfen. Ein erfolgreicher Live-Test oder eine Anfrage garantiert keine Indexierung und keine Platzierung.

Öffentliche Inhaltsseiten: Startseite, `moviepilot-bewertungen-exportieren.html`, `ki-filmliste-analysieren.html`, `datenschutz.html`. Die bestehende Verifizierungsdatei `google2dfe94ecf53bd9d7.html` bleibt unverändert; sie ist keine Inhaltsseite für die Sitemap. Keine zusätzliche robots.txt im Projekt-Unterpfad anlegen und keine anderen GitHub-Pages-Projekte ändern.

Offizielle Anleitung: [Google URL-Prüftool](https://support.google.com/webmasters/answer/9012289?hl=de), [erneutes Crawlen anfragen](https://developers.google.com/search/docs/crawling-indexing/ask-google-to-recrawl).
