"""Fetch product data for all products without published articles."""
import json
import subprocess
import sys
import time

API_BASE = "https://api.affordable-gadgetske.com/api/v1/public/products/"
OUTPUT = "/tmp/product_data.json"

def curl_json(url):
    result = subprocess.run(
        ["curl", "-s", url],
        capture_output=True, text=True, timeout=30
    )
    return json.loads(result.stdout)

page = 1
all_products = []

while True:
    url = f"{API_BASE}?limit=100&page={page}"
    try:
        data = curl_json(url)
    except Exception as e:
        print(f"Error on page {page}: {e}")
        break
    
    results = data.get('results', [])
    if not results:
        break
    
    for r in results:
        if not r.get('has_published_article'):
            all_products.append({
                'slug': r['slug'],
                'product_name': r['product_name'],
                'brand': r.get('brand', '') or '',
                'model_series': r.get('model_series', '') or '',
                'product_type': r.get('product_type', '') or '',
                'min_price': r.get('min_price'),
                'max_price': r.get('max_price'),
                'primary_image': r.get('primary_image', '') or '',
                'long_description': r.get('long_description', '') or '',
                'product_description': r.get('product_description', '') or '',
                'financing_available': r.get('financing_available', False),
            })
    
    print(f"Page {page}: {len(results)} results, {len(all_products)} without articles so far", flush=True)
    
    if not data.get('next'):
        break
    page += 1
    time.sleep(0.2)

with open(OUTPUT, 'w') as f:
    json.dump(all_products, f, indent=2)

print(f"\nDone! Saved {len(all_products)} products to {OUTPUT}")
