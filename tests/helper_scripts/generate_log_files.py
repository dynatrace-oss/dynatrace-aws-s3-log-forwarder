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
  python generate_log_files.py                                             # Generate perf_test_1MB.jsonl
  LOG_SIZE_MB=5 python generate_log_files.py                               # Generate perf_test_5MB.jsonl
  LOG_FORMAT=json_array python generate_log_files.py                       # Generate perf_test_1MB.json
  LOG_FILE_COUNT=10 python generate_log_files.py                           # Generate perf_test_1MB_0001.jsonl to perf_test_1MB_0010.jsonl
  LOG_SIZE_MB=2 LOG_FORMAT=json_array LOG_FILE_COUNT=5 python generate_log_files.py  # Generate perf_test_2MB_0001.json to perf_test_2MB_0005.json
"""

import json
import os
import secrets

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
    record = {"content": "[s3-log-fwd perf test]"}
    target_length = secrets.randbelow(max_length - min_length + 1) + min_length
    attribute_names = ["message", "data", "log_message", "details", "event_data", "context", "metadata", "info", "request", "response"]
    max_attributes = 10

    for _ in range(max_attributes):
        current_size = len(json.dumps(record, separators=(',', ':')).encode('utf-8'))

        if current_size >= target_length:
            break

        remaining_space = target_length - current_size - 50
        if remaining_space <= 10:
            break

        attr_name = "{}_{}".format(secrets.choice(attribute_names), secrets.randbelow(9999) + 1)
        word_count = min(secrets.randbelow(max(5, remaining_space // 20) - 3 + 1) + 3, 50)
        words = [secrets.choice(LOREM_IPSUM_WORDS) for _ in range(word_count)]
        record[attr_name] = " ".join(words)

    return record


def print_progress(current_size: int, target_size_mb: int, record_count: int) -> None:
    """Print progress indicator."""
    progress_mb = current_size / (1024 * 1024)
    print("  Progress: {:.2f} MB / {} MB ({} records)".format(progress_mb, target_size_mb, record_count))


def generate_jsonl_file(output_path: str, target_size_bytes: int, size_mb: int) -> int:
    """
    Generate a JSONL format log file.

    Args:
        output_path: Path where the log file will be created.
        target_size_bytes: Target file size in bytes.
        size_mb: Target size in MB (for progress display).

    Returns:
        Final size in bytes.
    """
    current_size = 0
    record_count = 0
    buffer = []
    buffer_size = 0
    max_buffer_size = 1024 * 1024  # 1MB buffer

    with open(output_path, 'w', encoding='utf-8') as f:
        while current_size < target_size_bytes:
            log_record = generate_random_log_record()
            json_line = json.dumps(log_record) + "\n"

            buffer.append(json_line)
            line_size = len(json_line.encode('utf-8'))
            buffer_size += line_size
            current_size += line_size
            record_count += 1

            should_flush = buffer_size >= max_buffer_size or current_size >= target_size_bytes
            if should_flush:
                f.write(''.join(buffer))
                buffer.clear()
                buffer_size = 0

            if current_size % (1024 * 1024) == 0 or current_size >= target_size_bytes:
                print_progress(current_size, size_mb, record_count)

        if buffer:
            f.write(''.join(buffer))

    return current_size


def generate_json_array_file(output_path: str, target_size_bytes: int, size_mb: int) -> int:
    """
    Generate a JSON array format log file.

    Args:
        output_path: Path where the log file will be created.
        target_size_bytes: Target file size in bytes.
        size_mb: Target size in MB (for progress display).

    Returns:
        Final size in bytes.
    """
    wrapper_overhead = 14  # {"Records":[]} = 14 bytes
    current_size = wrapper_overhead
    record_separator_size = 1  # comma between records
    records = []

    while current_size < target_size_bytes:
        log_record = generate_random_log_record()
        record_json = json.dumps(log_record)
        record_size = len(record_json.encode('utf-8'))

        if records:
            record_size += record_separator_size

        if current_size + record_size > target_size_bytes and records:
            break

        records.append(log_record)
        current_size += record_size

        if current_size % (1024 * 1024) == 0 or current_size >= target_size_bytes:
            print_progress(current_size, size_mb, len(records))

    with open(output_path, 'w', encoding='utf-8') as f:
        wrapper = {"Records": records}
        json.dump(wrapper, f)

    return current_size


def generate_log_file(output_path: str, size_mb: int = 1, format_type: str = 'jsonl') -> None:
    """
    Generate a log file of specified size with JSON records.

    Args:
        output_path: Path where the log file will be created.
        size_mb: Size of the log file in megabytes (default: 1 MB).
        format_type: Output format - 'jsonl' for JSONL (one record per line) or 'json_array' for JSON array format (default: 'jsonl').
    """
    target_size_bytes = size_mb * 1024 * 1024

    print("Generating log file: {}".format(output_path))
    print("Target size: {} MB ({} bytes)".format(size_mb, target_size_bytes))
    print("Format: {}".format(format_type))

    if format_type == 'json_array':
        current_size = generate_json_array_file(output_path, target_size_bytes, size_mb)
    else:
        current_size = generate_jsonl_file(output_path, target_size_bytes, size_mb)

    final_size_mb = current_size / (1024 * 1024)
    print("Log file created successfully!")
    print("Final size: {:.2f} MB ({} bytes)".format(final_size_mb, current_size))


def get_output_folder(format_type: str, size_mb: int) -> str:
    """
    Determine the output folder name based on format and size.

    Args:
        format_type: Output format type.
        size_mb: Size in MB.

    Returns:
        Folder name.
    """
    return "jsonlines_{}MB".format(size_mb) if format_type == "jsonl" else "json_{}MB".format(size_mb)


def get_output_filename(format_type: str, size_mb: int, file_id: int = None) -> str:
    """
    Generate output filename based on format, size, and optional file ID.

    Args:
        format_type: Output format type.
        size_mb: Size in MB.
        file_id: Optional file ID for multiple files.

    Returns:
        Filename.
    """
    extension = "json" if format_type == "json_array" else "jsonl"

    if file_id is None:
        return "perf_test_{}MB.{}".format(size_mb, extension)

    return "perf_test_{}MB_{:04d}.{}".format(size_mb, file_id, extension)


def generate_single_file(size_mb: int, format_type: str) -> None:
    """Generate a single log file."""
    folder_name = get_output_folder(format_type, size_mb)
    base_path = os.path.join(os.path.dirname(__file__), folder_name)

    if "LOG_FILE_PATH" in os.environ:
        output_path = os.environ["LOG_FILE_PATH"]
    else:
        os.makedirs(base_path, exist_ok=True)
        output_filename = get_output_filename(format_type, size_mb)
        output_path = os.path.join(base_path, output_filename)

    generate_log_file(output_path, size_mb, format_type)


def generate_multiple_files(size_mb: int, format_type: str, file_count: int) -> None:
    """Generate multiple log files."""
    folder_name = get_output_folder(format_type, size_mb)
    base_path = os.path.join(os.path.dirname(__file__), folder_name)

    if "LOG_FILE_PATH" in os.environ:
        base_path = os.environ["LOG_FILE_PATH"]
        if os.path.isfile(base_path) or not os.path.isdir(base_path):
            base_path = os.path.dirname(base_path)

    os.makedirs(base_path, exist_ok=True)
    print("Generating {} log files...".format(file_count))

    for file_id in range(1, file_count + 1):
        filename = get_output_filename(format_type, size_mb, file_id)
        output_path = os.path.join(base_path, filename)
        print("\nGenerating file {} of {}:".format(file_id, file_count))
        generate_log_file(output_path, size_mb, format_type)

    print("\nSuccessfully generated {} log files!".format(file_count))


def validate_inputs(size_mb: int, format_type: str, file_count: int) -> None:
    """Validate input parameters."""
    if format_type not in ['jsonl', 'json_array']:
        print("Error: LOG_FORMAT must be 'jsonl' or 'json_array', got '{}'".format(format_type))
        exit(1)

    if size_mb <= 0:
        print("Error: LOG_SIZE_MB must be a positive integer")
        exit(1)

    if file_count <= 0:
        print("Error: LOG_FILE_COUNT must be a positive integer")
        exit(1)


def main() -> None:
    """Main entry point."""
    size_mb = int(os.getenv("LOG_SIZE_MB", "1"))
    format_type = os.getenv("LOG_FORMAT", "jsonl").lower()
    file_count = int(os.getenv("LOG_FILE_COUNT", "1"))

    validate_inputs(size_mb, format_type, file_count)

    if file_count == 1:
        generate_single_file(size_mb, format_type)
    else:
        generate_multiple_files(size_mb, format_type, file_count)


if __name__ == "__main__":
    main()

