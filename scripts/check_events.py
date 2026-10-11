import re

with open("frontend/index.html", encoding="utf-8") as f:
    html = f.read()

matches = re.findall(r'onclick="([^"]+)"', html)
print(f"Total onclick handlers: {len(matches)}")
for m in sorted(set(matches)):
    print(" -", m)
