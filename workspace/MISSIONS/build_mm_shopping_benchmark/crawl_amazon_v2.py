import requests
from bs4 import BeautifulSoup
import os
import time
import random
import json
import re

BASE_DIR = "./workspace/MISSIONS/build_mm_shopping_benchmark/mm_shopping_benchmark"
IMAGE_DIR = os.path.join(BASE_DIR, "images")
os.makedirs(IMAGE_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def search_amazon(query, max_results=10):
    """Search Amazon and return product image URLs and titles."""
    url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        img_tags = soup.find_all("img", class_="s-image")
        for img in img_tags[:max_results]:
            src = img.get("src", "")
            alt = img.get("alt", "product")
            if src and "media-amazon.com" in src and not src.endswith(".png"):
                # Get higher resolution
                src = re.sub(r'\._AC_UL\d+_', '._AC_UL600_', src)
                src = re.sub(r'\._AC_US\d+_', '._AC_US600_', src)
                results.append({"url": src, "title": alt})
        return results
    except Exception as e:
        print(f"  Error searching for '{query}': {e}")
        return []

def download_image(url, filename):
    """Download image from URL and save to images folder."""
    filepath = os.path.join(IMAGE_DIR, filename)
    if os.path.exists(filepath):
        return True
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200 and len(resp.content) > 1000:
            with open(filepath, "wb") as f:
                f.write(resp.content)
            return True
    except Exception as e:
        print(f"  Error downloading: {e}")
    return False

def sanitize_filename(name, max_len=60):
    name = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
    name = re.sub(r'_+', '_', name).strip('_')
    return name[:max_len]

def crawl_category(queries, category_prefix, needed=35):
    all_images = []
    seen_urls = set()
    for query in queries:
        if len(all_images) >= needed:
            break
        print(f"  Searching: {query}")
        results = search_amazon(query, max_results=8)
        for r in results:
            if len(all_images) >= needed:
                break
            if r["url"] in seen_urls:
                continue
            seen_urls.add(r["url"])
            desc = sanitize_filename(r["title"])
            idx = len(all_images)
            fname = f"{category_prefix}_{idx:03d}_{desc}.jpg"
            if download_image(r["url"], fname):
                all_images.append({"filename": fname, "description": r["title"]})
        time.sleep(random.uniform(2.0, 4.0))
    return all_images

print("=" * 60)
print("CRAWLING AMAZON IMAGES FOR BENCHMARK")
print("=" * 60)

# 1. Clothing items
print("\n[1/7] Crawling clothing items...")
clothing_queries = [
    "denim jacket women", "leather jacket men", "blazer women formal",
    "summer dress women floral", "maxi dress", "cocktail dress women",
    "men suit jacket slim", "cardigan sweater women", "hoodie men pullover",
    "trench coat women", "puffer jacket winter", "crop top women",
    "polo shirt men", "linen shirt men casual", "silk blouse women",
    "jeans women slim fit", "chino pants men", "midi skirt women",
    "athletic wear women set", "winter coat men wool",
    "women tshirt casual", "men shorts casual", "women jumpsuit",
    "men vest formal", "women romper summer"
]
clothing_images = crawl_category(clothing_queries, "clothing", needed=55)
print(f"  => Got {len(clothing_images)} clothing images")

# 2. Full body mannequins/dress forms (as portrait stand-ins)
print("\n[2/7] Crawling portrait/mannequin images...")
portrait_queries = [
    "female mannequin full body", "male mannequin full body display",
    "dress form female adjustable", "mannequin torso female",
    "display mannequin standing", "fashion mannequin woman",
    "male dress form", "child mannequin full body",
    "plus size mannequin female", "athletic mannequin male"
]
portrait_images = crawl_category(portrait_queries, "portrait", needed=35)
print(f"  => Got {len(portrait_images)} portrait images")

# 3. Home/room scenes
print("\n[3/7] Crawling home/room images...")
home_queries = [
    "living room furniture set modern", "bedroom furniture set complete",
    "kitchen island with stools", "dining room set 5 piece",
    "bathroom vanity with mirror", "home office desk with shelves",
    "patio furniture set outdoor wicker", "nursery furniture set baby",
    "entryway furniture set", "laundry room shelving unit",
    "living room sectional sofa", "bedroom nightstand set",
    "kitchen pantry cabinet", "dining room buffet sideboard"
]
home_images = crawl_category(home_queries, "home_scene", needed=40)
print(f"  => Got {len(home_images)} home scene images")

# 4. Home products (individual items)
print("\n[4/7] Crawling home products...")
home_product_queries = [
    "floor lamp modern arc", "table lamp ceramic", "throw pillow covers decorative",
    "canvas wall art abstract", "area rug 5x7 modern", "bookshelf 5 tier",
    "coffee table glass modern", "accent side table gold", "indoor plant pot ceramic",
    "curtains blackout living room", "wall mirror round decorative", "ceramic vase set",
    "pendant light modern", "storage ottoman velvet", "desk lamp adjustable",
    "floating wall shelf set", "candle holder decorative", "wall clock modern large",
    "throw blanket knitted", "picture frame set gallery"
]
home_product_images = crawl_category(home_product_queries, "home_product", needed=50)
print(f"  => Got {len(home_product_images)} home product images")

# 5. Shoes/accessories for Visual Product Search
print("\n[5/7] Crawling shoes and accessories...")
shoes_acc_queries = [
    "running sneakers men nike", "high heels women pump", "ankle boots women leather",
    "sandals women flat", "loafers men casual", "backpack laptop travel",
    "handbag women crossbody", "watch men analog", "sunglasses women polarized",
    "fedora hat men", "scarf women cashmere", "belt men genuine leather",
    "necklace women pendant", "earrings women hoop gold", "wallet men rfid",
    "tote bag women large"
]
shoes_acc_images = crawl_category(shoes_acc_queries, "accessory", needed=35)
print(f"  => Got {len(shoes_acc_images)} shoes/accessory images")

# 6. Items for shoppable posts
print("\n[6/7] Crawling shoppable post items...")
shoppable_queries = [
    "baking supplies set complete", "yoga mat accessories set",
    "camping gear essentials kit", "gardening tools set",
    "art supplies painting set", "coffee maker accessories set",
    "dog accessories starter kit", "beach accessories set",
    "picnic basket set", "spa bath gift set",
    "home gym equipment set", "cocktail shaker set",
    "sewing supplies kit", "bbq grill accessories set",
    "meditation cushion set", "travel accessories organizer set"
]
shoppable_images = crawl_category(shoppable_queries, "shoppable", needed=35)
print(f"  => Got {len(shoppable_images)} shoppable images")

# Save metadata
metadata = {
    "clothing": clothing_images,
    "portrait": portrait_images,
    "home_scene": home_images,
    "home_product": home_product_images,
    "accessory": shoes_acc_images,
    "shoppable": shoppable_images,
}

with open(os.path.join(BASE_DIR, "image_metadata.json"), "w") as f:
    json.dump(metadata, f, indent=2)

total = sum(len(v) for v in metadata.values())
print(f"\n{'='*60}")
print(f"TOTAL IMAGES DOWNLOADED: {total}")
for k, v in metadata.items():
    print(f"  {k}: {len(v)} images")
print(f"{'='*60}")
