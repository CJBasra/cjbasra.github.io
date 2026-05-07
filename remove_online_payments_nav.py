import os
import re

base = "C:/Users/CJBasra/Documents/N1-Payments"

# Patterns to remove (whole line containing these)
patterns = [
    r'\s*<a href="/online-payments/" class="nav-link">Online Payments</a>\s*\n',
    r'\s*<a href="/online-payments/" class="rounded-lg px-4 py-3 text-sm font-semibold text-\[#575757\]">Online Payments</a>\s*\n',
    r'\s*<a href="/alternate/online-payments/" class="nav-link">Online Payments</a>\s*\n',
    r'\s*<a href="/alternate/online-payments/" class="rounded-lg px-4 py-3 text-sm font-semibold text-\[#575757\]">Online Payments</a>\s*\n',
]

count = 0
for root, dirs, files in os.walk(base):
    dirs[:] = [d for d in dirs if d != '.git']
    for fname in files:
        if not fname.endswith('.html'):
            continue
        fpath = os.path.join(root, fname)
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        new_content = content
        for pat in patterns:
            new_content = re.sub(pat, '', new_content)
        if new_content != content:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            count += 1
            print(f"Updated: {fpath}")

print(f"\nTotal files updated: {count}")
