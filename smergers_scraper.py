import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from urllib.parse import urljoin
from pathlib import Path
import re

BASE_URL = "https://www.smergers.com/investors"
HEADERS = {"User-Agent": "Mozilla/5.0"}
PAGES = 5  # max pages to crawl

output_file = Path(__file__).resolve().parent / "output" / "investors_smergers.csv"
output_file.parent.mkdir(parents=True, exist_ok=True)

session = requests.Session()
session.headers.update(HEADERS)

results = []

def extract_from_card(card, base_url):
    text = card.get_text(separator="|", strip=True)

    # Profile link: prefer internal link leading to a profile
    profile_link = ""
    a_tags = card.select('a[href]')
    for a in a_tags:
        href = a.get('href')
        if href and not href.startswith('#'):
            # pick first internal profile-like href
            if '/investor' in href or '/buyer' in href or '/profile' in href:
                profile_link = urljoin(base_url, href)
                break
    if not profile_link and a_tags:
        profile_link = urljoin(base_url, a_tags[0].get('href'))

    # Name: look for heading tags or the first strong/text link
    name = ""
    for sel in ('h1','h2','h3','h4','.title','a > h3','a > h2'):
        el = card.select_one(sel)
        if el and el.get_text(strip=True):
            name = el.get_text(strip=True)
            break
    if not name:
        # fallback: first link text
        if a_tags:
            name = a_tags[0].get_text(strip=True)
    if not name:
        # fallback: first line
        name = text.split('|')[0] if text else ''

    # Type: try to find markers like 'Individual Buyer' or 'Investor' in text
    investor_type = ''
    m = re.search(r'(Individual Buyer|Company|Investor|Venture Capitalist|VC|Angel|Private Equity)', text, re.I)
    if m:
        investor_type = m.group(1)

    # Website: external link in card
    website = ''
    for a in a_tags:
        href = a.get('href')
        if href and href.startswith('http') and 'smergers.com' not in href:
            website = href
            break

    # Stage and Sectors: look for keywords 'Interests' or 'Industries' in text
    stage = ''
    sectors = ''
    # Extract segment after 'Interests:'
    m = re.search(r'Interests:?\s*([^|]+)', text, re.I)
    if m:
        sectors = m.group(1).strip()
    m2 = re.search(r'Industries:?\s*([^|]+)', text, re.I)
    if m2:
        sectors = m2.group(1).strip()

    # Investment size or preference can be considered as stage sometimes
    m3 = re.search(r'Investment Size([^|]+)', text, re.I)
    if m3:
        stage = m3.group(1).strip()

    return {
        'Investor Name': name,
        'Type': investor_type,
        'Website': website,
        'Stage': stage,
        'Sectors': sectors,
        'Profile Link': profile_link
    }


def scrape_pages(base_url, pages=5):
    url = base_url
    for page in range(1, pages+1):
        # try page parameter if present
        if page == 1:
            page_url = url
        else:
            # Smergers uses /i/?page=2 in rel=next; use query param
            page_url = f"{url}?page={page}"
        print('Fetching', page_url)
        try:
            r = session.get(page_url, timeout=15)
        except Exception as e:
            print('  request failed', e)
            break
        if r.status_code != 200:
            print('  status', r.status_code)
            break
        soup = BeautifulSoup(r.text, 'html.parser')
        # cards observed as div.listing-card
        cards = soup.select('div.listing-card')
        print('  found cards', len(cards))
        if not cards:
            break
        for c in cards:
            rec = extract_from_card(c, base_url)
            results.append(rec)
        time.sleep(1)

scrape_pages(BASE_URL, PAGES)

if results:
    df = pd.DataFrame(results)
else:
    df = pd.DataFrame(columns=['Investor Name','Type','Website','Stage','Sectors','Profile Link'])

df.to_csv(output_file, index=False)
print('Saved', output_file, 'rows', len(df))
