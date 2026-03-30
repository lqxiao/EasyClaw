import json
import csv
import random
import os

BASE_DIR = "./workspace/MISSIONS/build_mm_shopping_benchmark/mm_shopping_benchmark"

with open(os.path.join(BASE_DIR, "image_metadata.json"), "r") as f:
    meta = json.load(f)

clothing = meta["clothing"]
portrait = meta["portrait"]
home_scene = meta["home_scene"]
home_product = meta["home_product"]
accessory = meta["accessory"]
shoppable = meta["shoppable"]

random.seed(42)

samples = []

# ============================================================
# TASK 1: Virtual Try-On (Edit)
# Input: instruction + full-body portrait + 1-3 clothing items
# ============================================================
tryon_templates = [
    "Put this {item} on me",
    "Show me wearing this {item}",
    "Try this {item} on my body",
    "Can you dress me in this {item}?",
    "Place this {item} on me please",
    "I want to see how this {item} looks on me",
    "Virtually try on this {item} for me",
    "Show what I'd look like in this {item}",
    "Dress me up with this {item}",
    "Apply this {item} to my photo",
    "Put these items on me",
    "Show me wearing these clothes together",
    "Try these pieces on my body",
    "Can you dress me in these items?",
    "Layer these clothing items on me",
]

clothing_items_short = [
    "denim jacket", "leather jacket", "blazer", "summer dress", "maxi dress",
    "cocktail dress", "suit jacket", "cardigan", "hoodie", "trench coat",
    "puffer jacket", "crop top", "polo shirt", "linen shirt", "silk blouse",
    "slim jeans", "chino pants", "midi skirt", "athletic set", "winter coat",
    "casual tee", "shorts", "jumpsuit", "formal vest", "romper",
    "knit sweater", "button-down shirt", "wrap dress", "overcoat", "tunic"
]

for i in range(30):
    p = portrait[i % len(portrait)]
    num_clothes = random.choice([1, 1, 1, 2, 2, 3])
    cloth_indices = random.sample(range(len(clothing)), num_clothes)
    cloth_items = [clothing[j] for j in cloth_indices]
    
    item_name = clothing_items_short[i % len(clothing_items_short)]
    template = tryon_templates[i % len(tryon_templates)]
    instruction = template.format(item=item_name)
    
    images = [p["filename"]] + [c["filename"] for c in cloth_items]
    
    samples.append({
        "Type": "Edit",
        "Benchmark": "Virtual Try-On",
        "Task": "Place one or more clothing items onto a user body",
        "Instruction": instruction,
        "Images": "; ".join(images)
    })

# ============================================================
# TASK 2: Outfit Styling (Edit)
# Input: instruction + full-body portrait
# ============================================================
outfit_templates = [
    "Generate outfit ideas around this {item}",
    "Suggest complete outfits that go with this {item}",
    "Style me with outfits based on this {item}",
    "Create a full look centered on this {item}",
    "What outfits would match this {item}?",
    "Build a stylish outfit around this {item}",
    "Pair this {item} with complementary pieces",
    "Design a head-to-toe look featuring this {item}",
    "Show me outfit combinations with this {item}",
    "Put together a complete outfit using this {item} as the anchor",
    "Recommend styling options for this {item}",
    "Create a casual outfit around this {item}",
    "Style a formal look with this {item}",
    "Generate a street-style outfit with this {item}",
    "Suggest a weekend outfit featuring this {item}",
]

anchor_items = [
    "navy blazer", "white sneakers", "black leather jacket", "floral dress",
    "denim jacket", "khaki chinos", "red heels", "striped shirt",
    "wool cardigan", "pleated skirt", "bomber jacket", "linen pants",
    "silk scarf", "ankle boots", "oversized hoodie", "tailored trousers",
    "graphic tee", "midi dress", "suede loafers", "cropped jacket",
    "turtleneck sweater", "wide-leg pants", "puffer vest", "wrap blouse",
    "cargo pants", "ballet flats", "trench coat", "denim shorts",
    "velvet blazer", "maxi skirt"
]

for i in range(30):
    p = portrait[i % len(portrait)]
    item = anchor_items[i]
    template = outfit_templates[i % len(outfit_templates)]
    instruction = template.format(item=item)
    
    samples.append({
        "Type": "Edit",
        "Benchmark": "Outfit Styling",
        "Task": "Suggest outfit styling combinations given an anchor clothing item",
        "Instruction": instruction,
        "Images": p["filename"]
    })

