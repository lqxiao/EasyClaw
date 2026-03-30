#!/usr/bin/env python3
"""
Crawl Amazon images using browser-use (real Chrome).
Extracts product images from Amazon search results.
"""

import subprocess
import json
import os
import time
import re
import urllib.request
import ssl
import sys

BASE_DIR = "./workspace/MISSIONS/build_mm_train/mm_shopping_benchmark_train"
IMAGES_DIR = os.path.join(BASE_DIR, "images")
os.makedirs(IMAGES_DIR, exist_ok=True)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

def run_browser_cmd(cmd):
    """Run a browser-use command and return output."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    return result.stdout.strip()

def sanitize_filename(name, max_len=80):
    name = re.sub(r'[^\w\s-]', '', name.lower())
    name = re.sub(r'[\s]+', '_', name.strip())
    return name[:max_len]

def download_image(url, filepath):
    """Download image from URL."""
    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        return True
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            data = resp.read()
            if len(data) < 500:
                return False
            with open(filepath, 'wb') as f:
                f.write(data)
            return True
    except Exception as e:
        print(f"  [ERR] Download failed: {e}")
        return False

def get_high_res_url(url):
    """Convert Amazon thumbnail URL to higher resolution."""
    # Replace sizing suffix with larger version
    base = url.split('._')[0]
    return base + "._AC_SX679_.jpg"

def search_and_download(query, prefix, count=3, start_idx=0):
    """Search Amazon and download product images. Returns list of filenames."""
    encoded_query = query.replace(' ', '+')
    
    # Determine search category
    home_keywords = ['lamp', 'table', 'chair', 'shelf', 'rug', 'pillow', 'vase', 
                     'mirror', 'light', 'basket', 'blanket', 'console', 'organizer',
                     'clock', 'cart', 'cushion', 'candle', 'rack', 'stand', 'tray',
                     'curtain', 'island', 'furniture', 'decor', 'bedroom', 'living',
                     'kitchen', 'bathroom', 'dining', 'office', 'entryway', 'faucet',
                     'ottoman', 'pendant', 'sofa', 'couch']
    
    category = "garden"
    for kw in home_keywords:
        if kw in query.lower():
            category = "garden"
            break
    else:
        category = "fashion"
    
    url = f"https://www.amazon.com/s?k={encoded_query}&i={category}"
    
    print(f"  Searching: {query} (category: {category})")
    
    try:
        run_browser_cmd(f'browser-use --browser real open "{url}"')
        time.sleep(2)
        
        # Extract image URLs
        js = """JSON.stringify(Array.from(document.querySelectorAll('img.s-image')).slice(0,15).map(img => ({src: img.src, alt: img.alt})))"""
        output = run_browser_cmd(f"browser-use eval \"{js}\"")
        
        # Parse the result
        if 'result:' in output:
            json_str = output.split('result:', 1)[1].strip()
            images = json.loads(json_str)
        else:
            print(f"  [WARN] No results for '{query}'")
            return []
        
        if not images:
            print(f"  [WARN] No images found for '{query}'")
            return []
        
        filenames = []
        for i in range(min(count, len(images))):
            idx = start_idx + i
            if idx >= len(images):
                idx = idx % len(images)
            
            img_data = images[idx]
            src = get_high_res_url(img_data['src'])
            alt = img_data.get('alt', query)
            
            fname = sanitize_filename(f"{prefix}_{query}_{i}") + ".png"
            filepath = os.path.join(IMAGES_DIR, fname)
            
            if download_image(src, filepath):
                print(f"  [OK] {fname}")
                filenames.append(fname)
            else:
                print(f"  [FAIL] {fname}")
        
        return filenames
        
    except Exception as e:
        print(f"  [ERR] Search failed for '{query}': {e}")
        return []

# ============================================================
# ALL QUERIES TO CRAWL
# ============================================================

ALL_QUERIES = {
    # Portrait/model images (full body shots from Amazon fashion)
    "portrait": [
        ("men casual outfit", "portrait", 2),
        ("women casual dress outfit", "portrait", 2),
        ("men suit outfit", "portrait", 2),
        ("women blazer outfit", "portrait", 2),
        ("men winter jacket outfit", "portrait", 2),
        ("women summer dress", "portrait", 2),
        ("men sweater outfit", "portrait", 2),
        ("women winter coat", "portrait", 2),
        ("men shirt outfit", "portrait", 2),
        ("women skirt outfit", "portrait", 2),
    ],
    # Clothing items for Virtual Try-On
    "clothing": [
        ("denim jacket men", "clothing", 2),
        ("red blazer women", "clothing", 2),
        ("floral summer dress women", "clothing", 2),
        ("leather motorcycle jacket", "clothing", 2),
        ("navy suit men", "clothing", 2),
        ("oversized hoodie unisex", "clothing", 2),
        ("striped button down shirt men", "clothing", 2),
        ("cashmere sweater women", "clothing", 2),
        ("plaid flannel shirt", "clothing", 2),
        ("cropped denim vest women", "clothing", 2),
        ("white linen blazer men", "clothing", 2),
        ("puffer jacket women", "clothing", 2),
        ("trench coat men", "clothing", 2),
        ("graphic tee men", "clothing", 2),
        ("long cardigan women", "clothing", 2),
        ("polo shirt men", "clothing", 2),
        ("silk blouse women", "clothing", 2),
        ("bomber jacket men", "clothing", 2),
        ("turtleneck sweater women", "clothing", 2),
        ("chambray shirt men", "clothing", 2),
        ("quilted vest men", "clothing", 2),
        ("hawaiian shirt men", "clothing", 2),
        ("corduroy blazer women", "clothing", 2),
        ("athletic zip jacket", "clothing", 2),
        ("cable knit sweater", "clothing", 2),
        ("double breasted coat women", "clothing", 2),
        ("henley shirt men", "clothing", 2),
        ("windbreaker jacket", "clothing", 2),
        ("linen camp collar shirt", "clothing", 2),
        ("velvet blazer women", "clothing", 2),
    ],
    # Home/room images
    "home": [
        ("living room furniture set modern", "home", 2),
        ("modern living room decor", "home", 2),
        ("bedroom furniture set complete", "home", 2),
        ("kitchen decor accessories", "home", 2),
        ("dining room table set", "home", 2),
        ("home office desk setup", "home", 2),
        ("bathroom vanity modern", "home", 2),
        ("entryway furniture bench", "home", 2),
        ("cozy living room sectional sofa", "home", 2),
        ("modern bedroom platform bed", "home", 2),
    ],
    # Home products for In-Scene Placement
    "home_product": [
        ("modern floor lamp arc", "home_product", 2),
        ("accent chair velvet", "home_product", 2),
        ("modern coffee table glass", "home_product", 2),
        ("bookshelf 5 tier wooden", "home_product", 2),
        ("decorative throw pillow set", "home_product", 2),
        ("area rug 8x10 modern", "home_product", 2),
        ("table lamp ceramic", "home_product", 2),
        ("wall art canvas abstract", "home_product", 2),
        ("indoor plant stand metal", "home_product", 2),
        ("round ottoman pouf", "home_product", 2),
        ("led desk lamp modern", "home_product", 2),
        ("nightstand side table", "home_product", 2),
        ("wall mirror round decorative", "home_product", 2),
        ("ceramic vase decorative", "home_product", 2),
        ("pendant light kitchen island", "home_product", 2),
        ("woven storage basket large", "home_product", 2),
        ("throw blanket knit cozy", "home_product", 2),
        ("console table narrow entryway", "home_product", 2),
        ("desk organizer wooden", "home_product", 2),
        ("wall clock modern large", "home_product", 2),
        ("bar cart gold modern", "home_product", 2),
        ("floor cushion large round", "home_product", 2),
        ("candle set decorative soy", "home_product", 2),
        ("shoe rack entryway organizer", "home_product", 2),
        ("tv stand modern wood", "home_product", 2),
        ("decorative tray ottoman", "home_product", 2),
        ("curtain rod double", "home_product", 2),
        ("kitchen island cart", "home_product", 2),
        ("coat rack standing tree", "home_product", 2),
        ("floating shelf wall mount", "home_product", 2),
    ],
    # Visual search items
    "search": [
        ("white sneakers men casual", "search", 1),
        ("designer handbag women leather", "search", 1),
        ("denim jacket classic", "search", 1),
        ("modern coffee table round", "search", 1),
        ("throw pillow boho", "search", 1),
        ("aviator sunglasses polarized", "search", 1),
        ("desk lamp adjustable", "search", 1),
        ("geometric area rug", "search", 1),
        ("men casual watch leather", "search", 1),
        ("modern dining chair set", "search", 1),
        ("women summer midi dress", "search", 1),
        ("wooden bookshelf modern", "search", 1),
        ("women ankle boots leather", "search", 1),
        ("abstract wall art large", "search", 1),
        ("canvas backpack vintage", "search", 1),
        ("pendant light fixture modern", "search", 1),
        ("silk scarf women designer", "search", 1),
        ("round side table gold", "search", 1),
        ("women blazer casual", "search", 1),
        ("ceramic vase set", "search", 1),
        ("men running shoes", "search", 1),
        ("knit throw blanket chunky", "search", 1),
        ("fedora hat men wool", "search", 1),
        ("full length floor mirror", "search", 1),
        ("gold drop earrings women", "search", 1),
        ("leather ottoman round", "search", 1),
        ("oversized cardigan women", "search", 1),
        ("modern kitchen faucet", "search", 1),
        ("crossbody bag leather women", "search", 1),
        ("linen curtain set", "search", 1),
    ],
}

def main():
    # Track all downloaded files by category
    downloaded = {}
    
    total_queries = sum(len(queries) for queries in ALL_QUERIES.values())
    done = 0
    
    for category, queries in ALL_QUERIES.items():
        downloaded[category] = []
        print(f"\n{'='*60}")
        print(f"CATEGORY: {category} ({len(queries)} queries)")
        print(f"{'='*60}")
        
        for query, prefix, count in queries:
            done += 1
            print(f"\n[{done}/{total_queries}] {query}")
            filenames = search_and_download(query, prefix, count)
            downloaded[category].extend(filenames)
            time.sleep(1.5)  # Rate limiting
    
    # Save download manifest
    manifest_path = os.path.join(BASE_DIR, "download_manifest.json")
    with open(manifest_path, 'w') as f:
        json.dump(downloaded, f, indent=2)
    
    print(f"\n{'='*60}")
    print("DOWNLOAD SUMMARY")
    print(f"{'='*60}")
    for cat, files in downloaded.items():
        print(f"  {cat}: {len(files)} images")
    total = sum(len(f) for f in downloaded.values())
    print(f"  TOTAL: {total} images")
    print(f"\nManifest saved to {manifest_path}")

if __name__ == "__main__":
    main()
