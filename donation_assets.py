"""Current supplied originals and QR-decoded public payment destinations."""
from pathlib import Path
from PIL import Image, ImageOps

PAYPAL_URL = "https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=stigliz1981%40gmail.com&currency_code=EUR"
BEP20 = "0x181536e0cc46c18200324e142a15852edefbff17"
DONATIONS = {
    "PayPal": dict(file="paypal.jpg", bounds=(200,188,1072,1062), network="PayPal · Zahlungslink",
                   addresses=(("PayPal-Link", "https://www.paypal.com/qrcodes/p2pqrc/M7QJQJYSHXGAU"),), crypto=False),
    "Bitcoin": dict(file="btc.png", bounds=(325,437,947,1060), network="Bitcoin Mainnet (Native SegWit)",
                    addresses=(("BTC", "bc1qgk2hkpqsazshjkrfk3n4ah66z0rmmwpj95nav0"),), crypto=True),
    "Litecoin · Mainnet": dict(file="ltc-mainnet.jpg", bounds=(400,346,1038,984), network="Litecoin Mainnet",
                    addresses=(("LTC", "LPX49WT3wVUwhPyozQzZ2PW34g2e7BGWPv"),), crypto=True),
    "Litecoin · BEP20": dict(file="ltc-bep20.png", bounds=(325,489,947,1112), network="BNB Smart Chain (BEP20)",
                    addresses=(("LTC (BEP20)", BEP20),), crypto=True),
    "USDC · BEP20": dict(file="usdc.png", bounds=(325,489,947,1112), network="BNB Smart Chain (BEP20)",
                    addresses=(("USDC (BEP20)", BEP20),), crypto=True),
    "Binance App": dict(file="binance.png", bounds=(251,555,801,1105), network="Binance Pay · App-Zahlungslink (kein Blockchain-Netzwerk)",
                    addresses=(("App-Link", "https://app.binance.com/qr/dplkc2c1222b1d7a49efb4edb5ce9d73b2eb"),), crypto=False),
}


def qr_preview(folder: Path, choice: str, size: int) -> Image.Image:
    config = DONATIONS[choice]
    with Image.open(folder / config["file"]) as original:
        image = original.convert("RGB").crop(config["bounds"])
    # Add a quiet zone, especially for the tightly cropped Binance Pay original.
    image = ImageOps.expand(image, border=max(12, image.width // 12), fill="white")
    image = ImageOps.contain(image, (size, size), Image.Resampling.NEAREST)
    result = Image.new("RGB", (size, size), "white")
    result.paste(image, ((size-image.width)//2, (size-image.height)//2))
    return result


def copy_address(window, address: str, feedback):
    window.clipboard_clear()
    window.clipboard_append(address)
    feedback.set("Adresse kopiert")
