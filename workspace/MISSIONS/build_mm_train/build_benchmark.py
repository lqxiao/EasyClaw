#!/usr/bin/env python3
"""
Build MM Shopping Benchmark Train dataset.
- 8 subtasks x 30 samples = 240 samples
- Images crawled from Amazon.com
- Output: samples.csv + images/ folder
"""

import csv
import os
import time
import re
import json
import hashlib
import urllib.request
import urllib.parse
import ssl
import random
from pathlib import Path

BASE_DIR = Path("./workspace/MISSIONS/build_mm_train/mm_shopping_benchmark_train")
IMAGES_DIR = BASE_DIR / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# SSL context for urllib
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def download_image(url, filename):
    """Download image from URL to filename in images dir."""
    filepath = IMAGES_DIR / filename
    if filepath.exists():
        print(f"  [SKIP] {filename} already exists")
        return True
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            data = resp.read()
            if len(data) < 1000:
                print(f"  [WARN] {filename} too small ({len(data)} bytes), skipping")
                return False
            with open(filepath, 'wb') as f:
                f.write(data)
            print(f"  [OK] Downloaded {filename} ({len(data)} bytes)")
            return True
    except Exception as e:
        print(f"  [ERR] Failed to download {filename}: {e}")
        return False

def sanitize_filename(name, max_len=80):
    """Create a safe filename from description."""
    name = re.sub(r'[^\w\s-]', '', name.lower())
    name = re.sub(r'[\s]+', '_', name.strip())
    return name[:max_len]

# ============================================================
# INSTRUCTIONS FOR EACH SUBTASK
# ============================================================

VIRTUAL_TRYON_INSTRUCTIONS = [
    "Put this denim jacket on me",
    "Try this red blazer on my photo",
    "Show me wearing this floral summer dress",
    "Put this leather motorcycle jacket on me",
    "I want to see how this navy suit looks on me",
    "Try this oversized hoodie on my picture",
    "Show me in this striped button-down shirt",
    "Put this cashmere sweater on me please",
    "How would I look in this plaid flannel shirt",
    "Try this cropped denim vest on my photo",
    "Show me wearing this white linen blazer",
    "Put this puffer jacket on me",
    "I want to see this trench coat on me",
    "Try this graphic tee and this cardigan on me together",
    "Show me in this polo shirt",
    "Put this silk blouse on my photo",
    "How would this bomber jacket look on me",
    "Try this turtleneck sweater on me",
    "Show me wearing this chambray shirt and vest",
    "Put this quilted gilet on me",
    "I want to see this Hawaiian shirt on my body",
    "Try this corduroy blazer on me",
    "Show me in this athletic zip-up jacket",
    "Put this cable knit sweater on me",
    "How would I look in this double-breasted coat",
    "Try this henley shirt on my photo",
    "Show me wearing this windbreaker",
    "Put this linen camp collar shirt on me",
    "Try this velvet blazer on me",
    "Show me in this denim shirt and this leather jacket together",
]

OUTFIT_STYLING_INSTRUCTIONS = [
    "Generate outfit ideas around this navy blazer",
    "Style a complete look with this floral skirt",
    "Build me outfits around this leather jacket",
    "Create outfit combinations with this white sneakers",
    "Suggest styling options for this denim jacket",
    "What outfits go well with this plaid scarf",
    "Generate looks around this camel overcoat",
    "Style me with this pair of black boots",
    "Create complete outfits featuring this striped sweater",
    "Build a weekend look around this hoodie",
    "Suggest outfit pairings for this midi dress",
    "Generate casual outfits with this graphic tee",
    "Style a date night look with this silk blouse",
    "Create work outfits around this pencil skirt",
    "Build outfits featuring this varsity jacket",
    "Suggest looks with this pair of wide-leg pants",
    "Generate brunch outfit ideas with this cardigan",
    "Style a travel outfit around this linen shirt",
    "Create gym-to-street looks with this athletic jacket",
    "Build a fall layered outfit with this turtleneck",
    "Suggest festival outfits around this crop top",
    "Generate smart casual looks with this polo shirt",
    "Style a summer outfit with this tank top",
    "Create office looks around this button-down shirt",
    "Build a cozy winter outfit with this puffer vest",
    "Suggest evening outfits with this sequin top",
    "Generate beach vacation looks with this linen shorts",
    "Style a spring outfit around this trench coat",
    "Create monochrome outfits with this black blazer",
    "Build a streetwear look around this oversized tee",
]

