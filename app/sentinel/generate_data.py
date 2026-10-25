
"""Generate reproducible synthetic UPI data for QueryMind Sentinel.

All records are fictional and intended for testing only.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


SEED = 42
DEFAULT_TRANSACTIONS = 2_000
OUTPUT_DIR = Path(__file__).resolve().parent / "data"


def generate_data(
    n_transactions: int = DEFAULT_TRANSACTIONS,
    seed: int = SEED,
) -> dict[str, pd.DataFrame]:
    """Return synthetic entities and transactions with planted scenarios."""
    if n_transactions < 200:
        raise ValueError("n_transactions must be at least 200")

    rng = __import__("numpy").random.default_rng(seed)

    n_accounts = max(100, n_transactions // 8)
    n_devices = max(60, n_accounts // 2)
    n_merchants = max(30, n_accounts // 4)

    accounts = pd.DataFrame({
        "account_id": [f"ACC{i:05d}" for i in range(n_accounts)],
        "account_age_days": rng.integers(1, 2500, n_accounts),
        "account_type": rng.choice(
            ["savings", "current"], n_accounts, p=[0.92, 0.08]
        ),
        "is_synthetic": True,
    })

    devices = pd.DataFrame({
        "device_id": [f"DEV{i:05d}" for i in range(n_devices)],
        "device_type": rng.choice(
            ["android", "ios"], n_devices, p=[0.88, 0.12]
        ),
        "is_synthetic": True,
    })

    merchants = pd.DataFrame({
        "merchant_id": [f"MER{i:05d}" for i in range(n_merchants)],
        "merchant_category": rng.choice(
            ["grocery", "food", "travel", "utilities", "retail"],
            n_merchants,
        ),
        "is_synthetic": True,
    })

    account_ids = accounts["account_id"].tolist()
    device_ids = devices["device_id"].tolist()
    merchant_ids = merchants["merchant_id"].tolist()

    timestamps = pd.Timestamp("2026-01-01", tz="UTC") + pd.to_timedelta(
        rng.integers(0, 30 * 24 * 60 * 60, n_transactions), unit="s"
    )

    transactions = pd.DataFrame({
        "transaction_id": [f"TXN{i:07d}" for i in range(n_transactions)],
        "timestamp": timestamps,
        "sender_account": rng.choice(account_ids, n_transactions),
        "receiver_account": rng.choice(account_ids, n_transactions),
        "device_id": rng.choice(device_ids, n_transactions),
        "merchant_id": rng.choice(merchant_ids, n_transactions),
        "amount_inr": rng.choice(
            [50, 100, 150, 200, 250, 500, 750, 1000, 1500, 2500, 5000],
            n_transactions,
            p=[.08, .10, .08, .12, .10, .15, .08, .10, .07, .07, .05],
        ),
        "is_synthetic": True,
        "scenario_label": "normal",
        "ground_truth_suspicious": False,
    })

    # Scenario A: one sender rapidly transfers to many recipients.
    # These are known suspicious examples for evaluation, not proof of fraud.
    burst_count = 8
    burst_start = 0
    burst_sender = account_ids[0]
    burst_times = pd.date_range(
        "2026-01-15 10:00:00", periods=burst_count, freq="2min", tz="UTC"
    )
    for offset in range(burst_count):
        idx = burst_start + offset
        transactions.loc[idx, "timestamp"] = burst_times[offset]
        transactions.loc[idx, "sender_account"] = burst_sender
        transactions.loc[idx, "receiver_account"] = account_ids[10 + offset]
        transactions.loc[idx, "amount_inr"] = 4900 + offset * 10
        transactions.loc[idx, "scenario_label"] = "rapid_outbound_burst"
        transactions.loc[idx, "ground_truth_suspicious"] = True

    # Scenario B: several accounts use the same device in a short period.
    shared_device = device_ids[0]
    shared_start = burst_count
    shared_count = 8
    shared_times = pd.date_range(
        "2026-01-20 15:00:00", periods=shared_count, freq="3min", tz="UTC"
    )
    for offset in range(shared_count):
        idx = shared_start + offset
        transactions.loc[idx, "timestamp"] = shared_times[offset]
        transactions.loc[idx, "sender_account"] = account_ids[20 + offset]
        transactions.loc[idx, "receiver_account"] = account_ids[50 + offset]
        transactions.loc[idx, "device_id"] = shared_device
        transactions.loc[idx, "amount_inr"] = 900 + offset * 25
        transactions.loc[idx, "scenario_label"] = "shared_device_cluster"
        transactions.loc[idx, "ground_truth_suspicious"] = True

    # Scenario C: a short transfer chain A -> B -> C -> D.
    chain_start = shared_start + shared_count
    chain_accounts = account_ids[70:74]
    chain_times = pd.date_range(
        "2026-01-25 09:00:00", periods=3, freq="4min", tz="UTC"
    )
    for offset in range(3):
        idx = chain_start + offset
        transactions.loc[idx, "timestamp"] = chain_times[offset]
        transactions.loc[idx, "sender_account"] = chain_accounts[offset]
        transactions.loc[idx, "receiver_account"] = chain_accounts[offset + 1]
        transactions.loc[idx, "amount_inr"] = 3000 + offset * 100
        transactions.loc[idx, "scenario_label"] = "rapid_transfer_chain"
        transactions.loc[idx, "ground_truth_suspicious"] = True

    return {
        "accounts": accounts,
        "devices": devices,
        "merchants": merchants,
        "transactions": transactions.sort_values(
            ["timestamp", "transaction_id"]
        ).reset_index(drop=True),
    }


def save_data(
    datasets: dict[str, pd.DataFrame],
    output_dir: Path = OUTPUT_DIR,
) -> None:
    """Write datasets to CSV files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in datasets.items():
        frame.to_csv(output_dir / f"{name}.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate fictional UPI transaction data for Sentinel."
    )
    parser.add_argument("--transactions", type=int, default=DEFAULT_TRANSACTIONS)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    datasets = generate_data(args.transactions, args.seed)
    save_data(datasets)

    print("Synthetic Sentinel datasets created:")
    for name, frame in datasets.items():
        print(f"  {name}: {len(frame):,} rows")
    tx = datasets["transactions"]
    print(f"  Known suspicious transactions: {int(tx['ground_truth_suspicious'].sum()):,}")
    print(f"  Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
