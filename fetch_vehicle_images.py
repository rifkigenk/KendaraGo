"""Download model-specific vehicle photos from Wikimedia Commons.

Run this script after ``seed.py``. It stores one locally served JPEG per vehicle
and writes source/license attribution to ``sources.json`` beside the images.
"""

import html
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app import create_app
from models import Vehicle


COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "KendaraGoCatalog/1.0 (vehicle image attribution)"
OUTPUT_DIR = (
    Path(__file__).resolve().parent / "static" / "uploads" / "vehicles" / "catalog"
)

SEARCH_OVERRIDES = {
    "CAR-001": "Toyota Agya",
    "CAR-005": "Toyota Innova Zenix",
    "COM-004": "Daihatsu Gran Max pickup",
    "EV-001": "BYD Seagull Atto 1",
    "MPV-001": "Toyota Veloz",
    "MTR-001": "Honda Vario 160",
    "MTR-002": "Yamaha NMAX",
    "MTR-003": "Honda Scoopy",
    "MTR-004": "Yamaha YZF R15",
    "MTR-005": "Honda CBR250RR",
    "MTR-006": "Honda Stylo 160",
    "MTR-007": "Kawasaki Versys-X 250",
    "MTR-008": "Honda Beat scooter",
    "MTR-009": "Honda Vario 125",
    "MTR-010": "Honda PCX 160",
    "MTR-011": "Honda ADV 160",
    "MTR-012": "Yamaha Aerox 155",
    "MTR-013": "Yamaha Fazzio",
    "MTR-014": "Yamaha Gear scooter",
    "MTR-015": "Yamaha FreeGo",
    "MTR-016": "Suzuki Access 125",
    "TOUR-009": "Yamaha Tenere 700 World Raid",
    "TOUR-023": "Indian Pursuit motorcycle",
    "TOUR-027": "CFMoto 800MT",
    "TOUR-030": "Zero DSR X motorcycle",
}

IGNORED_WORDS = {
    "all",
    "new",
    "the",
    "and",
    "connected",
    "deluxe",
    "dct",
    "edition",
    "ev",
    "gr",
    "hybrid",
    "premium",
    "roadsync",
    "sport",
    "turbo",
}


def clean_text(value):
    value = html.unescape(re.sub(r"<[^>]+>", "", value or ""))
    return re.sub(r"\s+", " ", value).strip()


def normalized_tokens(value):
    words = re.findall(r"[a-z0-9]+", value.lower())
    return [word for word in words if len(word) > 1 and word not in IGNORED_WORDS]


def open_url(request, timeout):
    for attempt in range(3):
        try:
            return urlopen(request, timeout=timeout)
        except (HTTPError, URLError):
            if attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))


def commons_search(query):
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"{query} filetype:bitmap",
        "gsrnamespace": 6,
        "gsrlimit": 12,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": 1280,
    }
    request = Request(
        f"{COMMONS_API}?{urlencode(params)}", headers={"User-Agent": USER_AGENT}
    )
    with open_url(request, timeout=30) as response:
        payload = json.load(response)
    return list(payload.get("query", {}).get("pages", {}).values())


def image_score(page, query):
    title = page.get("title", "").lower()
    image_info = page.get("imageinfo", [{}])[0]
    url = image_info.get("thumburl", "")
    if not re.search(r"\.jpe?g(?:/|\?)", url, re.IGNORECASE):
        return -1000

    query_tokens = normalized_tokens(query)
    title_tokens = set(normalized_tokens(title))
    matched = sum(1 for token in query_tokens if token in title_tokens)
    score = matched * 10
    if query_tokens and all(token in title_tokens for token in query_tokens):
        score += 30
    if any(word in title for word in ("rear", "interior", "dashboard", "engine")):
        score -= 8
    return score


def best_image(query):
    pages = commons_search(query)
    candidates = sorted(pages, key=lambda page: image_score(page, query), reverse=True)
    if not candidates or image_score(candidates[0], query) < 10:
        return None
    return candidates[0]


def download(url, destination):
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with open_url(request, timeout=60) as response:
        destination.write_bytes(response.read())


def source_record(vehicle, query, page):
    info = page["imageinfo"][0]
    metadata = info.get("extmetadata", {})
    return {
        "code": vehicle["code"],
        "vehicle": vehicle["name"],
        "search_query": query,
        "commons_file": page["title"],
        "source_page": info.get("descriptionurl"),
        "download_url": info.get("thumburl"),
        "license": clean_text(metadata.get("LicenseShortName", {}).get("value")),
        "license_url": metadata.get("LicenseUrl", {}).get("value"),
        "creator": clean_text(metadata.get("Artist", {}).get("value")),
    }


def fetch_vehicle(vehicle):
    query = SEARCH_OVERRIDES.get(
        vehicle["code"], f"{vehicle['brand']} {vehicle['model']}"
    )
    page = best_image(query)
    if not page:
        return None, {
            "code": vehicle["code"],
            "vehicle": vehicle["name"],
            "query": query,
        }

    info = page["imageinfo"][0]
    destination = OUTPUT_DIR / f"{vehicle['code'].lower()}.jpg"
    download(info["thumburl"], destination)
    return source_record(vehicle, query, page), None


def fetch_images():
    app = create_app()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    missing = []

    with app.app_context():
        vehicles = [
            {
                "code": vehicle.code,
                "name": vehicle.name,
                "brand": vehicle.brand,
                "model": vehicle.model or vehicle.name,
            }
            for vehicle in Vehicle.query.order_by(Vehicle.code).all()
        ]

    # Keep concurrency deliberately low; Commons throttles aggressive thumbnail
    # traffic and some Windows DNS resolvers reject larger request bursts.
    with ThreadPoolExecutor(max_workers=2) as executor:
        jobs = {
            executor.submit(fetch_vehicle, vehicle): vehicle for vehicle in vehicles
        }
        for index, future in enumerate(as_completed(jobs), start=1):
            vehicle = jobs[future]
            try:
                record, missing_record = future.result()
            except Exception as error:
                missing_record = {
                    "code": vehicle["code"],
                    "vehicle": vehicle["name"],
                    "query": SEARCH_OVERRIDES.get(vehicle["code"], vehicle["model"]),
                    "error": str(error),
                }
                record = None

            if record:
                records.append(record)
                print(
                    f"[{index:02}/{len(vehicles)}] tersimpan: {record['code']} — {record['commons_file']}"
                )
            else:
                missing.append(missing_record)
                print(
                    f"[{index:02}/{len(vehicles)}] tidak ditemukan: {vehicle['code']}"
                )

    records.sort(key=lambda item: item["code"])
    missing.sort(key=lambda item: item["code"])

    manifest = {
        "source": "Wikimedia Commons",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "images": records,
        "missing": missing,
    }
    (OUTPUT_DIR / "sources.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nSelesai: {len(records)} gambar, {len(missing)} belum ditemukan.")


if __name__ == "__main__":
    fetch_images()
