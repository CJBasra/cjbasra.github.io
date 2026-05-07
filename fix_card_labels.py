import os
import re

base = "C:/Users/CJBasra/Documents/N1-Payments"

files = [
    "industries/hospitality/index.html",
    "industries/beauty/index.html",
    "industries/retail/index.html",
    "alternate/industries/hospitality/index.html",
    "alternate/industries/beauty/index.html",
    "alternate/industries/retail/index.html",
]

# Match the plain grey label <p> before each h3
pattern = re.compile(
    r'<p class="text-\[12px\] font-bold uppercase tracking-\[0\.18em\] text-\[#767676\]">(.*?)</p>'
    r'(<h3 class="display )(text-\[28px\])',
    re.DOTALL
)

def replacer(m):
    label = m.group(1)
    return (
        f'<div class="flex justify-center">'
        f'<span class="inline-block rounded-full bg-[#DCFB00] px-4 py-1.5 text-[12px] font-bold uppercase tracking-[0.18em] text-black">{label}</span>'
        f'</div>'
        f'{m.group(2)}mt-4 {m.group(3)}'
    )

for rel in files:
    fpath = os.path.join(base, rel)
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    new_content = pattern.sub(replacer, content)
    if new_content != content:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated: {rel}")
    else:
        print(f"No match: {rel}")

print("Done.")
