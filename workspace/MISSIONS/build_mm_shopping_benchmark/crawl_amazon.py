import requests
from bs4 import BeautifulSoup
import os
import time
import random
import json
import re
import hashlib

BASE_DIR = "./workspace/MISSIONS/build_mm_shopping_benchmark/mm_shopping_benchmark"
IMAGE_DIR = os.path.join(BASE_DIR, "images")
os.makedirs(IMAGE_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

def search_amazon(query, max_results=10):
    """Search Amazon and return product image URLs and titles."""
    url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        # Find product images
        img_tags = soup.find_all("img", class_="s-image")
        for img in img_tags[:max_results]:
            src = img.get("src", "")
            alt = img.get("alt", "product")
            if src and "images-amazon.com" in src:
                # Get higher resolution version
                src = re.sub(r'\._AC_UL\d+_', '._AC_UL600_', src)
                src = re.sub(r'\._AC_US\d+_', '._AC_US600_', src)
                results.append({"url": src, "title": alt})
        return results
    except Exception as e:
        print(f"Error searching for '{query}': {e}")
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
        print(f"Error downloading {url}: {e}")
    return False

def sanitize_filename(name, max_len=80):
    """Create a safe filename from description."""
    name = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
    name = re.sub(r'_+', '_', name).strip('_')
    return name[:max_len]

def crawl_category(queries, category_prefix, needed=35):
    """Crawl images for a category, return list of (filename, description)."""
    all_images = []
    for query in queries:
        if len(all_images) >= needed:
            break
        results = search_amazon(query, max_results=8)
        for r in results:
            if len(all_images) >= needed:
                break
            desc = sanitize_filename(r["title"])
            fname = f"{category_prefix}_{desc}.png"
            if download_image(r["url"], fname):
                all_images.append({"filename": fname, "description": r["title"]})
                print(f"  Downloaded: {fname[:60]}...")
        time.sleep(random.uniform(1.5, 3.0))
    return all_images

# Define search queries for each category
print("=" * 60)
print("CRAWLING AMAZON IMAGES FOR BENCHMARK")
print("=" * 60)

# 1. Clothing items for Virtual Try-On, Outfit Styling, Garment Editing
print("\n[1/8] Crawling clothing items...")
clothing_queries = [
    "denim jacket women", "leather jacket men", "blazer women formal",
    "summer dress women", "maxi dress floral", "cocktail dress",
    "men suit jacket", "cardigan sweater women", "hoodie men",
    "trench coat women", "puffer jacket", "crop top women",
    "polo shirt men", "linen shirt men", "silk blouse women",
    "jeans women slim", "chino pants men", "skirt women midi",
    "athletic wear women", "winter coat men"
]
clothing_images = crawl_category(clothing_queries, "clothing", needed=50)
print(f"  Got {len(clothing_images)} clothing images")

# 2. Full body portraits (user photos) - search for mannequin/model displays
print("\n[2/8] Crawling body/portrait reference images...")
portrait_queries = [
    "women full body mannequin display", "men mannequin full body",
    "dress form mannequin female", "male mannequin standing",
    "women fashion mannequin", "display mannequin male full body",
    "female body form dress", "adjustable dress form"
]
portrait_images = crawl_category(portrait_queries, "portrait", needed=35)
print(f"  Got {len(portrait_images)} portrait images")

# 3. Home/room images for In-Scene Product Placement, Interior Style, Home Editing
print("\n[3/8] Crawling home/room images...")
home_queries = [
    "living room furniture set", "modern bedroom set", "kitchen decor set",
    "dining room table set", "bathroom vanity set", "home office desk setup",
    "patio furniture set outdoor", "nursery room furniture",
    "entryway console table", "laundry room organization"
]
home_images = crawl_category(home_queries, "home", needed=40)
print(f"  Got {len(home_images)} home images")

# 4. Home products (furniture, decor) for placement
print("\n[4/8] Crawling home products...")
home_product_queries = [
    "floor lamp modern", "table lamp decorative", "throw pillow set",
    "wall art canvas", "area rug modern", "bookshelf wooden",
    "coffee table modern", "side table accent", "plant pot indoor",
    "curtains living room", "mirror decorative wall", "vase ceramic",
    "chandelier modern", "storage ottoman", "desk organizer",
    "floating shelf wall", "candle holder set", "clock wall decorative"
]
home_product_images = crawl_category(home_product_queries, "home_product", needed=50)
print(f"  Got {len(home_product_images)} home product images")

# 5. Shoes/accessories for Visual Product Search
print("\n[5/8] Crawling shoes and accessories...")
shoes_acc_queries = [
    "sneakers men running", "high heels women", "boots ankle women",
    "sandals women summer", "loafers men leather", "backpack travel",
    "handbag women leather", "watch men casual", "sunglasses women",
    "hat fedora", "scarf women silk", "belt men leather",
    "jewelry necklace women", "earrings women gold", "wallet men leather"
]
shoes_acc_images = crawl_category(shoes_acc_queries, "accessory", needed=35)
print(f"  Got {len(shoes_acc_images)} shoes/accessory images")

# 6. Shoppable post items (kitchen, baking, fitness, etc.)
print("\n[6/8] Crawling shoppable post items...")
shoppable_queries = [
    "baking essentials set", "yoga accessories set", "camping gear essentials",
    "gardening tools set", "art supplies set", "coffee brewing set",
    "pet accessories dog", "beach essentials set", "picnic set outdoor",
    "spa gift set", "workout equipment home", "cocktail making set",
    "sewing kit supplies", "grilling accessories bbq", "meditation accessories"
]
shoppable_images = crawl_category(shoppable_queries, "shoppable", needed=35)
print(f"  Got {len(shoppable_images)} shoppable images")

# Save metadata
metadata = {
    "clothing": clothing_images,
    "portrait": portrait_images,
    "home": home_images,
    "home_product": home_product_images,
    "accessory": shoes_acc_images,
    "shoppable": shoppable_images,
}

with open(os.path.join(BASE_DIR, "image_metadata.json"), "w") as f:
    json.dump(metadata, f, indent=2)

total = sum(len(v) for v in metadata.values())
print(f"\n{'='*60}")
print(f"TOTAL IMAGES DOWNLOADED: {total}")
print(f"{'='*60}")