GARMENT_EDITING_INSTRUCTIONS = [
    "Change this red dress to a deep navy blue",
    "Make this cotton shirt look like it's made of silk",
    "Convert this midi skirt to a mini length",
    "Change the color of this jacket from black to burgundy",
    "Make this loose-fit shirt into a slim-fit version",
    "Turn this solid blue shirt into a pinstriped pattern",
    "Change this summer dress from floral to solid white",
    "Make this regular collar into a mandarin collar",
    "Convert this long-sleeve shirt to short sleeves",
    "Change this denim jacket to a lighter wash",
    "Make this wool coat look like leather",
    "Turn this V-neck sweater into a crew neck",
    "Change this plaid pattern to houndstooth",
    "Make this casual shirt more formal with French cuffs",
    "Convert this knee-length dress to floor-length",
    "Change the fabric of this blazer from cotton to velvet",
    "Make this bright yellow top a muted olive green",
    "Turn this button-up shirt into a pullover style",
    "Change this straight-leg pants to a tapered fit",
    "Make this plain white tee into a tie-dye pattern",
    "Convert this sleeveless top to cap sleeves",
    "Change this brown leather jacket to black suede",
    "Make this relaxed-fit jeans into a bootcut style",
    "Turn this crew neck sweater into an off-shoulder style",
    "Change this pastel pink blouse to coral",
    "Make this polyester dress look like chiffon",
    "Convert this regular hoodie to a cropped version",
    "Change this geometric print to a tropical pattern",
    "Make this oversized coat into a fitted silhouette",
    "Turn this dark wash denim into distressed light wash",
]

INSCENE_PLACEMENT_INSTRUCTIONS = [
    "Place this floor lamp in the corner of my living room",
    "Put this accent chair next to my sofa",
    "Add this coffee table to the center of my living room",
    "Place this bookshelf against the empty wall",
    "Put this throw pillow set on my couch",
    "Add this area rug under my dining table",
    "Place this table lamp on my nightstand",
    "Put this wall art above my fireplace",
    "Add this plant stand near the window",
    "Place this ottoman in front of my armchair",
    "Put this desk lamp on my home office desk",
    "Add this side table next to my bed",
    "Place this mirror on the hallway wall",
    "Put this vase on my kitchen counter",
    "Add this pendant light above my dining table",
    "Place this storage basket near the bookshelf",
    "Put this throw blanket on my sectional sofa",
    "Add this console table in my entryway",
    "Place this desk organizer on my workspace",
    "Put this wall clock above the mantel",
    "Add this bar cart to the corner of my dining room",
    "Place this floor cushion near the coffee table",
    "Put this candle set on my bathroom counter",
    "Add this shoe rack by the front door",
    "Place this TV stand in my living room",
    "Put this decorative tray on my coffee table",
    "Add this curtain rod and these curtains to my bedroom window",
    "Place this kitchen island in the center of my kitchen",
    "Put this coat rack by the entrance",
    "Add this floating shelf above my desk",
]

