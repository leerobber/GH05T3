"""OSS lab metrics — logging schema + visualization helpers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LogEntry = dict[str, Any]

_REPO = Path(__file__).resolve().parents[2]
_LOG_PATH = _REPO / "data" / "saas_lab_logs.jsonl"


def make_log_entry(
    *,
    cycle: int,
    agent_id: str,
    role: str,
    traits: dict[str, float],
    fitness: float,
    neurocoins: float,
    proposal: dict[str, Any],
    score: float,
    mutations: dict[str, Any] | None = None,
    lineage: dict[str, Any] | None = None,
    events: list[str] | None = None,
) -> LogEntry:
    return {
        "cycle": cycle,
        "agent_id": agent_id,
        "role": role,
        "traits": traits,
        "fitness": fitness,
        "neurocoins": neurocoins,
        "proposal": proposal,
        "score": score,
        "mutations": mutations or {},
        "lineage": lineage or {},
        "events": events or [],
    }


def append_logs(logs: list[LogEntry], path: Path | None = None) -> None:
    target = path or _LOG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "a", encoding="utf-8") as f:
        for entry in logs:
            f.write(json.dumps(entry) + "\n")


def load_logs(path: Path | None = None) -> list[LogEntry]:
    target = path or _LOG_PATH
    if not target.exists():
        return []
    rows: list[LogEntry] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def logs_to_dataframe(logs: list[LogEntry]):
    import pandas as pd

    rows: list[dict[str, Any]] = []
    for entry in logs:
        base = {
            "cycle": entry["cycle"],
            "agent_id": entry["agent_id"],
            "role": entry["role"],
            "fitness": entry["fitness"],
            "neurocoins": entry["neurocoins"],
            "score": entry["score"],
            "events": ",".join(entry.get("events", [])),
            "parent_id": entry.get("lineage", {}).get("parent_id"),
        }
        for t_name, t_val in entry.get("traits", {}).items():
            base[f"trait_{t_name}"] = t_val
        rows.append(base)
    return pd.DataFrame(rows)


def trade_logs_from_transactions(transactions: list[dict[str, Any]]):
    import pandas as pd

    rows = []
    for i, tx in enumerate(transactions):
        if tx.get("kind") != "list_trait":
            continue
        rows.append({
            "cycle": i,
            "trait_name": tx.get("detail", "unknown"),
            "volume": 1,
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["cycle", "trait_name", "volume"])


def compute_collective_metrics(logs: list[LogEntry]) -> dict[str, Any]:
    if not logs:
        return {}
    by_cycle: dict[int, list[float]] = {}
    trait_hist: dict[str, list[float]] = {}
    for entry in logs:
        c = entry["cycle"]
        by_cycle.setdefault(c, []).append(entry["score"])
        for t, v in entry.get("traits", {}).items():
            trait_hist.setdefault(t, []).append(v)
    scores = [entry["score"] for entry in logs]
    return {
        "cycles": len(by_cycle),
        "agents": len({e["agent_id"] for e in logs}),
        "mean_score": sum(scores) / len(scores),
        "max_score": max(scores),
        "trait_means": {t: sum(v) / len(v) for t, v in trait_hist.items()},
        "per_cycle_mean_score": {
            str(c): sum(v) / len(v) for c, v in sorted(by_cycle.items())
        },
    }


def plot_trait_evolution(df, agent_id: str):
    import matplotlib.pyplot as plt

    agent_df = df[df["agent_id"] == agent_id].sort_values("cycle")
    trait_cols = [c for c in agent_df.columns if c.startswith("trait_")]
    plt.figure(figsize=(8, 4))
    for col in trait_cols:
        plt.plot(agent_df["cycle"], agent_df[col], label=col.replace("trait_", ""))
    plt.xlabel("Cycle")
    plt.ylabel("Trait value")
    plt.title(f"Trait evolution — {agent_id}")
    plt.legend(fontsize=8)
    plt.tight_layout()
    return plt.gcf()


def plot_species_trait_landscape(df, trait_x: str, trait_y: str):
    import matplotlib.pyplot as plt

    x_col, y_col = f"trait_{trait_x}", f"trait_{trait_y}"
    plt.figure(figsize=(6, 6))
    plt.scatter(df[x_col], df[y_col], c=df["fitness"], cmap="viridis", alpha=0.7)
    plt.xlabel(trait_x)
    plt.ylabel(trait_y)
    plt.title("Species trait landscape")
    plt.colorbar(label="Fitness")
    plt.tight_layout()
    return plt.gcf()


def plot_fitness_over_time(df):
    import matplotlib.pyplot as plt

    plt.figure(figsize=(8, 4))
    for agent_id, group in df.groupby("agent_id"):
        g = group.sort_values("cycle")
        plt.plot(g["cycle"], g["fitness"], alpha=0.5, label=agent_id)
    plt.xlabel("Cycle")
    plt.ylabel("Fitness")
    plt.title("Fitness over time")
    plt.tight_layout()
    return plt.gcf()


def plot_wealth_distribution(df, cycle: int):
    import matplotlib.pyplot as plt

    cycle_df = df[df["cycle"] == cycle]
    plt.figure(figsize=(6, 4))
    plt.hist(cycle_df["neurocoins"], bins=10, alpha=0.7)
    plt.xlabel("NeuroCoins")
    plt.ylabel("Count")
    plt.title(f"Wealth distribution — cycle {cycle}")
    plt.tight_layout()
    return plt.gcf()


def plot_trait_market_activity(trade_logs):
    import matplotlib.pyplot as plt

    if trade_logs.empty:
        plt.figure(figsize=(6, 3))
        plt.text(0.5, 0.5, "No trait trades yet", ha="center")
        return plt.gcf()
    grouped = trade_logs.groupby("trait_name")["volume"].sum().reset_index()
    plt.figure(figsize=(8, 4))
    plt.bar(grouped["trait_name"], grouped["volume"])
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("Total trades")
    plt.title("Trait market activity")
    plt.tight_layout()
    return plt.gcf()


def build_lineage_graph(df):
    import networkx as nx

    G = nx.DiGraph()
    for _, row in df.iterrows():
        agent = row["agent_id"]
        parent = row.get("parent_id")
        G.add_node(agent)
        if parent and str(parent) != "nan":
            G.add_edge(str(parent), agent)
    return G


def plot_lineage_tree(df):
    import matplotlib.pyplot as plt
    import networkx as nx

    G = build_lineage_graph(df)
    plt.figure(figsize=(8, 6))
    if G.number_of_nodes() == 0:
        plt.text(0.5, 0.5, "No lineage data", ha="center")
        return plt.gcf()
    pos = nx.spring_layout(G, seed=42)
    nx.draw(G, pos, with_labels=True, node_size=400, font_size=7)
    plt.title("Lineage tree")
    plt.tight_layout()
    return plt.gcf()


def run_streamlit_dashboard(logs: list[LogEntry], trade_logs=None) -> None:
    import streamlit as st

    df = logs_to_dataframe(logs)
    if trade_logs is None:
        trade_logs = trade_logs_from_transactions([])

    st.title("OSS Product-Design Lab")
    if df.empty:
        st.warning("No lab logs yet — run the SaaS lab first.")
        return

    agent_ids = sorted(df["agent_id"].unique())
    selected_agent = st.sidebar.selectbox("Agent", agent_ids)
    cycles = sorted(df["cycle"].unique())
    selected_cycle = st.sidebar.slider(
        "Cycle", min_value=min(cycles), max_value=max(cycles), value=max(cycles),
    )
    trait_cols = [c.replace("trait_", "") for c in df.columns if c.startswith("trait_")]
    trait_x = st.sidebar.selectbox("Trait X", trait_cols or ["creativity"])
    # market_intuition is now part of canonical UNIVERSAL_TRAITS
    trait_y = st.sidebar.selectbox("Trait Y", trait_cols or ["market_intuition"])

    st.pyplot(plot_trait_evolution(df, selected_agent))
    st.pyplot(plot_species_trait_landscape(df, trait_x, trait_y))
    st.pyplot(plot_fitness_over_time(df))
    st.pyplot(plot_lineage_tree(df))
    st.pyplot(plot_wealth_distribution(df, selected_cycle))
    st.pyplot(plot_trait_market_activity(trade_logs))
    st.dataframe(df[["cycle", "agent_id", "events", "score", "fitness"]])