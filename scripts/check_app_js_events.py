import re

with open("frontend/app.js", "r", encoding="utf-8") as f:
    js = f.read()

m = re.findall(r'onclick=[\"\']([^\"\']+)[\"\']', js)
print(f"Total onclick in app.js: {len(m)}")
for x in sorted(set(m)):
    print(" -", x)
