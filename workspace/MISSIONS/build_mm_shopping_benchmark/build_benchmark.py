import csv
import os
import re
import json
import time
import random
import urllib.request
import urllib.parse
import hashlib
from pathlib import Path

BASE_DIR = "./workspace/MISSIONS/build_mm_shopping_benchmark/mm_shopping_benchmark_train"
IMG_DIR = os.path.join(BASE_DIR, "images")
CSV_PATH = os.path.join(BASE_DIR, "samples.csv")
os.makedirs(IMG_DIR, exist_ok=True)

# ─────────────────────────────────────────────
# 1.  DIVERSE INSTRUCTIONS  (30 per subtask)
# ─────────────────────────────────────────────

instructions = {
    "Virtual Try-On": [
        "Put this denim jacket on me",
        "Show me wearing this red cocktail dress",
        "Try this navy blue blazer on my photo",
        "Can you put this floral maxi skirt on me?",
        "Show how this leather bomber jacket looks on me",
        "Put this striped Oxford shirt on me please",
        "I want to see myself in this white linen suit",
        "Try on this yellow sundress on my body",
        "Show me wearing this green parka and these black jeans",
        "Put this cashmere sweater and scarf on me",
        "Can I see this plaid flannel shirt on me?",
        "Show me in this sequin evening gown",
        "Try this cropped hoodie and cargo pants on me",
        "Put this tweed blazer on my photo",
        "Show how this tie-dye t-shirt looks on me",
        "I want to try on this silk blouse",
        "Put this puffer vest and turtleneck on me",
        "Show me wearing this off-shoulder top",
        "Try this chambray shirt and chinos on me",
        "Put this velvet dinner jacket on me",
        "Show me in this boho wrap dress",
        "Can you put this athletic tank top and shorts on me?",
        "Try this oversized cardigan on my body",
        "Put this Hawaiian shirt on me",
        "Show me wearing this double-breasted trench coat",
        "I want to see this polka dot midi dress on me",
        "Try on this quilted gilet and henley shirt on me",
        "Put this corduroy jacket on my photo",
        "Show how this asymmetric top and pencil skirt look on me",
        "Put this cable-knit sweater and pleated trousers on me",
    ],
    "Outfit Styling": [
        "Generate outfits around this denim jacket",
        "Style a complete look around this black midi skirt",
        "Build me an outfit centered on this white sneaker",
        "Create three outfit ideas featuring this camel coat",
        "Suggest styling options for this graphic tee",
        "What should I wear with this plaid blazer?",
        "Help me style this leather pencil skirt for date night",
        "Put together a weekend outfit using this hoodie",
        "Create a business-casual look around this navy chino",
        "Style this floral blouse for a spring brunch",
        "Generate an athleisure outfit around these joggers",
        "Suggest a formal outfit with this bow-tie blouse",
        "Build a vacation look featuring this linen shirt",
        "Create a layered fall outfit around this turtleneck",
        "Style a concert outfit using this band tee",
        "Generate a work outfit around this wrap dress",
        "Suggest outfits for this olive cargo jacket",
        "Help me pair this metallic pleated skirt",
        "Create a smart-casual look with this polo shirt",
        "Style this oversized blazer for a street-style look",
        "Build an outfit around this pastel cardigan",
        "Generate a monochrome look using this black turtleneck",
        "Suggest outfits pairing this corduroy jacket",
        "Create a cocktail party look around this satin cami",
        "Style this denim vest for a summer festival",
        "Generate a preppy outfit with this cable-knit vest",
        "Suggest a rainy-day outfit around this trench coat",
        "Build a minimalist outfit using this white button-down",
        "Create a boho outfit around this crochet top",
        "Style this puffer jacket for a ski-trip look",
    ],
    "Garment Editing": [
        "Change this red dress to blue silk",
        "Make this cotton blazer look like velvet",
        "Switch the color of this hoodie from grey to forest green",
        "Turn this slim-fit jean into a relaxed wide-leg cut",
        "Change the fabric of this skirt from denim to leather",
        "Make this short-sleeve shirt into a long-sleeve version",
        "Convert this solid white tee into a navy stripe pattern",
        "Change this midi dress to a mini length",
        "Replace the buttons on this cardigan with a zipper",
        "Turn this matte jacket into a glossy patent finish",
        "Change this floral print dress to a geometric pattern",
        "Make this loose blouse into a fitted crop top",
        "Switch this linen pants color from beige to charcoal",
        "Change this round-neck sweater to a V-neck",
        "Turn this pleated skirt into a pencil skirt silhouette",
        "Make this polyester blouse look like silk chiffon",
        "Change the color of this trench coat from khaki to black",
        "Convert this full-length gown to a knee-length cocktail dress",
        "Turn this plain t-shirt into a tie-dye pattern",
        "Change this wool coat to a lighter cotton blend for spring",
        "Make this straight-leg pant into a tapered jogger style",
        "Switch this tank top from white to coral pink",
        "Change the neckline of this dress from crew to sweetheart",
        "Turn this casual flannel into a more polished plaid shirt",
        "Make this denim jacket look distressed and vintage",
        "Change this puffer jacket from black to metallic silver",
        "Convert this maxi skirt to an A-line midi",
        "Turn this satin blouse into a matte crepe version",
        "Change this polo shirt from solid navy to color-blocked",
        "Make this oversized sweater into a fitted ribbed knit",
    ],
    "In-Scene Product Placement": [
        "Place this floor lamp in the corner of my living room",
        "Put this area rug under the coffee table in my room",
        "Add this bookshelf against the empty wall in my study",
        "Place this potted fiddle-leaf fig next to my sofa",
        "Put this accent chair in the reading nook of my bedroom",
        "Add this pendant light above my dining table",
        "Place this console table in my entryway",
        "Put this decorative mirror above my fireplace mantel",
        "Add this bar cart next to the kitchen island",
        "Place this ottoman in front of my sectional sofa",
        "Put this desk lamp on my home-office desk",
        "Add this throw blanket on my living room couch",
        "Place this side table next to my bed",
        "Put this wall art above the sofa in my living room",
        "Add this standing coat rack near my front door",
        "Place this TV stand along the main wall of my den",
        "Put this ceramic vase on my dining table",
        "Add this storage bench at the foot of my bed",
        "Place this wine rack on my kitchen counter",
        "Put this table lamp on my nightstand",
        "Add this hanging planter by my living room window",
        "Place this shoe rack in my closet area",
        "Put this decorative tray on my coffee table",
        "Add this floor-to-ceiling bookcase in my home library",
        "Place this kitchen island cart in my small kitchen",
        "Put this desk organizer on my workspace",
        "Add this rocking chair to my nursery",
        "Place this umbrella stand by the front door",
        "Put this set of floating shelves on the bathroom wall",
        "Add this bean bag chair in the kids' playroom",
    ],
    "Interior Style Generation": [
        "Transform my living room into a mid-century modern style",
        "Generate a Scandinavian design for this bedroom",
        "Redesign my kitchen in a farmhouse style",
        "Convert this room to an industrial loft aesthetic",
        "Make my living room look like a Japanese minimalist space",
        "Transform this bedroom into a coastal beach house style",
        "Redesign my dining room in Art Deco style",
        "Give this room a bohemian eclectic makeover",
        "Convert my study into a traditional English library",
        "Transform this space into a contemporary urban apartment",
        "Make my bathroom look like a luxury spa retreat",
        "Redesign this living room in a rustic cabin style",
        "Give my bedroom a Hollywood Regency glamour look",
        "Transform this kitchen into a sleek modern European style",
        "Convert this room into a tropical paradise theme",
        "Make my living room feel like a Parisian apartment",
        "Redesign this space in a Memphis design style",
        "Give my dining room a Mediterranean villa aesthetic",
        "Transform this bedroom into a maximalist jewel-toned space",
        "Convert my home office into a cozy cottagecore style",
        "Make this bathroom look like a Moroccan hammam",
        "Redesign my living room with a desert Southwest theme",
        "Give this room a retro 1970s sunken-living-room vibe",
        "Transform this kitchen into a French country style",
        "Convert this bedroom to a serene Zen garden aesthetic",
        "Make my dining room look like a modern steakhouse",
        "Redesign this space in a Wabi-Sabi style",
        "Give my living room a transitional classic-meets-modern look",
        "Transform this room into a colorful Indian-inspired space",
        "Convert my bedroom into a luxe hotel suite style",
    ],
    "Home Editing": [
        "Replace the coffee table with a marble-top version",
        "Change the wall color from white to sage green",
        "Swap the curtains for floor-length velvet drapes",
        "Replace the sofa cushions with navy blue ones",
        "Change the hardwood floor to white marble tile",
        "Replace the ceiling fan with a modern chandelier",
        "Swap the kitchen backsplash for subway tiles",
        "Change the dining chairs from wood to upholstered",
        "Replace the area rug with a Persian-style carpet",
        "Change the cabinet hardware to brass handles",
        "Swap the bedside lamps for wall-mounted sconces",
        "Replace the kitchen countertop with butcher block",
        "Change the bathroom vanity to a floating modern design",
        "Swap the front door for a black steel-framed glass door",
        "Replace the TV console with a built-in media wall",
        "Change the staircase railing from wood to wrought iron",
        "Swap the shower curtain for a frameless glass enclosure",
        "Replace the window blinds with plantation shutters",
        "Change the fireplace surround from brick to stone",
        "Swap the pendant lights for industrial Edison bulbs",
        "Replace the bookshelf with floor-to-ceiling built-ins",
        "Change the wall paneling from drywall to shiplap",
        "Swap the bar stools for rattan counter chairs",
        "Replace the bedroom headboard with a tufted velvet one",
        "Change the outdoor deck railing to cable wire",
        "Swap the laundry room shelves for closed cabinetry",
        "Replace the garage door with a carriage-style door",
        "Change the living room accent wall to exposed brick",
        "Swap the kitchen island for a butcher-block cart",
        "Replace the bathroom mirror with a round gold-framed one",
    ],
    "Visual Product Search": [
        "Find the exact same sneakers from this photo",
        "Search for this coffee table I spotted in the picture",
        "Find me the same floral curtains shown here",
        "Identify and find this leather handbag for purchase",
        "Search for the same throw pillow in this image",
        "Find me this exact desk lamp from the photo",
        "Where can I buy the same dining chair shown here?",
        "Search for this patterned area rug I see in the picture",
        "Find the same wall clock from this room photo",
        "Identify this pendant light and find it for sale",
        "Search for the exact same boots in this outfit photo",
        "Find me this wooden bookshelf from the image",
        "Where can I get the same ceramic planter shown here?",
        "Search for this striped blazer from the street-style photo",
        "Find the same velvet accent chair in this picture",
        "Identify this watch and find where to buy it",
        "Search for the exact same sunglasses in this selfie",
        "Find me this woven basket from the room photo",
        "Where can I buy the same bar cart shown here?",
        "Search for this quilted jacket from the photo",
        "Find the same table runner in this dining room image",
        "Identify this floor mirror and find it online",
        "Search for the exact same crossbody bag in this photo",
        "Find me this macrame wall hanging from the picture",
        "Where can I get the same knit beanie shown here?",
        "Search for this mid-century side table from the photo",
        "Find the same canvas tote bag in this image",
        "Identify this scented candle holder and find it for sale",
        "Search for the exact same denim overalls in this photo",
        "Find me this geometric shelf from the room picture",
    ],
    "Shoppable Posts": [
        "Create a 'Baking essentials' shoppable collage",
        "Generate a 'Cozy fall reading nook' shoppable post",
        "Create a 'Summer beach day must-haves' visual post",
        "Generate a 'Work from home desk setup' shoppable collage",
        "Create a 'Date night outfit inspiration' styled post",
        "Generate a 'Minimalist bathroom essentials' collage",
        "Create a 'Weekend brunch table setting' shoppable post",
        "Generate a 'Outdoor patio party setup' visual collage",
        "Create a 'Back to school supplies' shoppable post",
        "Generate a 'Holiday gift guide for her' visual post",
        "Create a 'Morning skincare routine' shoppable collage",
        "Generate a 'Camping gear checklist' visual post",
        "Create a 'Nursery room essentials' shoppable collage",
        "Generate a 'Home bar starter kit' visual post",
        "Create a 'Yoga and meditation corner' shoppable post",
        "Generate a 'Vintage-inspired living room' styled collage",
        "Create a 'Pet owner starter pack' shoppable post",
        "Generate a 'Spring garden essentials' visual collage",
        "Create a 'College dorm room makeover' shoppable post",
        "Generate a 'Sustainable kitchen swaps' visual post",
        "Create a 'Winter layering outfit guide' shoppable collage",
        "Generate a 'Home gym essentials' visual post",
        "Create a 'Rainy day self-care kit' shoppable collage",
        "Generate a 'Kids birthday party supplies' visual post",
        "Create a 'Aesthetic desk accessories' shoppable collage",
        "Generate a 'Boho bedroom makeover' styled post",
        "Create a 'Travel packing essentials' shoppable post",
        "Generate a 'Thanksgiving dinner table' visual collage",
        "Create a 'New apartment starter kit' shoppable post",
        "Generate a 'Summer cocktail party setup' visual collage",
    ],
}