INTERIOR_STYLE_INSTRUCTIONS = [
    "Transform this room into a Scandinavian minimalist style",
    "Generate a mid-century modern redesign of this space",
    "Restyle this room in a bohemian aesthetic",
    "Convert this living room to an industrial loft style",
    "Transform this bedroom into a coastal beach house look",
    "Redesign this space in a Japanese wabi-sabi style",
    "Generate a farmhouse chic version of this room",
    "Restyle this room in an art deco theme",
    "Convert this space to a modern contemporary design",
    "Transform this room into a rustic cabin aesthetic",
    "Generate a Hollywood regency redesign of this living room",
    "Restyle this bedroom in a French country style",
    "Convert this room to a tropical resort look",
    "Transform this space into a Moroccan-inspired design",
    "Generate a maximalist eclectic version of this room",
    "Restyle this living room in a Memphis design style",
    "Convert this bedroom to a dark academia aesthetic",
    "Transform this room into a desert modern style",
    "Generate a Victorian-inspired redesign of this space",
    "Restyle this room in a Korean minimalist aesthetic",
    "Convert this living room to a retro 70s style",
    "Transform this space into a Bauhaus-inspired design",
    "Generate a cottagecore version of this bedroom",
    "Restyle this room in an urban jungle style",
    "Convert this space to a luxury penthouse aesthetic",
    "Transform this room into a Mediterranean villa style",
    "Generate a preppy traditional redesign of this living room",
    "Restyle this bedroom in a zen meditation room style",
    "Convert this room to a Parisian apartment aesthetic",
    "Transform this space into a modern organic design",
]

HOME_EDITING_INSTRUCTIONS = [
    "Replace the coffee table with a round marble one",
    "Change the wall color from white to sage green",
    "Swap the curtains for floor-to-ceiling linen drapes",
    "Replace the carpet with light oak hardwood flooring",
    "Change the sofa upholstery to navy blue velvet",
    "Swap the ceiling fan for a modern chandelier",
    "Replace the kitchen backsplash with white subway tiles",
    "Change the dining chairs to mid-century modern style",
    "Swap the bathroom vanity for a floating wooden one",
    "Replace the bed frame with an upholstered platform bed",
    "Change the kitchen cabinets from white to dark walnut",
    "Swap the throw pillows for a terracotta and cream set",
    "Replace the overhead light with recessed lighting",
    "Change the window blinds to Roman shades",
    "Swap the nightstands for wall-mounted floating shelves",
    "Replace the area rug with a Persian-style vintage rug",
    "Change the countertops from granite to white quartz",
    "Swap the bookshelf for a built-in wall unit",
    "Replace the front door with a modern black steel door",
    "Change the fireplace surround to stacked stone",
    "Swap the desk for a standing desk with walnut top",
    "Replace the dining table with a live-edge wood slab",
    "Change the bathroom tiles to hexagonal marble",
    "Swap the TV console for a minimalist floating media unit",
    "Replace the staircase railing with modern glass panels",
    "Change the bedroom walls to a textured wallpaper",
    "Swap the kitchen island for a butcher block cart",
    "Replace the patio furniture with wicker lounge chairs",
    "Change the closet doors to sliding barn doors",
    "Swap the pendant lights for industrial Edison bulb fixtures",
]

VISUAL_SEARCH_INSTRUCTIONS = [
    "Find the exact same sneakers shown in this photo",
    "Search for this exact handbag online",
    "Find where I can buy this same jacket",
    "Locate this exact coffee table for purchase",
    "Find the same throw pillow set from this image",
    "Search for this exact pair of sunglasses",
    "Find where to buy this same desk lamp",
    "Locate this exact area rug for purchase",
    "Find the same watch shown in this photo",
    "Search for this exact dining chair",
    "Find where I can buy this same dress",
    "Locate this exact bookshelf for purchase",
    "Find the same boots shown in this image",
    "Search for this exact wall art print",
    "Find where to buy this same backpack",
    "Locate this exact pendant light fixture",
    "Find the same scarf shown in this photo",
    "Search for this exact side table",
    "Find where I can buy this same blazer",
    "Locate this exact vase for purchase",
    "Find the same running shoes from this image",
    "Search for this exact throw blanket",
    "Find where to buy this same hat",
    "Locate this exact floor mirror for purchase",
    "Find the same earrings shown in this photo",
    "Search for this exact ottoman",
    "Find where I can buy this same cardigan",
    "Locate this exact kitchen faucet for purchase",
    "Find the same crossbody bag from this image",
    "Search for this exact curtain set",
]