# ============================================================
# TASK 3: Garment Editing (Edit)
# Input: instruction + full-body portrait
# ============================================================
garment_edit_instructions = [
    "Change the red dress to a blue silk version",
    "Make this jacket leather instead of denim",
    "Convert this dress from short to floor-length",
    "Change the fabric of this shirt to linen",
    "Turn this black blazer into a white one",
    "Make this skirt longer and add a floral pattern",
    "Change the color of these pants from khaki to navy",
    "Convert this casual shirt into a formal button-down",
    "Add a belt to this dress and change it to emerald green",
    "Make this sweater into a cropped version in pastel pink",
    "Change the neckline of this top from round to V-neck",
    "Transform this cotton dress into a satin evening gown",
    "Make this jacket oversized and change it to olive green",
    "Convert these straight-leg jeans to bootcut in dark wash",
    "Change this solid blouse to have a polka dot pattern",
    "Make this winter coat lighter and change it to camel color",
    "Transform this t-shirt into a long-sleeve henley in burgundy",
    "Change this plaid shirt to a solid chambray blue",
    "Make this midi skirt into a mini and change to leather material",
    "Convert this pullover hoodie to a zip-up in heather gray",
    "Change the sleeves of this dress from long to cap sleeves",
    "Transform this casual blazer into a structured formal one in charcoal",
    "Make this cotton cardigan into a cashmere version in cream",
    "Change this striped top to a color-blocked design in teal and white",
    "Convert this fitted dress to an A-line silhouette in lavender",
    "Make this denim jacket distressed and add a sherpa lining",
    "Change this plain white shirt to have French cuffs and subtle pinstripes",
    "Transform this summer dress from sleeveless to off-shoulder in coral",
    "Make this wool trousers into wide-leg palazzo pants in taupe",
    "Change this polo shirt to a mandarin collar style in sage green"
]

for i in range(30):
    p = portrait[i % len(portrait)]
    instruction = garment_edit_instructions[i]
    
    samples.append({
        "Type": "Edit",
        "Benchmark": "Garment Editing",
        "Task": "Modify clothing attributes in an image such as color, fabric, or fit while preserving the garment structure",
        "Instruction": instruction,
        "Images": p["filename"]
    })

# ============================================================
# TASK 4: In-Scene Product Placement (Edit)
# Input: instruction + home picture + 1-3 product pictures
# ============================================================
placement_templates = [
    "Place this {product} in the {room}",
    "Add this {product} to the {room} scene",
    "Insert this {product} into my {room} photo",
    "Put this {product} in the corner of the {room}",
    "Show how this {product} would look in my {room}",
    "Virtually place this {product} in the {room}",
    "Can you add this {product} to my {room}?",
    "Position this {product} in the {room} naturally",
    "Show this {product} staged in the {room}",
    "Place these products in the {room} scene",
]

products_short = [
    "floor lamp", "table lamp", "throw pillows", "wall art", "area rug",
    "bookshelf", "coffee table", "side table", "plant pot", "curtains",
    "wall mirror", "ceramic vase", "pendant light", "storage ottoman",
    "desk lamp", "floating shelf", "candle holders", "wall clock",
    "throw blanket", "picture frames"
]

rooms = ["living room", "bedroom", "kitchen", "dining room", "bathroom",
         "home office", "patio", "nursery", "entryway", "study"]

for i in range(30):
    h = home_scene[i % len(home_scene)]
    num_products = random.choice([1, 1, 2, 2, 3])
    prod_indices = random.sample(range(len(home_product)), num_products)
    prod_items = [home_product[j] for j in prod_indices]
    
    product = products_short[i % len(products_short)]
    room = rooms[i % len(rooms)]
    template = placement_templates[i % len(placement_templates)]
    instruction = template.format(product=product, room=room)
    
    images = [h["filename"]] + [p["filename"] for p in prod_items]
    
    samples.append({
        "Type": "Edit",
        "Benchmark": "In-Scene Product Placement",
        "Task": "Insert products into a user-provided home photo with correct scale, lighting, and perspective",
        "Instruction": instruction,
        "Images": "; ".join(images)
    })

