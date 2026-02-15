#!/usr/bin/env python3
"""Seed BigQuery infrastructure_metrics tables with realistic test data.

Generates 2 weeks of synthetic homelab metrics:
  - 10 services with hourly uptime checks (~3,360 rows)
  - 2 Proxmox nodes with hourly resource readings (~672 rows)
  - 10-row service inventory

Idempotent: --replace (default) truncates tables before inserting.
Use --append to add data without truncating.

Usage:
    python scripts/seed_metrics.py --project-id labsight-487303 --dataset infrastructure_metrics_dev
    python scripts/seed_metrics.py --project-id labsight-487303 --dataset infrastructure_metrics_dev --append
"""

import argparse
import datetime
import math
import random
import sys

from google.cloud import bigquery


# --- Service definitions ---

SERVICES = [
    {"name": "adguard", "host": "[PRIVATE_IP_1]", "port": 3000, "container_type": "lxc"},
    {"name": "nginx-proxy-manager", "host": "[PRIVATE_IP_2]", "port": 81, "container_type": "lxc"},
    {"name": "uptime-kuma", "host": "[PRIVATE_IP_3]", "port": 3001, "container_type": "docker"},
    {"name": "portainer", "host": "[PRIVATE_IP_4]", "port": 9443, "container_type": "docker"},
    {"name": "homepage", "host": "[PRIVATE_IP_5]", "port": 3000, "container_type": "docker"},
    {"name": "wireguard", "host": "[PRIVATE_IP_6]", "port": 51820, "container_type": "lxc"},
    {"name": "plex", "host": "[PRIVATE_IP_7]", "port": 32400, "container_type": "lxc"},
    {"name": "grafana", "host": "[PRIVATE_IP_8]", "port": 3000, "container_type": "docker"},
    {"name": "prometheus", "host": "[PRIVATE_IP_9]", "port": 9090, "container_type": "docker"},
    {"name": "pihole-secondary", "host": "[PRIVATE_IP_10]", "port": 80, "container_type": "lxc"},
]

NODES = ["pve01", "pve02"]

# Each service gets 2-3 downtime windows (start_hour_offset, duration_hours)
DOWNTIME_WINDOWS: dict[str, list[tuple[int, int]]] = {
    "adguard": [(48, 1), (200, 2)],
    "nginx-proxy-manager": [(72, 3), (150, 1), (280, 2)],
    "uptime-kuma": [(100, 1)],
    "portainer": [(160, 2), (300, 1)],
    "homepage": [(50, 1), (250, 1)],
    "wireguard": [(120, 4), (310, 1)],
    "plex": [(80, 2), (220, 1), (320, 1)],
    "grafana": [(90, 1)],
    "prometheus": [(180, 2), (260, 1)],
    "pihole-secondary": [(140, 3), (290, 2)],
}


def generate_uptime_events(start: datetime.datetime, hours: int) -> list[dict]:
    """Generate hourly uptime check rows for all services."""
    rows = []
    for service in SERVICES:
        windows = DOWNTIME_WINDOWS.get(service["name"], [])
        for h in range(hours):
            checked_at = start + datetime.timedelta(hours=h)
            is_down = any(offset <= h < offset + dur for offset, dur in windows)

            if is_down:
                rows.append({
                    "checked_at": checked_at.isoformat(),
                    "service_name": service["name"],
                    "status": "down",
                    "response_time_ms": None,
                    "status_code": 0,
                    "message": "Connection refused",
                })
            else:
                # Realistic response times: 5-200ms with some jitter
                base_rt = random.uniform(5, 50)
                jitter = random.gauss(0, 10)
                rt = max(1.0, base_rt + jitter)

                rows.append({
                    "checked_at": checked_at.isoformat(),
                    "service_name": service["name"],
                    "status": "up",
                    "response_time_ms": round(rt, 1),
                    "status_code": 200,
                    "message": None,
                })
    return rows