SHOPPABLE_POSTS_INSTRUCTIONS = [
    "Create a 'Cozy fall morning' shoppable mood board",
    "Generate a 'Baking essentials' shoppable collage",
    "Create a 'Home office upgrade' shopping inspiration post",
    "Generate a 'Beach vacation packing list' visual post",
    "Create a 'Date night outfit' shoppable mood board",
    "Generate a 'Plant parent starter kit' collage",
    "Create a 'Minimalist bathroom essentials' shopping post",
    "Generate a 'Summer BBQ party setup' shoppable collage",
    "Create a 'Work from home comfort' mood board",
    "Generate a 'Rainy day self-care' shoppable post",
    "Create a 'Fitness starter pack' visual shopping guide",
    "Generate a 'Scandinavian living room' shoppable collage",
    "Create a 'Back to school essentials' mood board",
    "Generate a 'Outdoor camping gear' shoppable post",
    "Create a 'Modern kitchen must-haves' collage",
    "Generate a 'Valentine's Day gift guide' shoppable post",
    "Create a 'Weekend brunch table setting' mood board",
    "Generate a 'Nursery room essentials' shoppable collage",
    "Create a 'Winter layering guide' visual post",
    "Generate a 'Pet parent essentials' shopping mood board",
    "Create a 'Bohemian bedroom makeover' shoppable collage",
    "Generate a 'Cocktail party hosting kit' visual post",
    "Create a 'Spring cleaning essentials' mood board",
    "Generate a 'Road trip must-haves' shoppable collage",
    "Create a 'Sustainable fashion picks' visual shopping post",
    "Generate a 'Game day snack setup' shoppable mood board",
    "Create a 'Luxury spa at home' collage",
    "Generate a 'Holiday gift wrapping station' shoppable post",
    "Create a 'Streetwear essentials' visual mood board",
    "Generate a 'Breakfast in bed' shoppable collage",
]

# ============================================================
# AMAZON SEARCH QUERIES for crawling images
# ============================================================

# For Virtual Try-On: need user portraits (model photos) + clothing items
CLOTHING_QUERIES = [
    "denim jacket men", "red blazer women", "floral summer dress",
    "leather motorcycle jacket", "navy suit men", "oversized hoodie",
    "striped button down shirt", "cashmere sweater", "plaid flannel shirt",
    "cropped denim vest", "white linen blazer", "puffer jacket women",
    "trench coat men", "graphic tee men", "cardigan women",
    "polo shirt men", "silk blouse women", "bomber jacket",
    "turtleneck sweater", "chambray shirt", "quilted gilet",
    "hawaiian shirt men", "corduroy blazer", "athletic zip jacket",
    "cable knit sweater", "double breasted coat", "henley shirt men",
    "windbreaker jacket", "linen camp collar shirt", "velvet blazer women",
    "leather jacket men", "denim shirt women",
]

# For user portrait images - search for model photos on amazon
PORTRAIT_QUERIES = [
    "men casual outfit full body", "women dress full body",
    "men suit full body", "women blazer outfit",
    "men jacket outfit model", "women summer dress model",
    "men sweater outfit model", "women coat outfit model",
    "men casual shirt outfit", "women skirt outfit model",
]

# For home images
HOME_QUERIES = [
    "living room furniture set", "modern living room decor",
    "bedroom furniture set", "kitchen decor set",
    "dining room furniture", "home office desk setup",
    "bathroom vanity set", "entryway furniture",
    "cozy living room setup", "modern bedroom set",
]

