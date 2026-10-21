# FilmKompass 1.0 – Windows-Kompatibilität des veröffentlichten Pakets

Stand: 21.10.2026. Diese Untersuchung betrifft ausschließlich die bereits veröffentlichte portable EXE aus Release v1.0.0. Es wurde kein neuer Build erstellt. Die ZIP enthält 25.387.531 Bytes, also rund 25,4 MB bzw. 24,2 MiB.

| Betriebssystem, jeweils x64 | Ergebnis für dieses Paket |
| --- | --- |
| Windows 11 | **Getestet:** Die veröffentlichte Runtime wurde mit isolierten Beispieldaten erfolgreich gestartet und in AP12/AP13 nativ bedient. Keine vollständige Abnahme aller Windows-11-Versionen oder Hardwarekonfigurationen. |
| Windows 10 | **Technisch kompatibel laut grundlegenden Voraussetzungen, nicht praktisch getestet.** Python, Bootloader und die untersuchten nativen Komponenten sprechen dafür. Ein erfolgreicher Start auf Windows 10 wird ausdrücklich nicht behauptet. |
| Windows 8.1 | **Nicht bestätigt.** Die dokumentierte Python-Untergrenze allein ist kein Beleg für den gesamten konkreten Build mit Pillow, Tcl/Tk, OpenSSL, Systembibliotheken und aktuellen HTTPS-Zertifikaten. Kein Praxistest; keine Bewerbung als unterstütztes Zielsystem. |
| Windows 8 | **Nicht unterstützt:** unterhalb der dokumentierten Windows-Untergrenze von Python 3.13. Kein Legacy-Build. |
| Windows 7 | **Nicht unterstützt:** unterhalb der dokumentierten Windows-Untergrenze von Python 3.13. Kein Legacy-Build. |

## Untersuchte Laufzeit

- Gebündelte Python-DLL: **CPython 3.13.16**, AMD64. Version direkt aus der veröffentlichten Laufzeitdatei geprüft.
- **PyInstaller 6.22.3** in der zugehörigen Buildumgebung; die ausführbare `.text`-Sektion des EXE-Bootloaders stimmt mit deren `runw.exe` überein. Die PyInstaller-Dokumentation nennt Windows 8 und neuer als Grundvoraussetzung; Python und alle weiteren Abhängigkeiten können diese Grenze erhöhen.
- **Pillow 11.3.0**, Versionskonstante direkt aus dem eingebetteten Modul `PIL._version` gelesen. Native Bildmodule und Codec-DLLs wurden mituntersucht. Historische Plattformmeldungen anderer Pillow-Versionen gelten nicht als Test dieses Pakets.
- **Tcl/Tk 8.6.15**, `_tkinter.pyd` und zugehörige Tcl-/Tk-Daten sind gebündelt.
- **OpenSSL 3.5.9**, `_ssl.pyd`, `libssl-3.dll` und `libcrypto-3.dll` sind gebündelt; der HTTPS-Workflow benötigt weiterhin funktionierende Netzverbindung und vertrauenswürdige Zertifikate. Die Windows-Zertifikatsumgebung und Systemupdates können den Abruf beeinflussen. Eine reine Programmstartprüfung bestätigt noch keinen vollständigen Online-Download.
- **73 native PE-Dateien** untersucht, alle AMD64. Python importiert unter anderem `api-ms-win-core-path-l1-1-0.dll`, `PathCchCombineEx`, `PathCchSkipRoot`, `GetSystemTimePreciseAsFileTime` und `AddDllDirectory`. Weitere Standardimporte betreffen u. a. Kernel32, User32, GDI32, Winsock, BCrypt und Crypt32.
- Visual-C-Runtime `VCRUNTIME140.dll`, `ucrtbase.dll` und zahlreiche UCRT/API-Set-Dateien sind Bestandteil des OneDir-Pakets. Das ersetzt weder sämtliche Betriebssystem-DLLs noch eine Prüfung auf einem älteren, ungepatchten Windows. Die im PE-Header eingetragene Subsystemversion allein beweist keine Betriebssystemkompatibilität.

Ein vorhandenes Windows 11 wurde nicht als Windows-10-Test ausgegeben. Für Windows 10/8.1/8/7 wurde keine geeignete isolierte Zielumgebung getestet. Es wurden keine virtuellen Maschinen neu installiert und keine produktiven Nutzerdaten verwendet. Der vollständige `_internal`-Ordner muss neben der EXE erhalten bleiben. Eine separate Python-Installation ist nicht erforderlich.

Die Aussage zur technischen Lauffähigkeit ist von Microsofts Sicherheitsunterstützung einer Windows-Version zu trennen. Der allgemeine Support für Windows 10 endete am 14.10.2025; gesonderte ESU-/LTSC-Regelungen können abweichen. Für den alltäglichen Einsatz sollte ein mit Sicherheitsupdates versorgtes System verwendet werden.

## Quellen und Nachweisgrenzen

- [Python 3.13 unter Windows](https://docs.python.org/3.13/using/windows.html) – dokumentierte Windows-Untergrenze.
- [PyInstaller-Anforderungen](https://pyinstaller.org/en/stable/requirements.html) – Bootloader-/Buildvoraussetzungen.
- [Pillow-11.3.0-Plattformhinweise](https://github.com/python-pillow/Pillow/blob/11.3.0/docs/installation/platform-support.rst) – Plattformtests sind versionsbezogen; keine pauschale Zusage für dieses Paket.
- [Microsoft: Windows-10-Support](https://support.microsoft.com/en-us/windows/windows-10-support-has-ended-on-october-14-2025-2ca8b313-1946-43d3-b55c-2b95b107f281).

Die tatsächlichen gebündelten Dateiversionen, PE-Importe, Hashvergleiche und Testgrenzen wurden lokal protokolliert. Analyseergebnisse sind keine umfassende Abnahme aller Windows-Ausgaben.