def generate_resource_utilization(start: datetime.datetime, hours: int) -> list[dict]:
    """Generate hourly resource utilization for Proxmox nodes.

    CPU follows a sinusoidal pattern (busier during daytime),
    memory is relatively stable, storage creeps up slowly.
    """
    rows = []
    for node_idx, node in enumerate(NODES):
        base_cpu = 15 + node_idx * 10  # pve01 baseline ~15%, pve02 ~25%
        base_mem = 45 + node_idx * 15  # pve01 ~45%, pve02 ~60%
        base_storage = 35 + node_idx * 10

        for h in range(hours):
            collected_at = start + datetime.timedelta(hours=h)
            hour_of_day = collected_at.hour

            # Sinusoidal CPU: peaks around 14:00, troughs around 02:00
            cpu_cycle = base_cpu + 20 * math.sin((hour_of_day - 2) * math.pi / 12)
            cpu = max(1.0, min(99.0, cpu_cycle + random.gauss(0, 5)))

            # Memory: stable with small random walks
            mem = max(10.0, min(95.0, base_mem + random.gauss(0, 3)))

            # Storage: slowly increasing
            storage = min(90.0, base_storage + (h / hours) * 5 + random.gauss(0, 1))

            rows.append({
                "collected_at": collected_at.isoformat(),
                "node": node,
                "cpu_percent": round(cpu, 1),
                "memory_percent": round(mem, 1),
                "storage_percent": round(storage, 1),
            })
    return rows


def generate_service_inventory() -> list[dict]:
    """Generate the service inventory table."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return [
        {
            "service_name": s["name"],
            "host": s["host"],
            "port": s["port"],
            "container_type": s["container_type"],
            "last_seen": now.isoformat(),
        }
        for s in SERVICES
    ]


def truncate_table(client: bigquery.Client, table_id: str) -> None:
    """Delete all rows from a table (BigQuery equivalent of TRUNCATE)."""
    query = f"DELETE FROM `{table_id}` WHERE TRUE"
    job = client.query(query)
    job.result()
    print(f"  Truncated {table_id}")


def insert_rows(client: bigquery.Client, table_id: str, rows: list[dict]) -> None:
    """Insert rows into a BigQuery table in batches."""
    batch_size = 500
    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        errors = client.insert_rows_json(table_id, batch)
        if errors:
            print(f"  ERROR inserting batch {i // batch_size}: {errors[:3]}")
            sys.exit(1)
        total += len(batch)
    print(f"  Inserted {total} rows into {table_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed BigQuery infrastructure metrics")
    parser.add_argument("--project-id", required=True, help="GCP project ID")
    parser.add_argument("--dataset", required=True, help="BigQuery dataset ID")
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append data without truncating (default: replace)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="Number of days of data to generate (default: 14)",
    )
    args = parser.parse_args()

    project = args.project_id
    dataset = args.dataset
    hours = args.days * 24

    # Seed the RNG for reproducible data
    random.seed(42)

    client = bigquery.Client(project=project)

    # Table IDs
    uptime_table = f"{project}.{dataset}.uptime_events"
    resource_table = f"{project}.{dataset}.resource_utilization"
    inventory_table = f"{project}.{dataset}.service_inventory"

    start_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=args.days)

    print(f"Generating {args.days} days of test data...")
    print(f"  Start: {start_time.isoformat()}")
    print(f"  Services: {len(SERVICES)}")
    print(f"  Nodes: {len(NODES)}")
    print()

    # Generate data
    uptime_rows = generate_uptime_events(start_time, hours)
    resource_rows = generate_resource_utilization(start_time, hours)
    inventory_rows = generate_service_inventory()

    print(f"Generated: {len(uptime_rows)} uptime events, "
          f"{len(resource_rows)} resource readings, "
          f"{len(inventory_rows)} inventory entries")
    print()

    # Truncate if replacing
    if not args.append:
        print("Truncating existing data...")
        truncate_table(client, uptime_table)
        truncate_table(client, resource_table)
        truncate_table(client, inventory_table)
        print()

    # Insert
    print("Inserting data...")
    insert_rows(client, uptime_table, uptime_rows)
    insert_rows(client, resource_table, resource_rows)
    insert_rows(client, inventory_table, inventory_rows)

    print()
    print("Done!")


if __name__ == "__main__":
    main()
