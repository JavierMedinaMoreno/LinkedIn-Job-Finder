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
# ==============================================================================
BATCH_SIZE = 50                    # Number of jobs per batch file

# ==============================================================================
INPUT_FILENAME = 'linkedin_job_details.txt'    # Source file containing all extracted job details
OUTPUT_DIR = ''                               # Destination directory ('' for current directory, or e.g. 'batches')
FILENAME_PREFIX = 'linkedin_job_details_batch' # Prefix for batch files (e.g. linkedin_job_details_batch_1_jobs_1-50.txt)
# ==============================================================================


def parse_job_blocks(source_filename: str) -> list:
    """Parses a job details text file into an ordered list of raw job blocks."""
    if not os.path.exists(source_filename):
        print(f"Error: Source file '{source_filename}' not found.")
        return []

    with open(source_filename, mode='r', encoding='utf-8') as f:
        content = f.read()

    # Matches each block starting with '={80}\nJOB #<n>: ' through its trailing divider
    pattern = re.compile(
        r'(={80}\r?\nJOB #\d+: [^\n]+\r?\n={80}\r?\nJob ID:\s*\d+\r?\n.+?)(?=\n={80}\r?\nJOB #|\Z)',
        re.DOTALL,
    )

    blocks = [match.group(1).strip() for match in pattern.finditer(content)]
    return blocks


def split_job_details(
    input_filename: str = 'linkedin_job_details.txt',
    batch_size: int = 50,
    output_dir: str = '',
    filename_prefix: str = 'linkedin_job_details_batch',
) -> list:
    """Splits input_filename into separate batch text files of batch_size jobs each."""
    if batch_size <= 0:
        print('Error: BATCH_SIZE must be greater than 0.')
        return []

    print(f"Reading jobs from '{input_filename}'...")
    blocks = parse_job_blocks(input_filename)
    total_jobs = len(blocks)

    if total_jobs == 0:
        print(f"No job blocks found in '{input_filename}'.")
        return []

    print(f'Found {total_jobs} total jobs. Splitting into batches of {batch_size}...')

    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    generated_files = []
    total_batches = (total_jobs + batch_size - 1) // batch_size

    for batch_num in range(1, total_batches + 1):
        start_idx = (batch_num - 1) * batch_size + 1
        end_idx = min(batch_num * batch_size, total_jobs)
        batch_blocks = blocks[start_idx - 1 : end_idx]

        file_name = f'{filename_prefix}_{batch_num}_jobs_{start_idx}-{end_idx}.txt'
        file_path = os.path.join(output_dir, file_name) if output_dir else file_name

        with open(file_path, mode='w', encoding='utf-8') as f:
            for blk in batch_blocks:
                f.write(blk + '\n\n')

            f.flush()

        generated_files.append(file_path)
        print(f"  [Batch {batch_num}/{total_batches}] Created '{file_path}' ({len(batch_blocks)} jobs)")

    print(f'\nSuccessfully generated {len(generated_files)} batch file(s) from {total_jobs} total jobs.')
    return generated_files


if __name__ == '__main__':
    split_job_details(
        input_filename=INPUT_FILENAME,
        batch_size=BATCH_SIZE,
        output_dir=OUTPUT_DIR,
        filename_prefix=FILENAME_PREFIX,
    )
