import subprocess
import re

out = subprocess.check_output(['git', 'log', '-p'], text=True, errors='ignore')
patterns = [
    r'(?i)client_secret\s*[:=]\s*[\'\"][^\'\"]+[\'\"]',
    r'(?i)session_secret\s*[:=]\s*[\'\"][a-zA-Z0-9_\-]{16,}[\'\"]',
    r'BEGIN (?:RSA|OPENSSH|PRIVATE) KEY',
    r'AIza[0-9A-Za-z-_]{35}',
    r'ya29\.[0-9A-Za-z-_]+'
]

leaks = []
for p in patterns:
    matches = re.findall(p, out)
    if matches:
        leaks.extend(matches)

print(f"Git history secret scan complete.")
print(f"Total leaks found: {len(leaks)}")
for leak in leaks:
    print(" - Found:", leak)
