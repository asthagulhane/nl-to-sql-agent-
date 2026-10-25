
"""Rule-based investigation engine for synthetic UPI transactions."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pandas as pd


DATA_DIR = Path(__file__).resolve().parent / "data"


def load_transactions(path: Path | str | None = None) -> pd.DataFrame:
    """Load and validate the transaction CSV."""
    csv_path = Path(path) if path else DATA_DIR / "transactions.csv"
    df = pd.read_csv(csv_path)

    required = {
        "transaction_id",
        "timestamp",
        "sender_account",
        "receiver_account",
        "device_id",
        "merchant_id",
        "amount_inr",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df["timestamp"] = pd.to_datetime(
        df["timestamp"], utc=True, errors="raise"
    )
    df["amount_inr"] = pd.to_numeric(
        df["amount_inr"], errors="raise"
    )

    if (df["amount_inr"] < 0).any():
        raise ValueError("Transaction amounts cannot be negative")

    return df.sort_values("timestamp").reset_index(drop=True)


def build_transaction_graph(transactions: pd.DataFrame) -> nx.MultiDiGraph:
    """Build a directed graph of transfers and entity relationships."""
    graph = nx.MultiDiGraph()

    for row in transactions.itertuples(index=False):
        sender = str(row.sender_account)
        receiver = str(row.receiver_account)
        device = str(row.device_id)
        merchant = str(row.merchant_id)

        graph.add_node(sender, entity_type="account")
        graph.add_node(receiver, entity_type="account")
        graph.add_node(device, entity_type="device")
        graph.add_node(merchant, entity_type="merchant")

        graph.add_edge(
            sender,
            receiver,
            key=str(row.transaction_id),
            relationship="transfer",
            transaction_id=str(row.transaction_id),
            amount_inr=float(row.amount_inr),
            timestamp=str(row.timestamp),
        )
        graph.add_edge(
            sender,
            device,
            key=f"{row.transaction_id}:device",
            relationship="used_device",
        )
        graph.add_edge(
            sender,
            merchant,
            key=f"{row.transaction_id}:merchant",
            relationship="paid_merchant",
        )

    return graph


def investigate(transactions: pd.DataFrame) -> pd.DataFrame:
    """Generate transparent alerts for patterns that warrant review.

    Alerts are investigation leads, not proof of fraud.
    """
    df = transactions.copy()
    df["timestamp"] = pd.to_datetime(
        df["timestamp"], utc=True, errors="raise"
    )

    alerts: list[dict] = []

    # Rule 1: five or more transfers to distinct recipients
    # within a rolling 15-minute window.
    for sender, group in df.groupby("sender_account"):
        group = group.sort_values("timestamp").reset_index(drop=True)

        for _, row in group.iterrows():
            window_start = row["timestamp"] - pd.Timedelta(minutes=15)
            window = group[
                (group["timestamp"] >= window_start)
                & (group["timestamp"] <= row["timestamp"])
            ]

            recipient_count = window["receiver_account"].nunique()

            if len(window) >= 5 and recipient_count >= 5:
                alerts.append({
                    "alert_type": "rapid_outbound_burst",
                    "entity_id": str(sender),
                    "evidence_count": int(len(window)),
                    "distinct_recipients": int(recipient_count),
                    "window_start": str(window["timestamp"].min()),
                    "window_end": str(window["timestamp"].max()),
                    "transaction_ids": ",".join(
                        window["transaction_id"].astype(str)
                    ),
                    "explanation": (
                        f"Account {sender} sent {len(window)} transfers "
                        f"to {recipient_count} distinct recipients "
                        "within 15 minutes. Review the transactions; "
                        "this pattern alone does not establish fraud."
                    ),
                })
                break

    # Rule 2: five or more distinct sending accounts share a device
    # within a rolling 30-minute window.
    for device, group in df.groupby("device_id"):
        group = group.sort_values("timestamp").reset_index(drop=True)

        for _, row in group.iterrows():
            window_start = row["timestamp"] - pd.Timedelta(minutes=30)
            window = group[
                (group["timestamp"] >= window_start)
                & (group["timestamp"] <= row["timestamp"])
            ]

            account_count = window["sender_account"].nunique()

            if account_count >= 5:
                alerts.append({
                    "alert_type": "shared_device_cluster",
                    "entity_id": str(device),
                    "evidence_count": int(len(window)),
                    "distinct_recipients": int(account_count),
                    "window_start": str(window["timestamp"].min()),
                    "window_end": str(window["timestamp"].max()),
                    "transaction_ids": ",".join(
                        window["transaction_id"].astype(str)
                    ),
                    "explanation": (
                        f"Device {device} was associated with "
                        f"{account_count} distinct sending accounts "
                        "within 30 minutes. Shared-device use can have "
                        "legitimate explanations and warrants review."
                    ),
                })
                break

    # Rule 3: three consecutive transfers across four distinct accounts
    # within 15 minutes: A -> B -> C -> D.
    transfers = df.sort_values("timestamp").copy()

    outgoing = {}
    for row in transfers.itertuples(index=False):
        outgoing.setdefault(
            str(row.sender_account), []
        ).append(row)

    seen_chains = set()

    for first in transfers.itertuples(index=False):
        first_sender = str(first.sender_account)
        first_receiver = str(first.receiver_account)

        for second in outgoing.get(first_receiver, []):
            if second.timestamp <= first.timestamp:
                continue

            if (
                second.timestamp - first.timestamp
                > pd.Timedelta(minutes=15)
            ):
                continue

            second_receiver = str(second.receiver_account)

            for third in outgoing.get(second_receiver, []):
                if third.timestamp <= second.timestamp:
                    continue

                if (
                    third.timestamp - first.timestamp
                    > pd.Timedelta(minutes=15)
                ):
                    continue

                third_receiver = str(third.receiver_account)

                accounts = {
                    first_sender,
                    first_receiver,
                    second_receiver,
                    third_receiver,
                }
                if len(accounts) != 4:
                    continue

                chain_ids = (
                    str(first.transaction_id),
                    str(second.transaction_id),
                    str(third.transaction_id),
                )

                if chain_ids in seen_chains:
                    continue

                seen_chains.add(chain_ids)

                alerts.append({
                    "alert_type": "rapid_transfer_chain",
                    "entity_id": first_sender,
                    "evidence_count": 3,
                    "distinct_recipients": 3,
                    "window_start": str(first.timestamp),
                    "window_end": str(third.timestamp),
                    "transaction_ids": ",".join(chain_ids),
                    "explanation": (
                        f"Three linked transfers from {first_sender} "
                        f"through {first_receiver} and {second_receiver} "
                        f"to {third_receiver} occurred within 15 minutes. "
                        "Review the linked transactions; this pattern "
                        "alone does not establish fraud."
                    ),
                })

    columns = [
        "alert_type",
        "entity_id",
        "evidence_count",
        "distinct_recipients",
        "window_start",
        "window_end",
        "transaction_ids",
        "explanation",
    ]

    return pd.DataFrame(alerts, columns=columns)


def main() -> None:
    transactions = load_transactions()
    graph = build_transaction_graph(transactions)
    alerts = investigate(transactions)

    output_path = DATA_DIR / "investigation_alerts.csv"
    alerts.to_csv(output_path, index=False)

    print(f"Transactions loaded: {len(transactions):,}")
    print(f"Graph nodes: {graph.number_of_nodes():,}")
    print(f"Graph edges: {graph.number_of_edges():,}")
    print(f"Investigation alerts: {len(alerts):,}")

    if alerts.empty:
        print("No rule-based alerts found.")
    else:
        print("\nAlert types:")
        print(alerts["alert_type"].value_counts().to_string())
        print(f"\nSaved evidence to: {output_path}")


if __name__ == "__main__":
    main()
