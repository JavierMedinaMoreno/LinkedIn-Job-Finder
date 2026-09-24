# =============================================================================
# LinkedIn Job Finder
# Copyright (C) 2026  Javier Medina Moreno
# Licence: GNU AGPLv3
# Free to use, modify, and redistribute. Retain original author attribution and copyright notice.
# =============================================================================

import os
import re

# ==============================================================================
# USER INPUT FIELDS
# Paste interesting Job IDs below (as a multiline string or Python list).
# IDs can be separated by newlines, spaces, or commas.
# ==============================================================================
INTERESTING_JOB_IDS = """
"""

# ==============================================================================
INPUT_FILENAME = 'linkedin_job_details.txt'    # Source file containing all extracted job details
OUTPUT_FILENAME = 'interesting_jobs.txt'      # Destination file to expand with selected jobs
# ==============================================================================


def extract_target_ids(ids_input) -> list:
    """Extracts clean numeric Job IDs from a multiline string or iterable of IDs."""
    if isinstance(ids_input, str):
        return list(dict.fromkeys(re.findall(r'\b\d{8,}\b', ids_input)))
    elif isinstance(ids_input, (list, tuple, set)):
        extracted = []
        for item in ids_input:
            matches = re.findall(r'\b\d{8,}\b', str(item))
            for m in matches:
                if m not in extracted:
                    extracted.append(m)
        return extracted
    return []


def parse_source_job_blocks(source_filename: str) -> dict:
    """Parses a job details text file into a dictionary of {job_id: raw_job_block}."""
    if not os.path.exists(source_filename):
        print(f"Error: Source file '{source_filename}' not found.")
        return {}

    with open(source_filename, mode='r', encoding='utf-8') as f:
        content = f.read()

    # Each job block begins with '={80}\nJOB #<n>: ' and contains 'Job ID: <id>'
    pattern = re.compile(
        r'(={80}\r?\nJOB #\d+: [^\n]+\r?\n={80}\r?\nJob ID:\s*(\d+)\r?\n.+?)(?=\n={80}\r?\nJOB #|\Z)',
        re.DOTALL,
    )

    jobs_by_id = {}
    for match in pattern.finditer(content):
        job_block = match.group(1).strip()
        job_id = match.group(2)
        jobs_by_id[job_id] = job_block

    return jobs_by_id


def get_existing_saved_job_ids(destination_filename: str) -> tuple:
    """Reads already saved job IDs and total job count from the destination file."""
    saved_ids = set()
    total_count = 0

    if not os.path.exists(destination_filename):
        return saved_ids, 0

    with open(destination_filename, mode='r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('Job ID:'):
                jid = line.split('Job ID:')[1].strip()
                if jid:
                    saved_ids.add(jid)
            elif re.match(r'^JOB #\d+:', line):
                total_count += 1

    return saved_ids, total_count


def filter_interesting_jobs(
    interesting_ids_input,
    input_filename: str = 'linkedin_job_details.txt',
    output_filename: str = 'interesting_jobs.txt',
):
    """Extracts interesting jobs from input_filename and appends them to output_filename."""
    target_ids = extract_target_ids(interesting_ids_input)
    if not target_ids:
        print('No valid Job IDs provided in INTERESTING_JOB_IDS.')
        return

    print(f"Checking {len(target_ids)} target Job IDs against '{input_filename}'...")
    source_jobs = parse_source_job_blocks(input_filename)
    if not source_jobs:
        print(f"No job blocks found in '{input_filename}'.")
        return

    existing_ids, current_count = get_existing_saved_job_ids(output_filename)
    if existing_ids:
        print(f"Destination '{output_filename}' already contains {len(existing_ids)} jobs.")

    newly_appended = 0
    already_saved = 0
    not_found = []

    with open(output_filename, mode='a', encoding='utf-8') as out_f:
        for jid in target_ids:
            if jid in existing_ids:
                already_saved += 1
                continue

            if jid not in source_jobs:
                not_found.append(jid)
                continue

            current_count += 1
            raw_block = source_jobs[jid]

            # Renumber the job header to maintain sequential ordering
            renumbered_block = re.sub(
                r'JOB #\d+:', f'JOB #{current_count}:', raw_block, count=1
            )

            out_f.write(renumbered_block + '\n\n')
            out_f.flush()

            existing_ids.add(jid)
            newly_appended += 1
            print(f"  [+] Appended JOB #{current_count} (Job ID: {jid})")

    print('\n--- Summary ---')
    print(f'Total target IDs requested:  {len(target_ids)}')
    print(f'Newly appended to output:    {newly_appended}')
    if already_saved:
        print(f'Already in destination file: {already_saved}')
    if not_found:
        print(f"Not found in '{input_filename}': {len(not_found)} -> {', '.join(not_found)}")
    print(f"Output file: '{output_filename}' (Total jobs now: {current_count})\n")


if __name__ == '__main__':
    filter_interesting_jobs(
        interesting_ids_input=INTERESTING_JOB_IDS,
        input_filename=INPUT_FILENAME,
        output_filename=OUTPUT_FILENAME,
    )
