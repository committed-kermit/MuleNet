"""
Feature Engineering Pipeline — Person 3 (ML - Sequence & SHAP)

Reads raw IBM AML CSVs and produces the node_features_engineered.csv
used by both the XGBoost training script and the GAT training script.

Run from repo root:
    python scripts/feature_engineering.py

Output:
    data/raw/node_features_engineered.csv
"""

import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime


RAW_DIR = "data/raw"
OUT_PATH = os.path.join(RAW_DIR, "node_features_engineered.csv")

# Column aliases used in different IBM AML dataset versions
SENDER_ALIASES   = ["From Bank", "from_bank", "Sender_BIC", "sender_bank"]
ACCOUNT_ALIASES  = ["Account",   "account",   "Sender_Account"]
RECEIVER_ALIASES = ["To Bank",   "to_bank",   "Receiver_BIC", "receiver_bank"]
TO_ACC_ALIASES   = ["Account.1", "account_1", "Receiver_Account"]
AMOUNT_ALIASES   = ["Amount Received", "amount_received", "Amount", "amount"]
CURRENCY_ALIASES = ["Receiving Currency", "receiving_currency", "Currency", "currency"]
FORMAT_ALIASES   = ["Payment Format", "payment_format", "Format"]
LAUNDER_ALIASES  = ["Is Laundering", "is_laundering", "label", "Label"]
TIMESTAMP_ALIASES = ["Timestamp", "timestamp", "Date", "date"]


def _pick_col(df: pd.DataFrame, aliases: list, default=None):
    for a in aliases:
        if a in df.columns:
            return a
    return default


def load_transactions(raw_dir: str) -> pd.DataFrame:
    candidates = [
        "HI-Small_Trans.csv",
        "LI-Small_Trans.csv",
        "HI-Large_Trans.csv",
        "transactions.csv",
    ]
    for fname in candidates:
        p = os.path.join(raw_dir, fname)
        if os.path.exists(p):
            print(f"Loading {p} ...")
            df = pd.read_csv(p, low_memory=False)
            print(f"  Loaded {len(df):,} rows, {df.shape[1]} columns")
            return df
    raise FileNotFoundError(
        f"No transaction CSV found in {raw_dir}. "
        "Expected one of: " + ", ".join(candidates)
    )


