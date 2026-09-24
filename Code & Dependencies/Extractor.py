# =============================================================================
# LinkedIn Job Finder
# Copyright (C) 2026  Javier Medina Moreno
# Licence: GNU AGPLv3
# Free to use, modify, and redistribute. Retain original author attribution and copyright notice.
# =============================================================================

import csv
import random
import re
import time
from bs4 import BeautifulSoup
import requests

# ==============================================================================
# USER INPUT FIELDS
# ==============================================================================
# Optional: Extract from URLs
# Paste LinkedIn job URLs or standalone numeric Job IDs below (as a multiline string or list):
TARGET_URLS = """
"""

# ==============================================================================
INPUT_CSV = 'linkedin_jobs.csv'        # CSV exported by Finder.py (set to '' to ignore)
OUTPUT_FILENAME = 'linkedin_job_details.txt'  # Destination text file path
# ==============================================================================


def extract_urls(urls_input) -> list:
    """Extracts and normalizes clean URLs from a multiline string or iterable."""
    if isinstance(urls_input, str):
        lines = [url.strip() for url in urls_input.strip().splitlines() if url.strip()]
        return [normalize_job_url(line) for line in lines if normalize_job_url(line)]
    elif isinstance(urls_input, (list, tuple, set)):
        items = [str(url).strip() for url in urls_input if str(url).strip()]
        return [normalize_job_url(item) for item in items if normalize_job_url(item)]
    return []


