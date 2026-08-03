import sys
import urllib.parse
import base64
import gzip
import json
import os

url = sys.argv[1]
out_file = sys.argv[2]

# Extract base64 part
b64 = url.split('#')[1]
b64 = b64.replace('-', '+').replace('_', '/')
pad = len(b64) % 4
if pad:
    b64 += '=' * (4 - pad)
decoded = base64.b64decode(b64)
unzipped = gzip.decompress(decoded).decode('utf-8')

# Try parsing as JSON first
try:
    data = json.loads(unzipped)
    content = data["params"]["sources"][0]["content"]
except Exception:
    # If not JSON, it's raw scad
    content = unzipped

os.makedirs(os.path.dirname(out_file), exist_ok=True)
with open(out_file, 'w') as f:
    f.write(content)

print(f"Successfully extracted to {out_file}")
