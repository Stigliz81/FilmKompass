"""Central product/build metadata; never incremented by tests or builds."""
APP_VERSION = "1.0"
BUILD_NUMBER = 2
DISPLAY_VERSION = APP_VERSION
PRODUCT_NAME = "FilmKompass"
SHORT_NAME = PRODUCT_NAME
PUBLIC_NAME = PRODUCT_NAME
APP_TITLE = f"{PUBLIC_NAME} {DISPLAY_VERSION}"
EXE_STEM = PRODUCT_NAME
ICON_PNG = "assets/filmkompass.png"
ICON_ICO = "assets/filmkompass.ico"
SUBTITLE = "Excel-/CSV-Export- und Archivtool für deine Moviepilot-Bewertungen."
INDEPENDENCE_NOTICE = "Unabhängiges Projekt, nicht offiziell mit Moviepilot verbunden."
WINDOWS_PRODUCT_VERSION = tuple(map(int, APP_VERSION.split('.'))) + (0, 0)
WINDOWS_FILE_VERSION = WINDOWS_PRODUCT_VERSION[:3] + (BUILD_NUMBER,)
FILE_VERSION = '.'.join(map(str, WINDOWS_FILE_VERSION))
PACKAGE_STEM = f"{PRODUCT_NAME}-{APP_VERSION}"


def windows_version_info():
    """Render the public resource template from the same configuration as the GUI."""
    from pathlib import Path
    if not 1 <= BUILD_NUMBER <= 65535:
        raise ValueError('Buildnummer muss zwischen 1 und 65535 liegen.')
    return Path(__file__).with_name('windows_version_info.txt').read_text(encoding='utf-8').format(
        file_tuple=WINDOWS_FILE_VERSION, product_tuple=WINDOWS_PRODUCT_VERSION,
        file_version=FILE_VERSION, product_version=APP_VERSION, title=APP_TITLE, product_name=PUBLIC_NAME, original_filename=EXE_STEM+".exe")


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description='Windows resource from central version metadata')
    parser.add_argument('output', type=Path)
    target = parser.parse_args().output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(windows_version_info(), encoding='utf-8')