# ============================================================
# TASK 5: Interior Style Generation (Edit)
# Input: instruction + home image
# ============================================================
interior_style_instructions = [
    "Transform this room into a modern minimalist style",
    "Redesign this space in Scandinavian style",
    "Generate a bohemian-inspired version of this room",
    "Convert this room to an industrial loft aesthetic",
    "Restyle this space in mid-century modern design",
    "Transform this room into a coastal beach house style",
    "Redesign this space with a rustic farmhouse look",
    "Generate an Art Deco inspired version of this room",
    "Convert this room to a Japanese zen minimalist style",
    "Restyle this space in contemporary luxury design",
    "Transform this room into a French country style",
    "Redesign this space with a tropical resort aesthetic",
    "Generate a Mediterranean-inspired version of this room",
    "Convert this room to a Moroccan-themed design",
    "Restyle this space in a classic traditional style",
    "Transform this room into an eclectic maximalist design",
    "Redesign this space with a sleek urban modern look",
    "Generate a vintage retro-inspired version of this room",
    "Convert this room to a warm transitional style",
    "Restyle this space in a monochromatic modern design",
    "Transform this room into a nature-inspired biophilic design",
    "Redesign this space with a glamorous Hollywood Regency style",
    "Generate a cozy hygge-inspired version of this room",
    "Convert this room to a clean Bauhaus-influenced design",
    "Restyle this space in a warm Tuscan villa aesthetic",
    "Transform this room into a sleek futuristic design",
    "Redesign this space with a charming cottage core style",
    "Generate a sophisticated hotel-lobby inspired version of this room",
    "Convert this room to a vibrant Mexican hacienda style",
    "Restyle this space in a serene spa-like wellness design"
]

for i in range(30):
    h = home_scene[i % len(home_scene)]
    instruction = interior_style_instructions[i]
    
    samples.append({
        "Type": "Edit",
        "Benchmark": "Interior Style Generation",
        "Task": "Transform a user-provided home image into a different interior design style",
        "Instruction": instruction,
        "Images": h["filename"]
    })

# ============================================================
# TASK 6: Home Editing (Edit)
# Input: instruction + home image
# ============================================================
home_edit_instructions = [
    "Replace the coffee table with a marble-top version",
    "Change the wall color from white to sage green",
    "Swap the sofa fabric from leather to velvet in navy blue",
    "Replace the wooden floor with herringbone tile",
    "Change the kitchen countertop from granite to white quartz",
    "Replace the curtains with floor-to-ceiling linen drapes in cream",
    "Swap the dining chairs with modern upholstered ones",
    "Change the bathroom tiles from white to subway pattern in black",
    "Replace the ceiling fan with a modern chandelier",
    "Change the cabinet hardware from silver to brass",
    "Replace the area rug with a larger Persian-style one",
    "Change the backsplash to white marble herringbone tile",
    "Swap the bedframe from wood to upholstered in gray velvet",
    "Replace the pendant lights with industrial Edison bulb fixtures",
    "Change the fireplace surround from brick to white marble",
    "Replace the window blinds with Roman shades in natural linen",
    "Change the staircase railing from wood to black metal",
    "Swap the bathroom mirror with a round gold-framed one",
    "Replace the kitchen island stools with woven rattan ones",
    "Change the door from a panel style to a modern flush design",
    "Replace the bookshelf with built-in floor-to-ceiling shelving",
    "Change the throw pillows to a mix of mustard and teal patterns",
    "Swap the nightstands with floating wall-mounted shelves",
    "Replace the desk with a standing desk in walnut finish",
    "Change the light switch plates from white to brushed nickel",
    "Replace the outdoor furniture with a modern teak set",
    "Change the shower head from standard to rainfall style in matte black",
    "Swap the kitchen faucet with a pull-down sprayer in brushed gold",
    "Replace the closet doors with sliding barn doors in white",
    "Change the ceiling from flat white to exposed wooden beams"
]

for i in range(30):
    h = home_scene[i % len(home_scene)]
    instruction = home_edit_instructions[i]
    
    samples.append({
        "Type": "Edit",
        "Benchmark": "Home Editing",
        "Task": "Modify specific elements of a home scene such as furniture, decor, color palette, or materials",
        "Instruction": instruction,
        "Images": h["filename"]
    })

# ============================================================
# TASK 7: Visual Product Search (Edit)
# Input: instruction + image with clothing/furniture/decor
# ============================================================
search_templates = [
    "Find the exact same {item} from this photo",
    "Search for this {item} - I want to buy it",
    "Can you identify and find this {item}?",
    "I saw this {item} and want to purchase it, find it for me",
    "Locate this exact {item} for purchase",
    "Help me find where to buy this {item}",
    "Search for a match to this {item}",
    "I need to find this {item} online",
    "Find me the same {item} shown in this image",
    "Identify this {item} and show me where to get it",
]

