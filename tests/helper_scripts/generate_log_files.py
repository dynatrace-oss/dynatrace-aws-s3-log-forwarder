#!/usr/bin/env python3
"""
Generate log files of specified size for performance testing.

Environment Variables:
  - LOG_SIZE_MB: Size of each log file in megabytes (default: 1 MB)
  - LOG_FORMAT: Output format - 'jsonl' for JSONL (one record per line) or 'json_array' for JSON array format (default: 'jsonl')
  - LOG_FILE_COUNT: Number of files to generate (default: 1)
  - LOG_FILE_PATH: Override output path/directory (optional)

Generated files are saved in format-specific folders with size:
  - JSONL files → jsonlines_<SIZE>MB/
  - JSON array files → json_<SIZE>MB/

Each log record contains:
  - "content" field with text "[s3-log-fwd perf test]"
  - Up to 10 additional random attributes with lorem ipsum text
  - Record size varies randomly from 40 bytes to 2 KB

Examples:
  python generate_log_files.py                                              # Generate perf_test_1MB.jsonl
  LOG_SIZE_MB=5 python generate_log_files.py                               # Generate perf_test_5MB.jsonl
  LOG_FORMAT=json_array python generate_log_files.py                       # Generate perf_test_1MB.json
  LOG_FILE_COUNT=10 python generate_log_files.py                           # Generate perf_test_1MB_0001.jsonl to perf_test_1MB_0010.jsonl
  LOG_SIZE_MB=2 LOG_FORMAT=json_array LOG_FILE_COUNT=5 python generate_log_files.py  # Generate perf_test_2MB_0001.json to perf_test_2MB_0005.json
"""

import json
import os
import random
import string
from typing import List

# Lorem ipsum words for generating random content
LOREM_IPSUM_WORDS = [
    "lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing",
    "elit", "sed", "do", "eiusmod", "tempor", "incididunt", "ut", "labore",
    "et", "dolore", "magna", "aliqua", "enim", "ad", "minim", "veniam",
    "quis", "nostrud", "exercitation", "ullamco", "laboris", "nisi",
    "aliquip", "ex", "ea", "commodo", "consequat", "duis", "aute", "irure",
    "in", "reprehenderit", "voluptate", "velit", "esse", "cillum",
    "fugiat", "nulla", "pariatur", "excepteur", "sint", "occaecat",
    "cupidatat", "non", "proident", "sunt", "culpa", "qui", "officia",
    "deserunt", "mollit", "anim", "id", "est", "laborum", "test",
    "performance", "testing", "log", "message", "data", "processing",
]


