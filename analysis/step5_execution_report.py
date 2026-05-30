import csv
from pathlib import Path
import logging
import re

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

FILE_MAP = {
    "3-hour chunks": "compressed_3h.csv",
    "1-day chunks": "compressed_1day.csv",
    "1-week chunks": "compressed_1week.csv",
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def read_benchmark_file(filepath: Path) -> dict:
    """
    Returns dict mapping query_number (int) -> execution_time_ms (float)
    """
    results = {}
    with open(filepath, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            full_name = row["query_name"]
            # Extract number from "Query X: ..."
            match = re.search(r"Query\s+(\d+)", full_name)
            if match:
                q_num = int(match.group(1))
                results[q_num] = float(row["execution_time_ms"])
    return results


def main():
    all_data = {}  # {label: {query_number: time_ms}}

    for label, filename in FILE_MAP.items():
        filepath = DATA_DIR / filename
        if not filepath.exists():
            logging.error(f"Missing file: {filepath}")
            continue
        logging.info(f"Reading {filepath} ...")
        all_data[label] = read_benchmark_file(filepath)

    if not all_data:
        logging.error("No benchmark data found. Aborting.")
        return

    # Collect all query numbers (should be 1..4)
    query_numbers = set()
    for data in all_data.values():
        query_numbers.update(data.keys())
    query_numbers = sorted(query_numbers)  # [1,2,3,4]

    # Prepare output CSV (comma delimiter)
    output_file = DATA_DIR / "compressed_report.csv"
    logging.info(f"Writing report to {output_file}")

    with open(output_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)  # default delimiter is comma
        # Header
        writer.writerow(["Query"] + list(all_data.keys()))

        # Data rows
        for qnum in query_numbers:
            row = [qnum]
            for label in all_data.keys():
                time_ms = all_data[label].get(qnum, "")
                row.append(f"{time_ms:.2f}" if time_ms else "")
            writer.writerow(row)

    logging.info(f"Report successfully created: {output_file}")


if __name__ == "__main__":
    main()