# ─────────────────────────────────────────────
# 2.  AMAZON IMAGE SEARCH QUERIES  (per task)
# ─────────────────────────────────────────────

# For each subtask, define search queries to get relevant images
# We need different image types:
#   - "portrait": full-body model photos (clothing on model)
#   - "home": room/home photos (showroom images)
#   - "product": individual product images
#   - "clothing_product": individual clothing product images
#   - "home_product": home product images

amazon_queries = {
    "Virtual Try-On": {
        "portrait": [
            "women full body outfit", "men casual outfit full body",
            "women summer dress model", "men business casual outfit",
            "women winter coat model photo", "men jacket outfit",
            "women athletic wear full body", "men formal suit model",
            "women bohemian dress", "men streetwear outfit"
        ],
        "clothing_product": [
            "denim jacket women", "red cocktail dress", "navy blue blazer men",
            "floral maxi skirt", "leather bomber jacket", "striped oxford shirt men",
            "white linen suit", "yellow sundress", "green parka women", "black jeans men",
            "cashmere sweater", "wool scarf", "plaid flannel shirt",
            "sequin evening gown", "cropped hoodie women", "cargo pants",
            "tweed blazer women", "tie-dye t-shirt", "silk blouse",
            "puffer vest", "turtleneck sweater", "off-shoulder top",
            "chambray shirt", "chinos men", "velvet dinner jacket",
            "boho wrap dress", "athletic tank top", "oversized cardigan",
            "hawaiian shirt men", "double-breasted trench coat",
            "polka dot midi dress", "quilted gilet", "henley shirt men",
            "corduroy jacket", "cable-knit sweater", "pleated trousers"
        ],
    },
    "Outfit Styling": {
        "portrait": [
            "women casual outfit full body", "men smart casual full body",
            "women office outfit model", "men weekend outfit",
            "women party outfit", "men layered outfit",
            "women athleisure outfit", "men preppy style",
            "women minimalist outfit", "men outdoor style"
        ],
    },
    "Garment Editing": {
        "portrait": [
            "women red dress full body", "men cotton blazer outfit",
            "women grey hoodie outfit", "men slim fit jeans",
            "women denim skirt outfit", "men short sleeve shirt outfit",
            "women white t-shirt outfit", "men midi coat outfit",
            "women cardigan outfit full body", "men matte jacket outfit",
            "women floral print dress", "men loose blouse outfit",
            "women linen pants outfit", "men round neck sweater",
            "women pleated skirt outfit"
        ],
    },
    "In-Scene Product Placement": {
        "home": [
            "modern living room interior", "cozy bedroom interior",
            "home office setup", "dining room interior design",
            "kitchen interior modern", "entryway foyer decor",
            "reading nook interior", "bathroom modern design",
            "kids playroom interior", "nursery room design"
        ],
        "home_product": [
            "floor lamp modern", "area rug living room", "bookshelf wood",
            "fiddle leaf fig plant", "accent chair living room",
            "pendant light dining", "console table entryway",
            "decorative wall mirror", "bar cart gold", "ottoman round",
            "desk lamp modern", "throw blanket knit", "side table bedroom",
            "wall art abstract", "standing coat rack", "TV stand modern",
            "ceramic vase decorative", "storage bench bedroom",
            "wine rack countertop", "table lamp ceramic",
            "hanging planter indoor", "shoe rack", "decorative tray",
            "bookcase tall", "kitchen island cart", "desk organizer",
            "rocking chair nursery", "umbrella stand", "floating shelves",
            "bean bag chair"
        ],
    },
    "Interior Style Generation": {
        "home": [
            "living room interior design", "bedroom modern interior",
            "kitchen contemporary design", "dining room interior",
            "bathroom design modern", "home office interior",
            "studio apartment interior", "loft apartment design",
            "open concept living room", "small apartment interior"
        ],
    },
    "Home Editing": {
        "home": [
            "living room with coffee table", "modern kitchen interior",
            "bedroom with headboard", "dining room with chandelier",
            "bathroom with vanity", "living room with fireplace",
            "kitchen with island", "bedroom with curtains",
            "entryway with door", "living room with bookshelf"
        ],
    },
    "Visual Product Search": {
        "clothing_product": [
            "sneakers white", "leather handbag women", "striped blazer",
            "quilted jacket", "denim overalls", "crossbody bag",
            "canvas tote bag", "knit beanie", "boots ankle women",
            "sunglasses aviator", "watch men casual"
        ],
        "home_product": [
            "coffee table modern", "floral curtains", "throw pillow decorative",
            "desk lamp", "dining chair modern", "area rug patterned",
            "wall clock modern", "pendant light kitchen", "wooden bookshelf",
            "ceramic planter", "velvet accent chair", "woven basket storage",
            "bar cart", "table runner", "floor mirror full length",
            "macrame wall hanging", "mid-century side table",
            "candle holder decorative", "geometric shelf"
        ],
    },
    "Shoppable Posts": {
        # Generation task - no images needed
    },
}

