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
4472054618
4469421267
4470164371
4471885496
4468198561
4472299370
4470446094
4467391346
4463397226
4470145054
4470689662
"""

# Paste Job IDs to exclude/remove below (takes precedence over INTERESTING_JOB_IDS).
EXCLUDED_JOB_IDS = """
4427557481
4448446368
4467714034
4468769329
4442617102
4467891631
4468909447
4434115036
4461952450
4470974324
4469474859
4468910382
4459266505
4460998798
4468152040
4468980307
4432637181
4461996996
4469924295
4467628263
4462898076
4453094820
4471143668
4470501438
4470464816
4450813447
4472006005
4461689758
4462235198
4434774578
4463376843
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


def parse_job_blocks_ordered(filename: str) -> list:
    """Parses a job details text file into an ordered list of (job_id, raw_job_block) tuples."""
    if not os.path.exists(filename):
        return []

    with open(filename, mode='r', encoding='utf-8') as f:
        content = f.read()

    pattern = re.compile(
        r'(={80}\r?\nJOB #\d+: [^\n]+\r?\n={80}\r?\nJob ID:\s*(\d+)\r?\n.+?)(?=\n={80}\r?\nJOB #|\Z)',
        re.DOTALL,
    )

    blocks = []
    for match in pattern.finditer(content):
        job_block = match.group(1).strip()
        job_id = match.group(2)
        blocks.append((job_id, job_block))

    return blocks


def prune_excluded_jobs(output_filename: str, excluded_ids: set) -> tuple:
    """Removes excluded job IDs from the output file, renumbers remaining jobs, and rewrites the file.
    Returns (current_count, existing_ids).
    """
    if not os.path.exists(output_filename) or not excluded_ids:
        existing_ids, current_count = get_existing_saved_job_ids(output_filename)
        return current_count, existing_ids

    existing_blocks = parse_job_blocks_ordered(output_filename)
    if not existing_blocks:
        return 0, set()

    retained_blocks = []
    deleted_ids = []

    for jid, blk in existing_blocks:
        if jid in excluded_ids:
            deleted_ids.append(jid)
        else:
            retained_blocks.append((jid, blk))

    if deleted_ids:
        renumbered_blocks = []
        for idx, (jid, blk) in enumerate(retained_blocks, start=1):
            new_blk = re.sub(r'JOB #\d+:', f'JOB #{idx}:', blk, count=1)
            renumbered_blocks.append(new_blk)

        with open(output_filename, mode='w', encoding='utf-8') as f:
            if renumbered_blocks:
                f.write('\n\n'.join(renumbered_blocks) + '\n\n')
            f.flush()

        print(f"[-] Removed {len(deleted_ids)} excluded job(s) from '{output_filename}': {', '.join(deleted_ids)}")

    current_count = len(retained_blocks)
    existing_ids = {jid for jid, _ in retained_blocks}
    return current_count, existing_ids


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


def prune_conflicts_from_source(source_py_path: str, conflict_ids: set) -> list:
    """Removes conflicting job IDs from the INTERESTING_JOB_IDS block in the source script itself."""
    if not source_py_path or not os.path.exists(source_py_path) or not conflict_ids:
        return []

    try:
        with open(source_py_path, mode='r', encoding='utf-8') as f:
            code = f.read()

        # Match INTERESTING_JOB_IDS = """...""" or '''...'''
        pattern = re.compile(
            r'(INTERESTING_JOB_IDS\s*=\s*(?:"""|\'\'\'))([\s\S]*?)((?:"""|\'\'\'))',
            re.MULTILINE,
        )
        match = pattern.search(code)
        if not match:
            return []

        prefix, body, suffix = match.group(1), match.group(2), match.group(3)

        removed = []
        new_body_lines = []
        for line in body.splitlines(keepends=True):
            line_ids = re.findall(r'\b\d{8,}\b', line)
            if line_ids and any(jid in conflict_ids for jid in line_ids):
                for jid in line_ids:
                    if jid in conflict_ids and jid not in removed:
                        removed.append(jid)
            else:
                new_body_lines.append(line)

        if not removed:
            return []

        new_block = prefix + ''.join(new_body_lines) + suffix
        new_code = code[: match.start()] + new_block + code[match.end() :]

        with open(source_py_path, mode='w', encoding='utf-8') as f:
            f.write(new_code)
            f.flush()

        return removed
    except Exception as e:
        print(f"[Auto-Clean Warning] Could not update source script: {e}")
        return []


def filter_interesting_jobs(
    interesting_ids_input,
    excluded_ids_input=None,
    input_filename: str = 'linkedin_job_details.txt',
    output_filename: str = 'interesting_jobs.txt',
):
    """Extracts interesting jobs from input_filename, excludes/removes specified IDs, and updates output_filename."""
    raw_target_ids = extract_target_ids(interesting_ids_input)
    excluded_ids = set(extract_target_ids(excluded_ids_input)) if excluded_ids_input else set()

    # Check collision between interesting and excluded
    if raw_target_ids and excluded_ids:
        conflicts = [jid for jid in raw_target_ids if jid in excluded_ids]
        if conflicts:
            print(f"\n[WARNING] The following Job ID(s) appear in both INTERESTING_JOB_IDS and EXCLUDED_JOB_IDS and will be excluded: {', '.join(conflicts)}")
            # Automatically prune conflicting IDs from INTERESTING_JOB_IDS in Filter.py source code
            source_script = os.path.abspath(__file__)
            removed_from_src = prune_conflicts_from_source(source_script, set(conflicts))
            if removed_from_src:
                print(f"[Auto-Clean] Pruned {len(removed_from_src)} conflicting Job ID(s) from INTERESTING_JOB_IDS in '{os.path.basename(source_script)}': {', '.join(removed_from_src)}\n")
            else:
                print()

    # Filter out excluded IDs from target IDs
    target_ids = [jid for jid in raw_target_ids if jid not in excluded_ids]

    if not raw_target_ids and not excluded_ids:
        print('No valid Job IDs provided in INTERESTING_JOB_IDS or EXCLUDED_JOB_IDS.')
        return

    # Prune any excluded jobs that might already be in output_filename
    current_count, existing_ids = prune_excluded_jobs(output_filename, excluded_ids)

    if not target_ids:
        if not raw_target_ids and excluded_ids:
            print(f"Pruned excluded jobs. Output file '{output_filename}' now contains {current_count} jobs.")
        else:
            print('No remaining target Job IDs to add after exclusions.')
        return

    print(f"Checking {len(target_ids)} target Job IDs against '{input_filename}'...")
    source_jobs = parse_source_job_blocks(input_filename)
    if not source_jobs:
        print(f"No job blocks found in '{input_filename}'.")
        return

    if existing_ids:
        print(f"Destination '{output_filename}' currently contains {len(existing_ids)} jobs.")

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
    print(f'Total target IDs requested:  {len(raw_target_ids)}')
    if excluded_ids:
        print(f'Excluded IDs specified:      {len(excluded_ids)}')
    print(f'Newly appended to output:    {newly_appended}')
    if already_saved:
        print(f'Already in destination file: {already_saved}')
    if not_found:
        print(f"Not found in '{input_filename}': {len(not_found)} -> {', '.join(not_found)}")
    print(f"Output file: '{output_filename}' (Total jobs now: {current_count})\n")


if __name__ == '__main__':
    filter_interesting_jobs(
        interesting_ids_input=INTERESTING_JOB_IDS,
        excluded_ids_input=EXCLUDED_JOB_IDS,
        input_filename=INPUT_FILENAME,
        output_filename=OUTPUT_FILENAME,
    )