def load_target_urls(csv_file: str = '', raw_input: str = '') -> list:
    """Loads and deduplicates URLs from an input CSV file and/or raw input string."""
    urls = []
    seen = set()

    # 1. Load from CSV if provided and exists
    if csv_file:
        try:
            with open(csv_file, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    raw_val = (row.get('url') or '').strip() or (row.get('job_id') or '').strip()
                    url = normalize_job_url(raw_val)
                    if url and url not in seen:
                        seen.add(url)
                        urls.append(url)
            if urls:
                print(f"Loaded {len(urls)} URLs from '{csv_file}'.")
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Warning reading '{csv_file}': {e}")

    # 2. Add raw URLs if provided
    if raw_input:
        for u in extract_urls(raw_input):
            if u not in seen:
                seen.add(u)
                urls.append(u)

    return urls


def get_existing_job_ids(filename: str) -> set:
    """Reads already-extracted job IDs from the destination text file to avoid re-scraping."""
    existing = set()
    try:
        with open(filename, mode='r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('Job ID:'):
                    jid = line.split('Job ID:')[1].strip()
                    if jid:
                        existing.add(jid)
    except FileNotFoundError:
        pass
    return existing


def append_job_to_text_file(job: dict, filename: str, job_number: int):
    """Appends a single extracted job to the text file immediately."""
    with open(filename, mode='a', encoding='utf-8') as f:
        f.write('=' * 80 + '\n')
        f.write(f"JOB #{job_number}: {job['title']}\n")
        f.write('=' * 80 + '\n')
        f.write(f"Job ID:      {job['job_id']}\n")
        f.write(f"Company:     {job['company']}\n")
        f.write(f"Location:    {job['location']}\n")
        f.write(f"Date Posted: {job['date_posted']}\n")
        f.write(f"URL:         {job['url']}\n\n")
        f.write("DESCRIPTION:\n")
        f.write('-' * 80 + '\n')
        f.write(f"{job['description']}\n")
        f.write('=' * 80 + '\n\n')
        f.flush()


def extract_job_id(job_url: str):
    """Extracts the numeric Job ID from various LinkedIn job URL formats."""
    if not job_url:
        return None
    clean_path = job_url.split('?')[0].split('#')[0].rstrip('/')
    match = re.search(r'/jobs/view/(?:.*[-/])?(\d+)$', clean_path) or re.search(r'(\d{8,})', clean_path)
    return match.group(1) if match else None


def normalize_job_url(item: str) -> str:
    """Normalizes a raw Job ID or LinkedIn URL into a clean canonical URL."""
    if not item:
        return ''
    cleaned = item.strip()
    job_id = extract_job_id(cleaned)
    if job_id:
        return f'https://www.linkedin.com/jobs/view/{job_id}/'
    return cleaned


def parse_linkedin_job_url(job_url: str, session: requests.Session = None):
    job_id = extract_job_id(job_url)
    if not job_id:
        print(f"Error: Could not extract Job ID from '{job_url}'.")
        return None

    api_url = f'https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}'

    # 2. Mimic a standard browser to avoid bot blocks
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,'
            ' like Gecko) Chrome/128.0.0.0 Safari/537.36'
        ),
        'Accept': (
            'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        ),
        'Accept-Language': 'en-US,en;q=0.9',
    }

    print(f'Fetching details for Job ID: {job_id}...')

    http = session or requests

    response = None
    for attempt in range(2):
        try:
            response = http.get(api_url, headers=headers, timeout=12)
            if response.status_code == 429:
                if attempt == 0:
                    print('Rate limited (HTTP 429). Pausing 35s before retry...')
                    time.sleep(35)
                    continue
                else:
                    print('Rate limit persists after retry. Skipping job.')
                    return None
            elif response.status_code != 200:
                print(f'Failed to fetch (Status {response.status_code}). Skipping.')
                return None
            break
        except requests.RequestException as e:
            print(f'Network error: {e}')
            return None

    if not response or response.status_code != 200:
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    # 3. Extract the components using targeted CSS selectors
    title_tag = soup.find('h2', class_='top-card-layout__title') or soup.find(
        'h1'
    )
    title = title_tag.get_text(strip=True) if title_tag else 'N/A'

    company_tag = soup.find(
        'a', class_='topcard__org-name-link'
    ) or soup.find('span', class_='topcard__flavor')
    company = company_tag.get_text(strip=True) if company_tag else 'N/A'

    # Location: look for bullet flavor span, excluding posted time metadata
    location = 'N/A'
    bullets = soup.find_all('span', class_='topcard__flavor--bullet')
    for b in bullets:
        classes = b.get('class', [])
        if 'posted-time-ago__text' not in classes and 'topcard__flavor--metadata' not in classes:
            location = b.get_text(strip=True)
            break
    if location == 'N/A' and bullets:
        location = bullets[0].get_text(strip=True)

    # Date posted
    post_age_tag = soup.find('span', class_='posted-time-ago__text')
    date_posted = post_age_tag.get_text(strip=True) if post_age_tag else 'N/A'

    # Description (Preserve internal line breaks cleanly)
    desc_tag = soup.find('div', class_='description__text') or soup.find(
        'div', class_='show-more-less-html__markup'
    )
    if desc_tag:
        # Remove "Show more" / "Show less" toggle buttons from the DOM
        for btn in desc_tag.find_all(['button', 'span', 'a']):
            text = btn.get_text(strip=True).lower()
            classes = ' '.join(btn.get('class', []))
            if 'show more' in text or 'show less' in text or 'show-more-less' in classes:
                btn.decompose()

        description = desc_tag.get_text(separator='\n', strip=True)
        # Remove any trailing "Show more" / "Show less" text leftover
        description = re.sub(r'(?i)(\n\s*show\s+(?:more|less)\s*)+$', '', description).strip()
    else:
        description = 'N/A'

    return {
        'job_id': job_id,
        'title': title,
        'company': company,
        'location': location,
        'date_posted': date_posted,
        'description': description,
        'url': f'https://www.linkedin.com/jobs/view/{job_id}/',
    }

def parse_multiple_job_urls(
    urls: list,
    output_filename: str = 'linkedin_job_details.txt',
    delay_range: tuple = (2.5, 4.5),
) -> list:
    """Processes multiple LinkedIn job URLs sequentially with resuming and anti-bot defenses.

    delay_range defaults to (2.5, 4.5) seconds between requests to avoid rate limits (HTTP 429).
    """
    clean_urls = extract_urls(urls)
    existing_ids = get_existing_job_ids(output_filename)
    if existing_ids:
        print(f"Found {len(existing_ids)} jobs already extracted in '{output_filename}'.")

    # Filter out already extracted jobs
    urls_to_process = []
    for u in clean_urls:
        jid = extract_job_id(u)
        if jid and jid in existing_ids:
            continue
        urls_to_process.append(u)

    total = len(urls_to_process)
    if total == 0:
        print('No new URLs to parse.')
        return []

    results = []
    print(f'Starting bulk extraction for {total} new job URLs...\n')
    session = requests.Session()

    try:
        for idx, url in enumerate(urls_to_process, start=1):
            print(f'[{idx}/{total}] Processing: {url}')
            job = parse_linkedin_job_url(url, session=session)
            if job:
                results.append(job)
                job_num = len(existing_ids) + len(results)
                append_job_to_text_file(job, output_filename, job_num)
                print(f"  -> Extracted: {job['title']} @ {job['company']} (Saved to {output_filename})")

            # Polite delay between requests to prevent HTTP 429 throttling
            if idx < total:
                wait_time = random.uniform(*delay_range)
                time.sleep(wait_time)
    except KeyboardInterrupt:
        print(f"\nExtraction stopped by user (Ctrl+C). All {len(results)} newly extracted jobs are safely saved in '{output_filename}'.")

    print(f"\nFinished: Extracted {len(results)} of {total} jobs -> saved to '{output_filename}'.")
    return results


if __name__ == '__main__':
    target_urls = load_target_urls(csv_file=INPUT_CSV, raw_input=TARGET_URLS)
    if not target_urls:
        print(f"No URLs to extract. Ensure '{INPUT_CSV}' exists or paste URLs into TARGET_URLS.")
    else:
        parse_multiple_job_urls(target_urls, output_filename=OUTPUT_FILENAME)