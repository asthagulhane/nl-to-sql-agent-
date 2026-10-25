
from pathlib import Path

import pandas as pd
import pytest

from sentinel.investigation import (
    build_transaction_graph,
    investigate,
    load_transactions,
)


def test_generated_data_has_expected_size_and_labels():
    df = load_transactions()

    assert len(df) == 2000
    assert df["transaction_id"].is_unique
    assert df["is_synthetic"].all()
    assert int(df["ground_truth_suspicious"].sum()) == 19


def test_graph_contains_account_transfer_edges():
    df = load_transactions().head(20)
    graph = build_transaction_graph(df)

    assert graph.number_of_nodes() > 0
    assert graph.number_of_edges() >= len(df) * 3

    first = df.iloc[0]

    assert graph.has_edge(
        first["sender_account"],
        first["receiver_account"],
    )


def test_engine_detects_planted_outbound_burst():
    df = load_transactions()
    alerts = investigate(df)

    burst = alerts[
        alerts["alert_type"] == "rapid_outbound_burst"
    ]

    assert burst["entity_id"].eq("ACC00000").any()


def test_engine_detects_planted_shared_device_cluster():
    df = load_transactions()
    alerts = investigate(df)

    clusters = alerts[
        alerts["alert_type"] == "shared_device_cluster"
    ]

    assert clusters["entity_id"].eq("DEV00000").any()


def test_missing_required_column_is_rejected(tmp_path: Path):
    path = tmp_path / "bad.csv"

    pd.DataFrame(
        {"transaction_id": ["TX1"]}
    ).to_csv(path, index=False)

    with pytest.raises(
        ValueError,
        match="Missing required columns",
    ):
        load_transactions(path)


def test_engine_detects_planted_rapid_transfer_chain():
    df = load_transactions()
    alerts = investigate(df)

    chains = alerts[
        alerts["alert_type"] == "rapid_transfer_chain"
    ]

    assert not chains.empty
    assert chains["entity_id"].eq("ACC00070").any()

    chain = chains[
        chains["entity_id"] == "ACC00070"
    ].iloc[0]

    transaction_ids = chain["transaction_ids"].split(",")

    assert len(transaction_ids) == 3
    assert chain["evidence_count"] == 3
