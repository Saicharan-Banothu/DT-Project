import re

# 1. Update index.html
with open("frontend/index.html", "r", encoding="utf-8") as f:
    html = f.read()

# Replace specific onclick patterns with data-action
replacements = [
    # Navigation
    (r'onclick="switchPage\(\'([^\']+)\'\)"', r'data-action="switchPage" data-page="\1"'),
    (r'onclick="switchInputTab\(\'([^\']+)\'\)"', r'data-action="switchInputTab" data-tab="\1"'),
    (r'onclick="switchViewMode\(\'([^\']+)\'\)"', r'data-action="switchViewMode" data-mode="\1"'),
    (r'onclick="selectLiveSource\(\'([^\']+)\'\)"', r'data-action="selectLiveSource" data-source="\1"'),
    (r'onclick="toggleVictimChip\(\'([^\']+)\'\)"', r'data-action="toggleVictimChip" data-chip="\1"'),
    (r'onclick="nextOnboardingScreen\((\d+)\)"', r'data-action="nextOnboardingScreen" data-step="\1"'),

    # File input trigger
    (r'onclick="document\.getElementById\(\'audio-file-input\'\)\.click\(\)"', r'data-action="chooseFileInput"'),

    # Compound onclicks
    (r'onclick="closeSignInModal\(\);\s*switchPage\(\'analyze\'\);\s*return false;"', r'data-action="closeSignInModalAndAnalyze"'),
    (r'onclick="openAppLockModal\(\);\s*closeUserDropdown\(\);"', r'data-action="openAppLockModal"'),
    (r'onclick="switchPage\(\'privacy\'\);\s*closeUserDropdown\(\);"', r'data-action="switchPage" data-page="privacy"'),

    # Single function calls
    (r'onclick="([a-zA-Z0-9_]+)\(\)"', r'data-action="\1"'),
]

for pat, repl in replacements:
    html = re.sub(pat, repl, html)

# Remove the inline <script> block for service worker
sw_inline_pattern = r'<script>\s*if \(\'serviceWorker\' in navigator\).*?</script>'
html = re.sub(sw_inline_pattern, '<!-- Service Worker registered via static app.js for CSP compliance -->', html, flags=re.DOTALL)

with open("frontend/index.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Updated frontend/index.html")

# Check if any onclick remains in index.html
rem = re.findall(r'onclick="([^"]+)"', html)
print(f"Remaining onclick in index.html: {len(rem)}", rem)