def generate_random_log_record(min_length: int = 40, max_length: int = 2048) -> dict:
    """
    Generate a single log record with random attributes and content.

    Args:
        min_length: Minimum record length in bytes (default: 40)
        max_length: Maximum record length in bytes (default: 2048 = 2KB)

    Returns:
        A dictionary with "content" field set to "[s3-log-fwd perf test]" and up to 10 additional random attributes.
    """
    # Start with the content field
    record = {"content": "[s3-log-fwd perf test]"}

    # Target size for the JSON record
    target_length = random.randint(min_length, max_length)

    # Build additional attributes to fill the target size
    attribute_names = ["message", "data", "log_message", "details", "event_data", "context", "metadata", "info", "request", "response"]

    # Maximum number of additional attributes
    max_attributes = 10
    attribute_count = 0

    # Keep adding random attributes until we reach the target size or max attributes
    while attribute_count < max_attributes:
        # Estimate current size more efficiently
        current_size = len(json.dumps(record, separators=(',', ':')).encode('utf-8'))

        if current_size >= target_length:
            break

        # Calculate remaining space
        remaining_space = target_length - current_size - 50  # Leave buffer for JSON overhead

        if remaining_space <= 10:
            break

        # Generate a unique random attribute name
        attr_name = random.choice(attribute_names) + "_" + str(random.randint(1, 9999))

        # Generate random words to fill a portion of the remaining space
        # More efficient: pre-calculate word count
        word_count = min(random.randint(3, max(5, remaining_space // 20)), 50)

        # Use random.choices for better performance when selecting multiple items
        words = random.choices(LOREM_IPSUM_WORDS, k=word_count)

        # Add the attribute to the record
        record[attr_name] = " ".join(words)
        attribute_count += 1

    return record


def generate_log_file(output_path: str, size_mb: int = 1, format_type: str = 'jsonl') -> None:
    """
    Generate a log file of specified size with JSON records.

    Args:
        output_path: Path where the log file will be created.
        size_mb: Size of the log file in megabytes (default: 1 MB).
        format_type: Output format - 'jsonl' for JSONL (one record per line) or 'json_array' for JSON array format (default: 'jsonl').
    """
    target_size_bytes = size_mb * 1024 * 1024
    current_size = 0
    records = []

    print(f"Generating log file: {output_path}")
    print(f"Target size: {size_mb} MB ({target_size_bytes} bytes)")
    print(f"Format: {format_type}")

    if format_type == 'json_array':
        # Collect records for JSON array format
        # Start with wrapper overhead: {"Records":[]} = 14 bytes
        wrapper_overhead = 14
        current_size = wrapper_overhead
        record_separator_size = 1  # comma between records

        while current_size < target_size_bytes:
            log_record = generate_random_log_record()

            # Calculate size of this record
            record_json = json.dumps(log_record)
            record_size = len(record_json.encode('utf-8'))

            # Add separator size if not the first record
            if records:
                record_size += record_separator_size

            # Check if adding this record would exceed target
            if current_size + record_size > target_size_bytes and len(records) > 0:
                break

            records.append(log_record)
            current_size += record_size

            # Progress indicator every 1MB
            if current_size % (1024 * 1024) == 0 or current_size >= target_size_bytes:
                progress_mb = current_size / (1024 * 1024)
                print(f"  Progress: {progress_mb:.2f} MB / {size_mb} MB ({len(records)} records)")

        # Write as JSON object with Records array
        with open(output_path, 'w', encoding='utf-8') as f:
            wrapper = {"Records": records}
            json.dump(wrapper, f)

    else:  # Default to JSONL format
        record_count = 0
        buffer = []
        buffer_size = 0
        max_buffer_size = 1024 * 1024  # 1MB buffer

        with open(output_path, 'w', encoding='utf-8') as f:
            while current_size < target_size_bytes:
                log_record = generate_random_log_record()
                # Convert record to JSON
                json_line = json.dumps(log_record)
                json_line_with_newline = json_line + "\n"

                # Add to buffer
                buffer.append(json_line_with_newline)
                line_size = len(json_line_with_newline.encode('utf-8'))
                buffer_size += line_size
                current_size += line_size
                record_count += 1

                # Flush buffer when it reaches threshold or we're done
                if buffer_size >= max_buffer_size or current_size >= target_size_bytes:
                    f.write(''.join(buffer))
                    buffer.clear()
                    buffer_size = 0

                # Progress indicator every 1MB
                if current_size % (1024 * 1024) == 0 or current_size >= target_size_bytes:
                    progress_mb = current_size / (1024 * 1024)
                    print(f"  Progress: {progress_mb:.2f} MB / {size_mb} MB ({record_count} records)")

            # Flush any remaining buffered content
            if buffer:
                f.write(''.join(buffer))

    final_size_mb = current_size / (1024 * 1024)
    print(f"Log file created successfully!")
    print(f"Final size: {final_size_mb:.2f} MB ({current_size} bytes)")


def main() -> None:
    """Main entry point."""
    # Get size from environment variable, default to 1 MB
    size_mb = int(os.getenv("LOG_SIZE_MB", "1"))

    # Get format from environment variable, default to 'jsonl'
    # Valid values: 'jsonl' (one JSON object per line) or 'json_array' (all records in array)
    format_type = os.getenv("LOG_FORMAT", "jsonl").lower()

    # Get number of files to generate, default to 1
    file_count = int(os.getenv("LOG_FILE_COUNT", "1"))

    # Validate format
    if format_type not in ['jsonl', 'json_array']:
        print(f"Error: LOG_FORMAT must be 'jsonl' or 'json_array', got '{format_type}'")
        exit(1)

    # Validate size
    if size_mb <= 0:
        print("Error: LOG_SIZE_MB must be a positive integer")
        exit(1)

    # Validate file count
    if file_count <= 0:
        print("Error: LOG_FILE_COUNT must be a positive integer")
        exit(1)

    # Generate single file or multiple files
    if file_count == 1:
        # Determine folder name based on format and size
        folder_name = f"jsonlines_{size_mb}MB" if format_type == "jsonl" else f"json_{size_mb}MB"
        base_path = os.path.join(os.path.dirname(__file__), folder_name)

        # Allow override via environment variable
        if "LOG_FILE_PATH" in os.environ:
            output_path = os.environ["LOG_FILE_PATH"]
        else:
            # Create folder if it doesn't exist
            os.makedirs(base_path, exist_ok=True)

            # Create filename with size included
            if format_type == 'json_array':
                output_filename = f"perf_test_{size_mb}MB.json"
            else:
                output_filename = f"perf_test_{size_mb}MB.jsonl"

            output_path = os.path.join(base_path, output_filename)

        # Generate the log file
        generate_log_file(output_path, size_mb, format_type)
    else:
        # Generate multiple files with file IDs in filenames
        folder_name = f"jsonlines_{size_mb}MB" if format_type == "jsonl" else f"json_{size_mb}MB"
        base_path = os.path.join(os.path.dirname(__file__), folder_name)

        # Allow override via environment variable for base directory
        if "LOG_FILE_PATH" in os.environ:
            base_path = os.environ["LOG_FILE_PATH"]
            # If LOG_FILE_PATH is a file path, use its directory
            if os.path.isfile(base_path) or not os.path.isdir(base_path):
                base_path = os.path.dirname(base_path)

        # Create folder if it doesn't exist
        os.makedirs(base_path, exist_ok=True)

        print(f"Generating {file_count} log files...")

        for file_id in range(1, file_count + 1):
            # Insert file ID and size before extension
            if format_type == 'json_array':
                filename = f"perf_test_{size_mb}MB_{file_id:04d}.json"
            else:
                filename = f"perf_test_{size_mb}MB_{file_id:04d}.jsonl"

            output_path = os.path.join(base_path, filename)
            print(f"\nGenerating file {file_id} of {file_count}:")
            generate_log_file(output_path, size_mb, format_type)

        print(f"\nSuccessfully generated {file_count} log files!")


if __name__ == "__main__":
    main()