def build_canonical_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Create sender_id / receiver_id as BANK_ACCOUNT strings."""
    sb = _pick_col(df, SENDER_ALIASES)
    sa = _pick_col(df, ACCOUNT_ALIASES)
    rb = _pick_col(df, RECEIVER_ALIASES)
    ra = _pick_col(df, TO_ACC_ALIASES)

    if sb and sa:
        df["sender_id"] = df[sb].astype(str).str.strip() + "_" + df[sa].astype(str).str.strip()
    if rb and ra:
        df["receiver_id"] = df[rb].astype(str).str.strip() + "_" + df[ra].astype(str).str.strip()
    return df


def compute_node_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes per-node (account-level) aggregated graph features.

    Features produced:
      total_degree, in_degree, out_degree,
      in_degree_ratio, out_degree_ratio,
      flow_imbalance,
      log_total_degree,
      fan_in_out_ratio,
      degree_vs_time_mean,
      total_sent, total_received,
      mean_sent_amount, std_sent_amount,
      mean_received_amount,
      unique_counterparties,
      feature_mean, feature_std,
      extreme_feature_count_2, extreme_feature_count_3,
      is_laundering  (label)
    """
    amount_col   = _pick_col(df, AMOUNT_ALIASES,   "Amount Received")
    launder_col  = _pick_col(df, LAUNDER_ALIASES)

    # ---- Sender-side aggregates ----
    sender_grp = df.groupby("sender_id")
    sent_stats = sender_grp[amount_col].agg(
        total_sent="sum",
        mean_sent_amount="mean",
        std_sent_amount="std",
        out_degree="count",
    ).fillna(0)
    sent_unique_cp = sender_grp["receiver_id"].nunique().rename("unique_receivers")

    # ---- Receiver-side aggregates ----
    recv_grp = df.groupby("receiver_id")
    recv_stats = recv_grp[amount_col].agg(
        total_received="sum",
        mean_received_amount="mean",
        in_degree="count",
    ).fillna(0)
    recv_unique_cp = recv_grp["sender_id"].nunique().rename("unique_senders")

    # ---- Merge into node table ----
    nodes = sent_stats.join(sent_unique_cp, how="outer") \
                      .join(recv_stats, how="outer") \
                      .join(recv_unique_cp, how="outer") \
                      .fillna(0)

    nodes["total_degree"]   = nodes["in_degree"] + nodes["out_degree"]
    nodes["in_degree_ratio"]  = nodes["in_degree"]  / nodes["total_degree"].clip(lower=1)
    nodes["out_degree_ratio"] = nodes["out_degree"] / nodes["total_degree"].clip(lower=1)

    nodes["flow_imbalance"] = (
        (nodes["total_received"] - nodes["total_sent"]).abs()
        / (nodes["total_received"] + nodes["total_sent"]).clip(lower=1)
    )

    nodes["log_total_degree"]   = np.log1p(nodes["total_degree"])
    nodes["unique_counterparties"] = (
        nodes.get("unique_receivers", 0) + nodes.get("unique_senders", 0)
    )
    nodes["fan_in_out_ratio"]   = (nodes["in_degree"] + 1) / (nodes["out_degree"] + 1)
    nodes["degree_vs_time_mean"] = np.log1p(nodes["total_degree"]) * nodes["flow_imbalance"]

    # Normalised mean/std of outgoing amounts
    global_mean = nodes["mean_sent_amount"].mean()
    global_std  = nodes["mean_sent_amount"].std() + 1e-5
    nodes["feature_mean"] = (nodes["mean_sent_amount"] - global_mean) / global_std
    nodes["feature_std"]  = nodes["std_sent_amount"] / (nodes["mean_sent_amount"].clip(lower=1))

    # Extreme feature counts (proxy for multi-signal anomaly)
    thresholds_2 = {
        "flow_imbalance": 0.75,
        "fan_in_out_ratio": 3.0,
        "out_degree_ratio": 0.80,
        "log_total_degree": np.log1p(20),
    }
    thresholds_3 = {
        "flow_imbalance": 0.90,
        "fan_in_out_ratio": 6.0,
        "out_degree_ratio": 0.95,
    }
    nodes["extreme_feature_count_2"] = sum(
        (nodes[col] > thr).astype(int)
        for col, thr in thresholds_2.items()
        if col in nodes.columns
    )
    nodes["extreme_feature_count_3"] = sum(
        (nodes[col] > thr).astype(int)
        for col, thr in thresholds_3.items()
        if col in nodes.columns
    )

    # ---- Label: any laundering edge on this node ----
    if launder_col:
        launder_senders   = set(df[df[launder_col] == 1]["sender_id"].unique())
        launder_receivers = set(df[df[launder_col] == 1]["receiver_id"].unique())
        mule_nodes = launder_senders | launder_receivers
        nodes["is_laundering"] = nodes.index.isin(mule_nodes).astype(int)
    else:
        nodes["is_laundering"] = 0

    return nodes.reset_index().rename(columns={"index": "node_id", "sender_id": "node_id"})


def main():
    os.makedirs(RAW_DIR, exist_ok=True)

    try:
        df = load_transactions(RAW_DIR)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print("Building canonical sender/receiver IDs ...")
    df = build_canonical_ids(df)

    print("Computing node-level features ...")
    node_features = compute_node_features(df)

    print(f"Node feature table shape: {node_features.shape}")
    print(node_features.describe().T[["mean", "std", "min", "max"]].to_string())

    node_features.to_csv(OUT_PATH, index=False)
    print(f"\nSaved engineered features -> {OUT_PATH}")

    mule_pct = node_features["is_laundering"].mean() * 100
    print(f"Mule node prevalence: {mule_pct:.2f}%")


if __name__ == "__main__":
    main()
