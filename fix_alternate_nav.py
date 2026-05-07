import os
import re

base = "C:/Users/CJBasra/Documents/N1-Payments"

# Files to update (all alternates with plain Business Funding nav link)
targets = [
    "alternate/about/index.html",
    "alternate/business-account/index.html",
    "alternate/business-funding/index.html",
    "alternate/card-payments/index.html",
    "alternate/contact/index.html",
    "alternate/e-pos/index.html",
    "alternate/index.html",
    "alternate/industries/beauty/index.html",
    "alternate/industries/hospitality/index.html",
    "alternate/industries/retail/index.html",
    "alternate/industries/trade/index.html",
    "alternate/merchant-resources/index.html",
    "alternate/online-payments/index.html",
    "alternate/partners/index.html",
    "alternate/privacy-policy/index.html",
    "alternate/terms-and-conditions/index.html",
]

# Desktop nav: replace plain Business Funding link (active or normal) with dropdown
desktop_normal = '<a href="/alternate/business-funding/" class="nav-link">Business Funding</a>'
desktop_active = '<a href="/alternate/business-funding/" class="nav-link active" aria-current="page">Business Funding</a>'

desktop_dropdown_normal = '''<div class="nav-group">
          <a href="/alternate/business-funding/" class="nav-link dropdown-trigger border-0 bg-transparent p-0">
            <span>Business Funding</span>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="m6 9 6 6 6-6"></path></svg>
          </a>
          <div class="dropdown-panel">
            <a href="/alternate/cash-advance/" class="dropdown-link">Cash Advance</a><a href="/alternate/business-loans/" class="dropdown-link">Business Loans</a>
          </div>
        </div>'''

desktop_dropdown_active = '''<div class="nav-group">
          <a href="/alternate/business-funding/" class="nav-link dropdown-trigger border-0 bg-transparent p-0 active" aria-current="page">
            <span>Business Funding</span>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="m6 9 6 6 6-6"></path></svg>
          </a>
          <div class="dropdown-panel">
            <a href="/alternate/cash-advance/" class="dropdown-link">Cash Advance</a><a href="/alternate/business-loans/" class="dropdown-link">Business Loans</a>
          </div>
        </div>'''

# Mobile nav: add Cash Advance + Business Loans after Business Funding link
mobile_normal = '<a href="/alternate/business-funding/" class="rounded-lg px-4 py-3 text-sm font-semibold text-[#575757]">Business Funding</a>'
mobile_active  = '<a href="/alternate/business-funding/" class="rounded-lg px-4 py-3 text-sm font-semibold bg-brand-light text-black">Business Funding</a>'

mobile_normal_expanded = '''<p class="mobile-menu-label">Business Funding</p>
        <a href="/alternate/business-funding/" class="rounded-lg px-4 py-3 text-sm font-semibold text-[#575757]">Business Funding</a>
        <a href="/alternate/cash-advance/" class="rounded-lg px-4 py-3 text-sm font-semibold text-[#575757]">Cash Advance</a>
        <a href="/alternate/business-loans/" class="rounded-lg px-4 py-3 text-sm font-semibold text-[#575757]">Business Loans</a>'''

mobile_active_expanded = '''<p class="mobile-menu-label">Business Funding</p>
        <a href="/alternate/business-funding/" class="rounded-lg px-4 py-3 text-sm font-semibold bg-brand-light text-black">Business Funding</a>
        <a href="/alternate/cash-advance/" class="rounded-lg px-4 py-3 text-sm font-semibold text-[#575757]">Cash Advance</a>
        <a href="/alternate/business-loans/" class="rounded-lg px-4 py-3 text-sm font-semibold text-[#575757]">Business Loans</a>'''

count = 0
for rel in targets:
    fpath = os.path.join(base, rel)
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    new = content
    # Desktop
    new = new.replace(desktop_active, desktop_dropdown_active)
    new = new.replace(desktop_normal, desktop_dropdown_normal)
    # Mobile
    new = new.replace(mobile_active, mobile_active_expanded)
    new = new.replace(mobile_normal, mobile_normal_expanded)
    if new != content:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(new)
        count += 1
        print(f"Updated: {rel}")
    else:
        print(f"No change: {rel}")

print(f"\nDone. {count} files updated.")