search_items_clothing = [
    "sneakers", "heels", "boots", "sandals", "loafers",
    "backpack", "handbag", "watch", "sunglasses", "hat",
    "scarf", "belt", "necklace", "earrings", "wallet",
]

search_items_home = [
    "lamp", "throw pillow", "wall art", "rug", "bookshelf",
    "coffee table", "side table", "plant pot", "mirror", "vase",
    "pendant light", "ottoman", "shelf", "candle holder", "clock",
]

# Mix of accessories and home products
all_search_images = accessory + home_product[:15]
all_search_items = search_items_clothing + search_items_home

for i in range(30):
    img = all_search_images[i % len(all_search_images)]
    item = all_search_items[i % len(all_search_items)]
    template = search_templates[i % len(search_templates)]
    instruction = template.format(item=item)
    
    samples.append({
        "Type": "Edit",
        "Benchmark": "Visual Product Search",
        "Task": "Search for exact match products based on image",
        "Instruction": instruction,
        "Images": img["filename"]
    })

# ============================================================
# TASK 8: Shoppable Posts (Generation)
# Input: instruction only (no images)
# ============================================================
shoppable_instructions = [
    "Create a 'Baking Essentials' shoppable collage with must-have tools",
    "Generate a 'Morning Yoga Routine' shoppable post with yoga gear",
    "Design a 'Weekend Camping Trip' shoppable mood board",
    "Create a 'Spring Garden Starter Kit' shoppable visual post",
    "Generate an 'Artist's Studio Essentials' shoppable collage",
    "Design a 'Coffee Lover's Corner' shoppable post with brewing gear",
    "Create a 'New Puppy Welcome Kit' shoppable visual",
    "Generate a 'Beach Day Essentials' shoppable mood board",
    "Design a 'Perfect Picnic Setup' shoppable collage",
    "Create a 'Self-Care Sunday Spa Kit' shoppable post",
    "Generate a 'Home Gym Starter Pack' shoppable visual",
    "Design a 'Craft Cocktail Night' shoppable mood board",
    "Create a 'Cozy Reading Nook' shoppable collage with books and decor",
    "Generate a 'BBQ Master's Toolkit' shoppable post",
    "Design a 'Meditation & Mindfulness Kit' shoppable visual",
    "Create a 'Work From Home Essentials' shoppable collage",
    "Generate a 'Date Night Outfit' shoppable post for couples",
    "Design a 'Kids Birthday Party Supplies' shoppable mood board",
    "Create a 'Plant Parent Starter Kit' shoppable visual",
    "Generate a 'Travel Packing Essentials' shoppable collage",
    "Design a 'Minimalist Kitchen Makeover' shoppable post",
    "Create a 'Outdoor Movie Night Setup' shoppable mood board",
    "Generate a 'Sustainable Living Essentials' shoppable visual",
    "Design a 'Holiday Gift Guide for Her' shoppable collage",
    "Create a 'Fitness Recovery Kit' shoppable post with foam rollers and gear",
    "Generate a 'Dorm Room Essentials' shoppable mood board",
    "Design a 'Sunday Brunch Hosting Kit' shoppable visual",
    "Create a 'Winter Skincare Routine' shoppable collage",
    "Generate a 'Pet-Friendly Home Decor' shoppable post",
    "Design a 'Summer Festival Outfit Guide' shoppable mood board"
]

for i in range(30):
    instruction = shoppable_instructions[i]
    
    samples.append({
        "Type": "Generation",
        "Benchmark": "Shoppable Posts",
        "Task": "Generate inspirational visual posts that contain multiple styled products that can be purchased",
        "Instruction": instruction,
        "Images": ""
    })

# Write CSV
csv_path = os.path.join(BASE_DIR, "samples.csv")
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["Type", "Benchmark", "Task", "Instruction", "Images"])
    writer.writeheader()
    writer.writerows(samples)

print(f"Total samples: {len(samples)}")
print(f"CSV written to: {csv_path}")

# Summary
from collections import Counter
task_counts = Counter(s["Benchmark"] for s in samples)
for task, count in task_counts.items():
    print(f"  {task}: {count} samples")