def sanitize_filename(name, max_len=80):
    """Create a safe filename from a description."""
    name = name.lower().strip()
    name = re.sub(r'[^a-z0-9]+', '_', name)
    name = name.strip('_')[:max_len]
    return name

def download_image(url, filepath):
    """Download an image from a URL."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            data = response.read()
            if len(data) < 5000:  # Skip tiny images (likely placeholders)
                return False
            with open(filepath, 'wb') as f:
                f.write(data)
            return True
    except Exception as e:
        print(f"  Download failed for {url[:80]}: {e}")
        return False

def search_amazon_images(query, num_images=3):
    """Search Amazon and extract product image URLs."""
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://www.amazon.com/s?k={encoded_query}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'identity',
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as response:
            html = response.read().decode('utf-8', errors='ignore')
        
        # Extract image URLs from Amazon search results
        # Amazon uses various image URL patterns
        img_urls = []
        
        # Pattern 1: data-image attribute (common in search results)
        patterns = [
            r'"(https://m\.media-amazon\.com/images/I/[^"]+\.(?:jpg|png))"',
            r'"(https://images-na\.ssl-images-amazon\.com/images/I/[^"]+\.(?:jpg|png))"',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html)
            for m in matches:
                # Get larger version of image
                clean_url = re.sub(r'\._[A-Z][A-Z0-9_,]+_\.', '.', m)
                if clean_url not in img_urls:
                    img_urls.append(clean_url)
        
        # Deduplicate and limit
        seen = set()
        unique_urls = []
        for u in img_urls:
            # Normalize URL for dedup
            base = u.split('?')[0]
            if base not in seen:
                seen.add(base)
                unique_urls.append(u)
        
        return unique_urls[:num_images]
    except Exception as e:
        print(f"  Search failed for '{query}': {e}")
        return []

def crawl_images_for_queries(queries, category, num_per_query=3):
    """Crawl Amazon images for a list of queries. Returns dict of {description: filepath}."""
    results = {}
    for query in queries:
        print(f"  Searching Amazon for: {query}")
        urls = search_amazon_images(query, num_per_query)
        for i, url in enumerate(urls):
            desc = f"{category}_{sanitize_filename(query)}_{i}"
            filepath = os.path.join(IMG_DIR, f"{desc}.png")
            if os.path.exists(filepath):
                results[desc] = filepath
                continue
            if download_image(url, filepath):
                results[desc] = filepath
                print(f"    ✓ Downloaded: {desc}.png")
            else:
                print(f"    ✗ Failed: {desc}")
            time.sleep(random.uniform(1.0, 2.5))  # Be polite
        time.sleep(random.uniform(1.5, 3.0))
    return results

# ─────────────────────────────────────────────
# 3.  MAIN: Crawl images and build CSV
# ─────────────────────────────────────────────

def main():
    all_images = {}  # category -> list of filenames
    
    # Crawl all needed images
    for task_name, query_dict in amazon_queries.items():
        print(f"\n{'='*60}")
        print(f"Crawling images for: {task_name}")
        print(f"{'='*60}")
        for category, queries in query_dict.items():
            cat_key = f"{sanitize_filename(task_name)}_{category}"
            imgs = crawl_images_for_queries(queries, cat_key, num_per_query=3)
            all_images[cat_key] = list(imgs.keys())
            print(f"  → Got {len(imgs)} images for {cat_key}")
    
    # ─────────────────────────────────────────────
    # 4.  BUILD CSV
    # ─────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("Building CSV...")
    print(f"{'='*60}")
    
    rows = []
    
    # Helper to pick random images from a category
    def pick_images(cat_key, n=1):
        available = all_images.get(cat_key, [])
        if not available:
            return []
        n = min(n, len(available))
        return random.sample(available, n)
    
    # Task 1: Virtual Try-On (Edit) - portrait + 1-3 clothing products
    task = "Virtual Try-On"
    portrait_key = "virtual_try_on_portrait"
    clothing_key = "virtual_try_on_clothing_product"
    for i, instr in enumerate(instructions[task]):
        portrait_imgs = pick_images(portrait_key, 1)
        num_clothing = random.randint(1, 3)
        clothing_imgs = pick_images(clothing_key, num_clothing)
        all_imgs = portrait_imgs + clothing_imgs
        img_str = ";".join([f"{img}.png" for img in all_imgs])
        rows.append(["Edit", task, task, instr, img_str])
    
    # Task 2: Outfit Styling (Edit) - portrait only
    task = "Outfit Styling"
    portrait_key = "outfit_styling_portrait"
    for i, instr in enumerate(instructions[task]):
        portrait_imgs = pick_images(portrait_key, 1)
        img_str = ";".join([f"{img}.png" for img in portrait_imgs])
        rows.append(["Edit", task, task, instr, img_str])
    
    # Task 3: Garment Editing (Edit) - portrait only
    task = "Garment Editing"
    portrait_key = "garment_editing_portrait"
    for i, instr in enumerate(instructions[task]):
        portrait_imgs = pick_images(portrait_key, 1)
        img_str = ";".join([f"{img}.png" for img in portrait_imgs])
        rows.append(["Edit", task, task, instr, img_str])
    
    # Task 4: In-Scene Product Placement (Edit) - home + 1-3 products
    task = "In-Scene Product Placement"
    home_key = "in_scene_product_placement_home"
    product_key = "in_scene_product_placement_home_product"
    for i, instr in enumerate(instructions[task]):
        home_imgs = pick_images(home_key, 1)
        num_products = random.randint(1, 3)
        product_imgs = pick_images(product_key, num_products)
        all_imgs = home_imgs + product_imgs
        img_str = ";".join([f"{img}.png" for img in all_imgs])
        rows.append(["Edit", task, task, instr, img_str])
    
    # Task 5: Interior Style Generation (Edit) - home only
    task = "Interior Style Generation"
    home_key = "interior_style_generation_home"
    for i, instr in enumerate(instructions[task]):
        home_imgs = pick_images(home_key, 1)
        img_str = ";".join([f"{img}.png" for img in home_imgs])
        rows.append(["Edit", task, task, instr, img_str])
    
    # Task 6: Home Editing (Edit) - home only
    task = "Home Editing"
    home_key = "home_editing_home"
    for i, instr in enumerate(instructions[task]):
        home_imgs = pick_images(home_key, 1)
        img_str = ";".join([f"{img}.png" for img in home_imgs])
        rows.append(["Edit", task, task, instr, img_str])
    
    # Task 7: Visual Product Search (Edit) - single product image
    task = "Visual Product Search"
    clothing_key = "visual_product_search_clothing_product"
    home_prod_key = "visual_product_search_home_product"
    for i, instr in enumerate(instructions[task]):
        # Alternate between clothing and home product images
        if i < 15:
            imgs = pick_images(clothing_key, 1)
        else:
            imgs = pick_images(home_prod_key, 1)
        img_str = ";".join([f"{img}.png" for img in imgs])
        rows.append(["Edit", task, task, instr, img_str])
    
    # Task 8: Shoppable Posts (Generation) - no images needed
    task = "Shoppable Posts"
    for instr in instructions[task]:
        rows.append(["Generation", task, task, instr, ""])
    
    # Write CSV
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Type", "Benchmark", "Task", "Instruction", "Images"])
        writer.writerows(rows)
    
    print(f"\n✓ CSV written to {CSV_PATH}")
    print(f"  Total samples: {len(rows)}")
    print(f"  Total images: {len(os.listdir(IMG_DIR))}")

if __name__ == "__main__":
    main()

