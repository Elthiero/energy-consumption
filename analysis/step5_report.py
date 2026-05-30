import csv
from pathlib import Path
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Mapping: logical name -> (before_time_csv, after_time_csv, hypertable_name)
TABLES = {
    "3-hour chunks": ("readings_3h.csv", "compressed_3h.csv", "energy_readings_3h"),
    "1-day chunks": ("readings_1day.csv", "compressed_1day.csv", "energy_readings"),
    "1-week chunks": (
        "readings_1week.csv",
        "compressed_1week.csv",
        "energy_readings_week",
    ),
}


def parse_human_size(size_str):
    """Convert '1224 MB' or '410 MB' to bytes (1 MB = 1024*1024 bytes)."""
    size_str = size_str.strip().upper()
    if " MB" in size_str:
        val = float(size_str.replace(" MB", ""))
        return int(val * 1024 * 1024)
    elif " GB" in size_str:
        val = float(size_str.replace(" GB", ""))
        return int(val * 1024 * 1024 * 1024)
    else:
        return int(size_str)


def read_times(csv_path):
    """Return dict {query_name: execution_time_ms}"""
    times = {}
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            times[row["query_name"]] = float(row["execution_time_ms"])
    return times


def read_sizes_from_csv(filepath, name_col="hypertable_name", size_col="total_size"):
    """Return dict {hypertable_name: size_in_bytes}."""
    sizes = {}
    if not filepath.exists():
        logging.error(f"Size file not found: {filepath}")
        return sizes
    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row[name_col]
            raw = row[size_col]
            sizes[name] = parse_human_size(raw)
    return sizes


def main():
    # 1. Read uncompressed query times
    before_times = {}
    after_times = {}
    for label, (before_file, after_file, _) in TABLES.items():
        before_path = DATA_DIR / before_file
        after_path = DATA_DIR / after_file
        if not before_path.exists() or not after_path.exists():
            logging.error(f"Missing files for {label}: {before_file} or {after_file}")
            continue
        before_times[label] = read_times(before_path)
        after_times[label] = read_times(after_path)

    # 2. Read sizes
    uncompressed_sizes = read_sizes_from_csv(DATA_DIR / "hypertable_sizes.csv")
    compressed_sizes = read_sizes_from_csv(DATA_DIR / "hypertable_sizes2.csv")

    # 3. Build detailed report rows
    detail_rows = []

    # Performance changes
    for label in before_times:
        bt = before_times[label]
        at = after_times[label]
        for qname, before_ms in bt.items():
            if qname not in at:
                logging.warning(f"Query {qname} missing in after data for {label}")
                continue
            after_ms = at[qname]
            pct_change = ((after_ms - before_ms) / before_ms) * 100
            detail_rows.append(
                {
                    "section": "performance",
                    "hypertable": label,
                    "query": qname,
                    "before_ms": before_ms,
                    "after_ms": after_ms,
                    "pct_change": round(pct_change, 2),
                    "uncompressed_bytes": "",
                    "compressed_bytes": "",
                    "compression_ratio": "",
                }
            )

    # Compression ratios
    for label, (_, _, ht_name) in TABLES.items():
        before_bytes = uncompressed_sizes.get(ht_name)
        after_bytes = compressed_sizes.get(ht_name)
        if before_bytes and after_bytes and after_bytes > 0:
            ratio = before_bytes / after_bytes
            detail_rows.append(
                {
                    "section": "compression_ratio",
                    "hypertable": label,
                    "query": "",
                    "before_ms": "",
                    "after_ms": "",
                    "pct_change": "",
                    "uncompressed_bytes": before_bytes,
                    "compressed_bytes": after_bytes,
                    "compression_ratio": round(ratio, 2),
                }
            )
        else:
            logging.warning(
                f"Missing size data for {ht_name}: before={before_bytes}, after={after_bytes}"
            )

    # Write detailed report
    output_detail = DATA_DIR / "compression_size_impact_report.csv"
    fieldnames = [
        "section",
        "hypertable",
        "query",
        "before_ms",
        "after_ms",
        "pct_change",
        "uncompressed_bytes",
        "compressed_bytes",
        "compression_ratio",
    ]
    with open(output_detail, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in detail_rows:
            writer.writerow(row)
    logging.info(f"Detailed report saved to {output_detail}")

    # 4. Generate storage_efficiency.csv
    storage_rows = []
    for label, (_, _, ht_name) in TABLES.items():
        before_bytes = uncompressed_sizes.get(ht_name)
        after_bytes = compressed_sizes.get(ht_name)
        if before_bytes and after_bytes:
            ratio = before_bytes / after_bytes
            space_saved = (1 - 1 / ratio) * 100
            storage_rows.append(
                {
                    "hypertable": label,
                    "uncompressed_mb": round(before_bytes / (1024 * 1024), 0),
                    "compressed_mb": round(after_bytes / (1024 * 1024), 0),
                    "compression_ratio": round(ratio, 2),
                    "space_saved_pct": round(space_saved, 1),
                }
            )
    storage_out = DATA_DIR / "storage_efficiency.csv"
    with open(storage_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "hypertable",
                "uncompressed_mb",
                "compressed_mb",
                "compression_ratio",
                "space_saved_pct",
            ],
        )
        writer.writeheader()
        for row in storage_rows:
            writer.writerow(row)
    logging.info(f"Storage summary saved to {storage_out}")

    # 5. Generate query_performance.csv
    # First, collect pct_change per query per hypertable
    perf_map = {}  # {query_short: {label: pct}}
    for label in before_times:
        bt = before_times[label]
        at = after_times[label]
        for qname, before_ms in bt.items():
            if qname not in at:
                continue
            after_ms = at[qname]
            pct = ((after_ms - before_ms) / before_ms) * 100
            # Extract short query name (e.g., "Query 1: ..." -> "Q1")
            q_short = qname.split()[1].rstrip(":")
            q_short = f"Q{q_short}"
            if q_short not in perf_map:
                perf_map[q_short] = {}
            perf_map[q_short][label] = round(pct, 1)

    # Sort queries numerically
    sorted_queries = sorted(perf_map.keys(), key=lambda x: int(x[1:]))
    perf_out = DATA_DIR / "query_performance.csv"
    with open(perf_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["Query", "3-hour chunks (%)", "1-day chunks (%)", "1-week chunks (%)"]
        )
        for q in sorted_queries:
            row = [
                q,
                perf_map[q].get("3-hour chunks", ""),
                perf_map[q].get("1-day chunks", ""),
                perf_map[q].get("1-week chunks", ""),
            ]
            writer.writerow(row)
    logging.info(f"Query performance summary saved to {perf_out}")


if __name__ == "__main__":
    main()
