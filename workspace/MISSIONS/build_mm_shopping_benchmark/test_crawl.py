import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

url = "https://www.amazon.com/s?k=denim+jacket+women"
resp = requests.get(url, headers=HEADERS, timeout=15)
print(f"Status: {resp.status_code}")
print(f"Content length: {len(resp.text)}")

soup = BeautifulSoup(resp.text, "html.parser")
imgs = soup.find_all("img", class_="s-image")
print(f"s-image count: {len(imgs)}")

# Try all img tags
all_imgs = soup.find_all("img")
print(f"Total img tags: {len(all_imgs)}")
for img in all_imgs[:10]:
    src = img.get("src", "N/A")
    cls = img.get("class", "N/A")
    print(f"  class={cls}, src={src[:100]}")

# Check if CAPTCHA
if "captcha" in resp.text.lower() or "robot" in resp.text.lower():
    print("CAPTCHA/Robot check detected!")
    
# Save HTML for inspection
with open("/tmp/amazon_test.html", "w") as f:
    f.write(resp.text[:5000])