# For home products (In-Scene Placement)
HOME_PRODUCT_QUERIES = [
    "floor lamp modern", "accent chair living room", "coffee table modern",
    "bookshelf wooden", "throw pillow set", "area rug living room",
    "table lamp bedside", "wall art canvas", "plant stand indoor",
    "ottoman pouf", "desk lamp modern", "side table nightstand",
    "wall mirror decorative", "decorative vase", "pendant light",
    "storage basket woven", "throw blanket cozy", "console table entryway",
    "desk organizer", "wall clock modern", "bar cart gold",
    "floor cushion", "candle set decorative", "shoe rack entryway",
    "tv stand modern", "decorative tray", "curtain rod set",
    "kitchen island cart", "coat rack standing", "floating shelf set",
]

# For Visual Product Search - mixed items
VISUAL_SEARCH_QUERIES = [
    "sneakers white men", "designer handbag women", "denim jacket",
    "coffee table modern", "throw pillow decorative", "sunglasses aviator",
    "desk lamp modern", "area rug geometric", "watch men casual",
    "dining chair modern", "summer dress women", "bookshelf wooden",
    "ankle boots women", "wall art abstract", "backpack canvas",
    "pendant light fixture", "silk scarf women", "side table round",
    "blazer women", "ceramic vase", "running shoes men",
    "throw blanket knit", "fedora hat", "floor mirror full length",
    "drop earrings gold", "ottoman leather", "cardigan oversized",
    "kitchen faucet modern", "crossbody bag leather", "curtain set linen",
]


def get_amazon_image_url(query, index=0):
    """
    Build a direct Amazon search URL and extract image URLs.
    Returns (image_url, product_title) or (None, None).
    """
    search_url = f"https://www.amazon.com/s?k={urllib.parse.quote(query)}&i=fashion"
    if "lamp" in query or "table" in query or "chair" in query or "shelf" in query or \
       "rug" in query or "pillow" in query or "vase" in query or "mirror" in query or \
       "light" in query or "basket" in query or "blanket" in query or "console" in query or \
       "organizer" in query or "clock" in query or "cart" in query or "cushion" in query or \
       "candle" in query or "rack" in query or "stand" in query or "tray" in query or \
       "curtain" in query or "island" in query or "shelf" in query or \
       "furniture" in query or "decor" in query or "bedroom" in query or \
       "living room" in query or "kitchen" in query or "bathroom" in query or \
       "dining" in query or "office" in query or "entryway" in query or \
       "faucet" in query:
        search_url = f"https://www.amazon.com/s?k={urllib.parse.quote(query)}&i=garden"

    req = urllib.request.Request(search_url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"  [ERR] Failed to fetch Amazon search for '{query}': {e}")
        return None, None

    # Extract image URLs from search results
    # Amazon uses data-image attributes and img src with media-amazon.com
    img_pattern = re.compile(r'https://m\.media-amazon\.com/images/I/[A-Za-z0-9_+%-]+\._[^"\']+\.jpg')
    all_imgs = img_pattern.findall(html)
    
    # Filter for product images (reasonable size, not icons)
    product_imgs = []
    seen = set()
    for img in all_imgs:
        # Get base image ID
        base = img.split('._')[0]
        if base not in seen and 'icon' not in img.lower() and 'sprite' not in img.lower():
            seen.add(base)
            # Get a good resolution version
            high_res = base + "._AC_SX679_.jpg"
            product_imgs.append(high_res)

    if not product_imgs:
        print(f"  [WARN] No images found for query '{query}'")
        return None, None

    # Pick image at the requested index (with wrapping)
    idx = index % len(product_imgs)
    return product_imgs[idx], query

def download_amazon_image(query, desc_prefix, index=0):
    """Download an Amazon product image. Returns filename or None."""
    url, title = get_amazon_image_url(query, index)
    if not url:
        return None
    
    filename = sanitize_filename(f"{desc_prefix}_{query}_{index}") + ".png"
    if download_image(url, filename):
        return filename
    return None


