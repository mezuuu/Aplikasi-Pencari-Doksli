"""Test deeply parsing Google Lens response to extract images."""
import os, sys, requests, re, json, html as html_mod

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
})

media_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media')
test_image = None
for subdir in ['queries', 'uploads', 'masked', 'originals']:
    dirpath = os.path.join(media_root, subdir)
    if os.path.isdir(dirpath):
        for f in os.listdir(dirpath):
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                test_image = os.path.join(dirpath, f)
                break
    if test_image:
        break

print(f"Test image: {test_image}")

try:
    with open(test_image, 'rb') as f:
        img_data = f.read()
    
    print("\n--- Sending request to Google Lens ---")
    resp = session.post(
        'https://lens.google.com/v3/upload',
        files={'encoded_image': ('image.jpg', img_data, 'image/jpeg')},
        data={'sbisrc': '1'},
        timeout=30,
        allow_redirects=True,
    )
    print(f"Status: {resp.status_code}")
    print(f"URL: {resp.url[:100]}")
    
    if resp.status_code == 200:
        html_content = resp.text
        # Save HTML for manual inspection if needed
        with open('lens_debug.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        print("Saved response to lens_debug.html")

        # 1. Look for AF_initDataCallback patterns which hold JSON data in Google pages
        callbacks = re.findall(r'AF_initDataCallback\(\{key:\s*\'[^\']+\',\s*data:\s*(\[.*?\])\s*\}\);', html_content, re.DOTALL)
        print(f"\nFound {len(callbacks)} AF_initDataCallback arrays")
        
        extracted_urls = set()
        
        for i, cb in enumerate(callbacks):
            if len(cb) < 500: continue # Skip small arrays
            
            # Use regex to find URLs within the JSON array string
            # Google often stores external URLs inside arrays
            urls = re.findall(r'"(https?://[^"]+\.(?:jpg|jpeg|png|webp)(?:\?[^"]*)?)"', cb)
            urls = [u for u in urls if 'gstatic.com' not in u and 'google.com' not in u and 'googleusercontent' not in u]
            
            if urls:
                print(f"  Callback {i} ({len(cb)} chars) has {len(urls)} image URLs")
                for u in urls[:3]:
                    print(f"    -> {u[:100]}")
                extracted_urls.update(urls)
                
            # Also look for page URLs where the image was found
            page_urls = re.findall(r'"(https?://(?:www\.)?(?:instagram|facebook|twitter|x|tiktok)\.com/[^"]+)"', cb)
            if page_urls:
                print(f"  Callback {i} has {len(page_urls)} social media URLs")
                for u in page_urls[:3]:
                    print(f"    -> {u[:100]}")
                    
        # 2. Look for the newer data format (WrbQualifiers or similar)
        # Often data is in <script nonce="...">...</script> containing JSON-like structures
        script_blocks = re.findall(r'<script nonce="[^"]*">(.*?)</script>', html_content, re.DOTALL)
        print(f"\nFound {len(script_blocks)} script blocks")
        for i, script in enumerate(script_blocks):
            if len(script) > 5000:
                urls = re.findall(r'\["(https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp))"', script)
                urls = [u for u in urls if 'gstatic' not in u and 'google' not in u]
                if urls:
                    print(f"  Script {i} ({len(script)} chars) has {len(urls)} image URLs")
                    for u in urls[:3]:
                        print(f"    -> {u[:100]}")
                    extracted_urls.update(urls)
        
        print(f"\nTotal unique external image URLs extracted: {len(extracted_urls)}")
        for i, u in enumerate(list(extracted_urls)[:10]):
            print(f"  {i+1}: {u}")
            
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\nDone")
