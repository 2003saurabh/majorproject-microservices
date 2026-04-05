"""
seed.py — Populates the database with 50 dummy items on first run.
Called automatically at app startup if the table is empty.
"""

from sqlalchemy.orm import Session
from app import models

SEED_ITEMS = [
    {"name": "Wireless Bluetooth Headphones",  "description": "Noise-cancelling over-ear headphones with 30hr battery life", "is_active": True},
    {"name": "Mechanical Keyboard",             "description": "TKL layout with Cherry MX Blue switches and RGB backlight", "is_active": True},
    {"name": "4K USB-C Monitor",                "description": "27-inch IPS display, 144Hz refresh rate, HDR400 support", "is_active": True},
    {"name": "Ergonomic Office Chair",          "description": "Lumbar support, adjustable armrests, mesh back panel", "is_active": True},
    {"name": "Standing Desk",                   "description": "Electric height-adjustable desk, 120x60cm surface", "is_active": True},
    {"name": "Webcam HD 1080p",                 "description": "Wide-angle lens, auto-focus, built-in noise-cancelling mic", "is_active": True},
    {"name": "USB-C Hub 7-in-1",                "description": "HDMI, USB-A x3, SD card, PD charging, Ethernet", "is_active": True},
    {"name": "Laptop Stand Aluminium",          "description": "Adjustable height, foldable, supports up to 15.6 inch laptops", "is_active": True},
    {"name": "Portable SSD 1TB",                "description": "USB 3.2 Gen2, 1050MB/s read speed, shock-resistant casing", "is_active": True},
    {"name": "Smart LED Desk Lamp",             "description": "Touch dimmer, USB charging port, colour temperature control", "is_active": True},
    {"name": "Noise-Cancelling Earbuds",        "description": "ANC, 8hr playback, IPX5 water resistant, wireless charging case", "is_active": True},
    {"name": "Mouse Pad XXL",                   "description": "900x400mm desk mat, stitched edges, non-slip rubber base", "is_active": True},
    {"name": "Wireless Mouse",                  "description": "Ergonomic, 6-button, 2.4GHz dongle + Bluetooth dual mode", "is_active": True},
    {"name": "External Hard Drive 2TB",         "description": "USB 3.0, slim 2.5-inch, password-protected hardware encryption", "is_active": True},
    {"name": "Raspberry Pi 4 Model B",          "description": "4GB RAM, quad-core ARM, dual micro-HDMI, USB 3.0", "is_active": True},
    {"name": "Arduino Uno R3",                  "description": "ATmega328P, 14 digital I/O pins, USB-B, 5V/3.3V output", "is_active": True},
    {"name": "Soldering Iron Kit",              "description": "60W adjustable temp, 5 tips, stand, solder wire included", "is_active": True},
    {"name": "Multimeter Digital",              "description": "AC/DC voltage, current, resistance, diode, continuity tester", "is_active": True},
    {"name": "Cable Management Box",            "description": "Hides power strips and cables, bamboo lid, fire-resistant ABS", "is_active": True},
    {"name": "Smart Power Strip",               "description": "4 AC + 4 USB, surge protection, individual socket switches", "is_active": True},
    {"name": "Webcam Privacy Cover",            "description": "Thin aluminium slide cover, universal fit, 3-pack", "is_active": True},
    {"name": "HDMI Cable 2.1 2m",               "description": "8K@60Hz, 48Gbps bandwidth, braided nylon cable", "is_active": True},
    {"name": "Ethernet Cable Cat6 5m",          "description": "Flat design, 1Gbps, snagless boot, gold-plated connectors", "is_active": True},
    {"name": "Mini PC Intel N100",              "description": "16GB RAM, 512GB NVMe, dual LAN, WiFi 6, fanless option", "is_active": True},
    {"name": "Thermal Paste",                   "description": "High conductivity silver compound, 4g syringe, MX-4 grade", "is_active": True},
    {"name": "DDR4 RAM 16GB",                   "description": "3200MHz, CL16, low-profile heatspreader, single stick", "is_active": True},
    {"name": "NVMe SSD 512GB",                  "description": "PCIe 4.0 M.2 2280, 7000MB/s read, 5-year warranty", "is_active": True},
    {"name": "ATX Power Supply 650W",           "description": "80+ Gold certified, semi-modular, 120mm fan, 5-year warranty", "is_active": True},
    {"name": "CPU Cooler 120mm",                "description": "Dual heat pipe, PWM fan, compatible with Intel LGA1700/AM5", "is_active": True},
    {"name": "Network Switch 8-Port",           "description": "Gigabit unmanaged, desktop/wall-mount, plug-and-play", "is_active": True},
    {"name": "PoE Injector",                    "description": "802.3af/at, 30W output, gigabit passthrough, desktop", "is_active": True},
    {"name": "Micro SD Card 128GB",             "description": "A2 class, 160MB/s read, waterproof, with SD adapter", "is_active": True},
    {"name": "USB Flash Drive 64GB",            "description": "USB 3.1, 200MB/s read, metal casing, retractable connector", "is_active": True},
    {"name": "Screen Cleaning Kit",             "description": "Microfibre cloth + 100ml alcohol-free spray, anti-static", "is_active": True},
    {"name": "Laptop Backpack 17 inch",         "description": "Water-resistant, USB charging port, hidden anti-theft pocket", "is_active": True},
    {"name": "Wrist Rest Keyboard",             "description": "Memory foam, anti-slip base, 43cm wide, washable cover", "is_active": True},
    {"name": "Fingerprint USB Reader",          "description": "360° recognition, plug-and-play, Windows Hello compatible", "is_active": True},
    {"name": "Barcode Scanner USB",             "description": "1D/2D QR code, handheld, 500 scans/sec, 2m drop-proof", "is_active": True},
    {"name": "Label Maker",                     "description": "QWERTY keyboard, thermal printing, USB + battery, 6 tape sizes", "is_active": True},
    {"name": "Thermal Receipt Printer",         "description": "80mm, USB+BT+LAN, 250mm/s, auto-cutter, ESC/POS compatible", "is_active": True},
    {"name": "Document Scanner A4",             "description": "600dpi, duplex, 25ppm, USB, auto-feed 20 sheets", "is_active": True},
    {"name": "Inkjet Printer A4",               "description": "Print/Scan/Copy, WiFi, ADF, borderless photo printing", "is_active": True},
    {"name": "Drawing Tablet A5",               "description": "8192 pen pressure, tilt support, 6 express keys, USB-C", "is_active": True},
    {"name": "VR Headset Standalone",           "description": "4K display per eye, 6DOF tracking, 3hr battery, 128GB", "is_active": False},
    {"name": "Streaming Capture Card",          "description": "4K60 passthrough, 1080p60 capture, USB 3.0, low-latency", "is_active": True},
    {"name": "Green Screen 150x200cm",          "description": "Collapsible, wrinkle-resistant, includes carry bag", "is_active": True},
    {"name": "Ring Light 18 inch",              "description": "LED dimmable, colour temp 3000-6000K, phone holder, tripod", "is_active": True},
    {"name": "USB Condenser Microphone",        "description": "Cardioid polar pattern, 192kHz/24bit, mute button, gain knob", "is_active": True},
    {"name": "Boom Arm Mic Stand",              "description": "Heavy-duty clamp, 360° rotation, cable channel, fits 5/8\" thread", "is_active": True},
    {"name": "KVM Switch 2-Port",               "description": "4K HDMI + USB, hotkey switching, no drivers needed", "is_active": False},
]


def seed_database(db: Session) -> None:
    """Insert 50 seed items only if the items table is empty."""
    count = db.query(models.Item).count()
    if count > 0:
        return  # Already seeded — skip

    items = [models.Item(**data) for data in SEED_ITEMS]
    db.bulk_save_objects(items)
    db.commit()
    print(f"[seed] Inserted {len(items)} dummy items into the database.")
