# =============================================================================
# LinkedIn Job Finder
# Copyright (C) 2026  Javier Medina Moreno
# Licence: GNU AGPLv3
# Free to use, modify, and redistribute. Retain original author attribution and copyright notice.
# =============================================================================

import csv
import os
import random
import re
import time
from bs4 import BeautifulSoup
import requests

# ==============================================================================
# USER INPUT FIELDS
# ==============================================================================
KEYWORD = '(Economics OR ADE OR Economía OR Business) AND ("Power BI" OR SQL OR Python OR forecasting OR pricing OR "market analysis" OR "financial analysis" OR dashboard OR reporting)'
LOCATION = 'Barcelona, Catalonia, Spain'

# Search Filters (leave empty '' to disable):
TIME_FILTER = 'r604800'            # f_TPR: '' (anytime), 'r86400' (past 24h), 'r604800' (past week), 'r2592000' (past month)
EXPERIENCE_LEVEL = '1,2'              # f_E:   '' (any), '1' (Internship), '2' (Entry level), '3' (Associate), '4' (Mid-Senior), '5' (Director), '6' (Executive). Combos: '1,2,3', '2,3'
WORKPLACE_TYPE = ''                # f_WT:  '' (any), '1' (On-site), '2' (Remote), '3' (Hybrid). Combos: '2,3'
JOB_TYPE = ''                      # f_JT:  '' (any), 'F' (Full-time), 'P' (Part-time), 'C' (Contract), 'I' (Internship). Combos: 'F,C'

# Execution & Output Settings:
AUTO_RUN_EXTRACTOR = True          # True = automatically run Extractor.py once scraping finishes
MAX_PAGES = None                   # None = scrape until exhausted or throttled (up to 1,000 jobs); or set an integer ceiling
OUTPUT_FILENAME = 'linkedin_jobs.csv'  # File name for exported CSV results
DETAILS_OUTPUT_FILENAME = 'linkedin_job_details.txt'  # Destination text file for extracted details
# ==============================================================================