def build_all_samples():
    """Build all 240 samples."""
    samples = []
    
    # Track downloaded images to avoid redundant downloads
    image_cache = {}
    
    def get_or_download(query, prefix, index=0):
        """Get cached image or download new one."""
        key = f"{query}_{index}"
        if key in image_cache:
            return image_cache[key]
        fname = download_amazon_image(query, prefix, index)
        if fname:
            image_cache[key] = fname
        return fname
    
    print("=" * 60)
    print("TASK 1: Virtual Try-On (30 samples)")
    print("=" * 60)
    
    portrait_images = []
    # Download portrait/model images
    for i, q in enumerate(PORTRAIT_QUERIES):
        fname = get_or_download(q, "portrait", 0)
        if fname:
            portrait_images.append(fname)
        time.sleep(1)
    
    for i, instruction in enumerate(VIRTUAL_TRYON_INSTRUCTIONS):
        print(f"\n[VTO {i+1}/30] {instruction}")
        portrait = portrait_images[i % len(portrait_images)] if portrait_images else None
        
        # Download 1-3 clothing items
        num_items = random.choice([1, 1, 1, 2, 2, 3])  # weighted toward 1-2
        clothing_imgs = []
        q = CLOTHING_QUERIES[i % len(CLOTHING_QUERIES)]
        for j in range(num_items):
            fname = get_or_download(q if j == 0 else CLOTHING_QUERIES[(i + j) % len(CLOTHING_QUERIES)], "clothing", j)
            if fname:
                clothing_imgs.append(fname)
            time.sleep(0.5)
        
        all_images = []
        if portrait:
            all_images.append(portrait)
        all_images.extend(clothing_imgs)
        
        if all_images:
            samples.append({
                "Type": "Edit",
                "Benchmark": "Virtual Try-On",
                "Task": "Place one or more clothing items onto a user body",
                "Instruction": instruction,
                "Images": json.dumps(all_images)
            })
    
    print("\n" + "=" * 60)
    print("TASK 2: Outfit Styling (30 samples)")
    print("=" * 60)
    
    for i, instruction in enumerate(OUTFIT_STYLING_INSTRUCTIONS):
        print(f"\n[OS {i+1}/30] {instruction}")
        portrait = portrait_images[i % len(portrait_images)] if portrait_images else None
        
        if portrait:
            samples.append({
                "Type": "Edit",
                "Benchmark": "Outfit Styling",
                "Task": "Suggest outfit styling combinations given an anchor clothing item",
                "Instruction": instruction,
                "Images": json.dumps([portrait])
            })
    
    print("\n" + "=" * 60)
    print("TASK 3: Garment Editing (30 samples)")
    print("=" * 60)
    
    for i, instruction in enumerate(GARMENT_EDITING_INSTRUCTIONS):
        print(f"\n[GE {i+1}/30] {instruction}")
        portrait = portrait_images[i % len(portrait_images)] if portrait_images else None
        
        if portrait:
            samples.append({
                "Type": "Edit",
                "Benchmark": "Garment Editing",
                "Task": "Modify clothing attributes in an image such as color, fabric, or fit while preserving the garment structure",
                "Instruction": instruction,
                "Images": json.dumps([portrait])
            })
    
    print("\n" + "=" * 60)
    print("TASK 4: In-Scene Product Placement (30 samples)")
    print("=" * 60)
    
    home_images = []
    for i, q in enumerate(HOME_QUERIES):
        fname = get_or_download(q, "home", 0)
        if fname:
            home_images.append(fname)
        time.sleep(1)
    
    for i, instruction in enumerate(INSCENE_PLACEMENT_INSTRUCTIONS):
        print(f"\n[ISP {i+1}/30] {instruction}")
        home_img = home_images[i % len(home_images)] if home_images else None
        
        # Download 1-3 product images
        num_items = random.choice([1, 1, 1, 2, 2, 3])
        product_imgs = []
        q = HOME_PRODUCT_QUERIES[i % len(HOME_PRODUCT_QUERIES)]
        for j in range(num_items):
            fname = get_or_download(q if j == 0 else HOME_PRODUCT_QUERIES[(i + j) % len(HOME_PRODUCT_QUERIES)], "home_product", j)
            if fname:
                product_imgs.append(fname)
            time.sleep(0.5)
        
        all_images = []
        if home_img:
            all_images.append(home_img)
        all_images.extend(product_imgs)
        
        if all_images:
            samples.append({
                "Type": "Edit",
                "Benchmark": "In-Scene Product Placement",
                "Task": "Insert products into a user-provided home photo with correct scale, lighting, and perspective",
                "Instruction": instruction,
                "Images": json.dumps(all_images)
            })
    
    print("\n" + "=" * 60)
    print("TASK 5: Interior Style Generation (30 samples)")
    print("=" * 60)
    
    for i, instruction in enumerate(INTERIOR_STYLE_INSTRUCTIONS):
        print(f"\n[ISG {i+1}/30] {instruction}")
        home_img = home_images[i % len(home_images)] if home_images else None
        
        if home_img:
            samples.append({
                "Type": "Edit",
                "Benchmark": "Interior Style Generation",
                "Task": "Transform a user-provided home image into a different interior design style",
                "Instruction": instruction,
                "Images": json.dumps([home_img])
            })
    
    print("\n" + "=" * 60)
    print("TASK 6: Home Editing (30 samples)")
    print("=" * 60)
    
    for i, instruction in enumerate(HOME_EDITING_INSTRUCTIONS):
        print(f"\n[HE {i+1}/30] {instruction}")
        home_img = home_images[i % len(home_images)] if home_images else None
        
        if home_img:
            samples.append({
                "Type": "Edit",
                "Benchmark": "Home Editing",
                "Task": "Modify specific elements of a home scene such as furniture, decor, color palette, or materials",
                "Instruction": instruction,
                "Images": json.dumps([home_img])
            })
    
    print("\n" + "=" * 60)
    print("TASK 7: Visual Product Search (30 samples)")
    print("=" * 60)
    
    for i, instruction in enumerate(VISUAL_SEARCH_INSTRUCTIONS):
        print(f"\n[VPS {i+1}/30] {instruction}")
        q = VISUAL_SEARCH_QUERIES[i % len(VISUAL_SEARCH_QUERIES)]
        fname = get_or_download(q, "search_item", 0)
        time.sleep(0.5)
        
        if fname:
            samples.append({
                "Type": "Edit",
                "Benchmark": "Visual Product Search",
                "Task": "Search for exact match products based on image",
                "Instruction": instruction,
                "Images": json.dumps([fname])
            })
    
    print("\n" + "=" * 60)
    print("TASK 8: Shoppable Posts (30 samples)")
    print("=" * 60)
    
    for i, instruction in enumerate(SHOPPABLE_POSTS_INSTRUCTIONS):
        print(f"\n[SP {i+1}/30] {instruction}")
        samples.append({
            "Type": "Generation",
            "Benchmark": "Shoppable Posts",
            "Task": "Generate inspirational visual posts that contain multiple styled products that can be purchased",
            "Instruction": instruction,
            "Images": json.dumps([])
        })
    
    return samples


def write_csv(samples):
    """Write samples to CSV."""
    csv_path = BASE_DIR / "samples.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["Type", "Benchmark", "Task", "Instruction", "Images"])
        writer.writeheader()
        writer.writerows(samples)
    print(f"\n✅ Wrote {len(samples)} samples to {csv_path}")


if __name__ == "__main__":
    print("🚀 Building MM Shopping Benchmark Train Dataset")
    print("=" * 60)
    
    samples = build_all_samples()
    write_csv(samples)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    from collections import Counter
    benchmark_counts = Counter(s["Benchmark"] for s in samples)
    for benchmark, count in sorted(benchmark_counts.items()):
        print(f"  {benchmark}: {count} samples")
    print(f"  TOTAL: {len(samples)} samples")
    
    # Count images
    image_files = list(IMAGES_DIR.glob("*.png"))
    print(f"  Images downloaded: {len(image_files)}")
