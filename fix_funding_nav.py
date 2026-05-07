import os
import re

base = "C:/Users/CJBasra/Documents/N1-Payments"

replacements = [
    # Desktop + mobile nav anchor links → dedicated pages
    ('href="/business-funding/#cash-advance"', 'href="/cash-advance/"'),
    ('href="/business-funding/#business-loans"', 'href="/business-loans/"'),
    ('href="/alternate/business-funding/#cash-advance"', 'href="/alternate/cash-advance/"'),
    ('href="/alternate/business-funding/#business-loans"', 'href="/alternate/business-loans/"'),
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
        for old, new in replacements:
            new_content = new_content.replace(old, new)
        if new_content != content:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            count += 1
            print(f"Updated: {fpath.replace(base, '')}")

print(f"\nTotal files updated: {count}")