def scrape_linkedin_jobs(
    keyword: str,
    location: str,
    total_pages: int = None,
    time_filter: str = '',
    experience_level: str = '',
    workplace_type: str = '',
    job_type: str = '',
    output_filename: str = 'linkedin_jobs.csv',
    delay_range: tuple = (3.0, 5.5),
    auto_run_extractor: bool = False,
    details_output_filename: str = 'linkedin_job_details.txt',
) -> list:
  """Scrapes public LinkedIn job listings via the guest search endpoint until exhausted or throttled."""
  base_url = (
      'https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search'
  )

  session = requests.Session()
  session.headers.update({
      'User-Agent': (
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,'
          ' like Gecko) Chrome/128.0.0.0 Safari/537.36'
      ),
      'Accept': (
          'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
      ),
      'Accept-Language': 'en-US,en;q=0.9',
  })

  fields = ['job_id', 'title', 'company', 'location', 'date_posted', 'url']
  seen_ids = set()
  scraped_jobs = []

  # Pre-load existing IDs if file exists to resume gracefully without wiping previous work
  file_exists = os.path.exists(output_filename) and os.path.getsize(output_filename) > 0
  if file_exists:
    try:
      with open(output_filename, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
          key = (row.get('job_id') or '').strip() or (row.get('url') or '').strip()
          if key:
            seen_ids.add(key)
      print(f"Resuming search: Found {len(seen_ids)} existing jobs in '{output_filename}'. New unique jobs will be appended.")
    except Exception as err:
      print(f"Notice reading existing '{output_filename}': {err}")
  else:
    with open(output_filename, mode='w', newline='', encoding='utf-8') as f:
      writer = csv.DictWriter(f, fieldnames=fields)
      writer.writeheader()

  page_size = 10  # LinkedIn guest search endpoint returns 10 jobs per request
  hard_page_limit = 100  # LinkedIn hard-caps any search at 1,000 results (100 pages * 10)
  effective_limit = (
      min(total_pages, hard_page_limit) if total_pages else hard_page_limit
  )
  limit_desc = (
      f'up to {effective_limit} pages'
      if total_pages
      else f'opportunistic (up to {hard_page_limit} pages until exhausted/throttled)'
  )
  print(
      f"Starting search: '{keyword}' in '{location}' ({limit_desc})..."
  )
  active_filters = []
  if time_filter:
    active_filters.append(f'time={time_filter}')
  if experience_level:
    active_filters.append(f'experience={experience_level}')
  if workplace_type:
    active_filters.append(f'workplace={workplace_type}')
  if job_type:
    active_filters.append(f'job_type={job_type}')
  if active_filters:
    print(f"Active search filters: {', '.join(active_filters)}")

  consecutive_empty_new = 0
  interrupted = False

  try:
    for page in range(effective_limit):
      offset = page * page_size
      params = {'keywords': keyword, 'location': location, 'start': offset}
      if time_filter:
        params['f_TPR'] = time_filter
      if experience_level:
        params['f_E'] = experience_level
      if workplace_type:
        params['f_WT'] = workplace_type
      if job_type:
        params['f_JT'] = job_type

      page_label = f'{page + 1}/{effective_limit}' if total_pages else f'{page + 1}'
      print(f'\n[Page {page_label}] Fetching offset {offset}...')

      # Request with retry on 429
      response = None
      for attempt in range(2):
        try:
          response = session.get(base_url, params=params, timeout=12)
          if response.status_code == 429:
            if attempt == 0:
              print('Rate limited (HTTP 429). Pausing for 35s before retry...')
              time.sleep(35)
              continue
            else:
              print('Rate limit persists after retry. Stopping scraper early.')
              break
          elif response.status_code != 200:
            print(f'Unexpected status code {response.status_code}. Stopping.')
            break
          else:
            break
        except requests.RequestException as err:
          print(f'Request error: {err}')
          break

      if not response or response.status_code != 200:
        break

      soup = BeautifulSoup(response.text, 'html.parser')
      cards = soup.find_all('li')

      if not cards:
        print(f'No listings returned at offset {offset}. Search complete.')
        break

      new_jobs_this_page = []
      for card in cards:
        title_tag = card.find('h3', class_='base-search-card__title')
        title = title_tag.get_text(strip=True) if title_tag else None

        company_tag = card.find('h4', class_='base-search-card__subtitle')
        company = company_tag.get_text(strip=True) if company_tag else None

        loc_tag = card.find('span', class_='job-search-card__location')
        job_loc = loc_tag.get_text(strip=True) if loc_tag else None

        date_tag = card.find('time')
        post_date = (
            date_tag['datetime']
            if date_tag and date_tag.has_attr('datetime')
            else None
        )

        link_tag = card.find('a', class_='base-card__full-link') or card.find('a')
        job_url = None
        job_id = None
        if link_tag and link_tag.has_attr('href'):
          job_url = link_tag['href'].split('?')[0].strip()
          clean_path = job_url.split('?')[0].split('#')[0].rstrip('/')
          match = re.search(
              r'/jobs/view/(?:.*[-/])?(\d+)$', clean_path
          ) or re.search(r'(\d{8,})', clean_path)
          if match:
            job_id = match.group(1)

        dedup_key = job_id or job_url
        if title and company and dedup_key and dedup_key not in seen_ids:
          seen_ids.add(dedup_key)
          job_entry = {
              'job_id': job_id or '',
              'title': title,
              'company': company,
              'location': job_loc or '',
              'date_posted': post_date or '',
              'url': job_url or '',
          }
          # Write and flush each unique job to disk immediately as it is extracted
          with open(output_filename, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writerow(job_entry)
            f.flush()

          new_jobs_this_page.append(job_entry)
          scraped_jobs.append(job_entry)

      if new_jobs_this_page:
        consecutive_empty_new = 0
        print(
            f'Saved {len(new_jobs_this_page)} new jobs (Total unique so far:'
            f' {len(scraped_jobs)}) -> {output_filename}'
        )
      else:
        consecutive_empty_new += 1
        print('No new unique jobs on this page.')
        if consecutive_empty_new >= 2:
          print('Consecutive pages yielded no new unique listings. Search exhausted.')
          break

      # Delay before next page request
      if page + 1 < effective_limit:
        wait_time = random.uniform(*delay_range)
        time.sleep(wait_time)
  except KeyboardInterrupt:
    interrupted = True
    print(f"\nScraping stopped by user (Ctrl+C). All {len(scraped_jobs)} newly extracted jobs are safely saved in '{output_filename}'.")

  print(
      f"\nScraping complete. Total unique jobs saved: {len(scraped_jobs)} in"
      f" '{output_filename}'"
  )

  if auto_run_extractor and not interrupted:
    print('\n' + '=' * 80)
    print('Scraper finished. Automatically launching Extractor...')
    print('=' * 80 + '\n')
    try:
      import Extractor

      target_urls = Extractor.load_target_urls(csv_file=output_filename)
      if target_urls:
        Extractor.parse_multiple_job_urls(
            target_urls, output_filename=details_output_filename
        )
      else:
        print(f"No URLs found in '{output_filename}' to extract.")
    except Exception as err:
      print(f'Error launching Extractor: {err}')

  return scraped_jobs


def export_to_csv(jobs: list, filename: str = 'linkedin_jobs.csv'):
  if not jobs:
    print('No jobs to export.')
    return

  fields = ['title', 'company', 'location', 'date_posted', 'url']
  with open(filename, mode='w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(jobs)

  print(f'Successfully exported {len(jobs)} jobs to {filename}')


if __name__ == '__main__':
  scrape_linkedin_jobs(
      keyword=KEYWORD,
      location=LOCATION,
      total_pages=MAX_PAGES,
      time_filter=TIME_FILTER,
      experience_level=EXPERIENCE_LEVEL,
      workplace_type=WORKPLACE_TYPE,
      job_type=JOB_TYPE,
      output_filename=OUTPUT_FILENAME,
      auto_run_extractor=AUTO_RUN_EXTRACTOR,
      details_output_filename=DETAILS_OUTPUT_FILENAME,
  )