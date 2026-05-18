import os, sys, requests, re, html as html_module

image_path = r'D:\Coding\Capstone Project\backend\media\queries\c3c1efcce51843da8976fdea74b1a924.jpg'

def test_yandex(image_path):
    print(f"Testing Yandex with {image_path}")
    urls = []
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        with open(image_path, 'rb') as f:
            upload_resp = session.post(
                'https://yandex.com/images/search',
                params={'rpt': 'imageview'},
                files={'upfile': ('image.jpg', f, 'image/jpeg')},
                data={'prg': '1'},
                timeout=30,
                allow_redirects=False,
            )
        
        redirect_url = upload_resp.headers.get('Location', '')
        cbir_match = re.search(r'cbir_id=([^&]+)', redirect_url)
        if not cbir_match:
            print("No CBIR ID")
            return
            
        cbir_id = cbir_match.group(1)
        print(f"CBIR ID: {cbir_id}")
        
        for mode in ['sites', 'similar']:
            print(f"\n--- Mode: {mode} ---")
            search_resp = session.get(
                'https://yandex.com/images/search',
                params={'rpt': 'imageview', 'cbir_id': cbir_id, 'cbir_page': mode},
                timeout=30,
            )
            decoded = html_module.unescape(search_resp.text)
            
            raw_urls = re.findall(r'https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)', decoded)
            print(f"Found {len(raw_urls)} total image URLs")
            
            skip_patterns = ['yastatic.net', 'avatars.mds.yandex.net', 'yandex.net', 'favicon', '.css', '.js', '.svg', '.ico', 'yandex.ru']
            valid_urls = []
            
            for url in raw_urls:
                if any(skip in url.lower() for skip in skip_patterns): continue
                if len(url) < 30 or 'data:image' in url: continue
                if url not in valid_urls:
                    valid_urls.append(url)
            
            print(f"Valid external URLs: {len(valid_urls)}")
            for u in valid_urls[:10]:
                print(f"  -> {u}")
                
    except Exception as e:
        print(f"Error: {e}")

test_yandex(image_path)
