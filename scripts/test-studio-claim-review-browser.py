#!/usr/bin/env python3
"""Isolated Chromium DOM acceptance, with NO file/network navigation required."""
from pathlib import Path
from playwright.sync_api import sync_playwright
from shutil import which

ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/'web/studio-claim-review-demo.html').read_text()
# This fixture injects source scripts directly into an inert about:blank page.
# The production markup's restrictive CSP and script references remain unchanged.
import re
html=re.sub(r'<meta http-equiv="Content-Security-Policy"[^>]*>', '',html)
html=re.sub(r'<script src="[^"]+"></script>', '',html)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path=which('google-chrome') or which('chromium'),args=['--no-sandbox'])
    page=browser.new_page()
    page.set_content(html)
    for path in ['studio-claim-review.js','studio-claim-review-demo.js']:
        page.add_script_tag(content=(ROOT/'web'/path).read_text())
    assert page.locator('h1').inner_text()=='NEXUS · Claim Review'
    page.locator('#answer').fill('A report in 2025 included 200 volunteers. The therapy caused improvement.')
    page.locator('#review').click()
    assert page.locator('.claim').count()==2
    assert 'NOT been verified' in page.locator('#results').inner_text()
    page.locator('#answer').fill('The result was found in 2025. '+'github_pat_'+'A'*40)
    page.locator('#review').click()
    assert page.locator('.claim').count()==0
    assert 'Possible credential detected' in page.locator('#results').inner_text()
    assert 'github_pat_' not in page.locator('#results').inner_text()
    page.locator('#clear').click()
    assert page.locator('#answer').input_value()==''
    assert page.locator('#results').inner_text()==''
    browser.close()
print('NEXUS claim review DOM acceptance: PASS')
