#!/usr/bin/env python3
"""Generate README graphs from Plow's own run data -> docs/media/N.png.

Data sources: evidence.json (runs) + audits/plow-audit.jsonl (decisions).
Re-run after any demo run so graphs never carry stale numbers.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.join(os.path.dirname(__file__), "..")
MEDIA = os.path.join(ROOT, "docs", "media")
os.makedirs(MEDIA, exist_ok=True)

NAVY = "#061b31"
PURPLE = "#533afd"
PURPLE_LIGHT = "#b9b9f9"
GREEN = "#15be53"
RUBY = "#ea2261"
BORDER = "#e5edf5"
BODY = "#64748d"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "text.color": NAVY,
    "axes.edgecolor": BORDER,
    "axes.labelcolor": BODY,
    "xtick.color": BODY,
    "ytick.color": BODY,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})


def load_evidence() -> dict:
    with open(os.path.join(ROOT, "evidence.json")) as f:
        return json.load(f)


def graph_apy_ranking():
    """1.png — ranked venues by APY (from the latest rank run)."""
    ev = load_evidence()
    ranked = None
    for r in ev["runs"]:
        if r.get("action") == "rank_venues":
            ranked = r.get("ranked") or []
    if not ranked:
        return
    names = [v["name"].replace("Mock ", "") for v in ranked]
    apys = [v["apy"] for v in ranked]
    fig, ax = plt.subplots(figsize=(7.6, 3.4), dpi=150)
    bars = ax.barh(names[::-1], apys[::-1], height=0.52, color=[PURPLE, PURPLE_LIGHT, "#d6d9fc"], edgecolor="none")
    for b, v in zip(bars, apys[::-1]):
        ax.text(b.get_width() + 0.06, b.get_y() + b.get_height() / 2, f"{v:.2f}%", va="center", fontsize=10, color=NAVY, fontweight="bold")
    ax.set_xlabel("APY (%)", fontsize=9)
    ax.set_xlim(0, max(apys) * 1.25)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=9)
    ax.set_title("Ranked venues — live APY (degrade path on testnet)", fontsize=11, color=NAVY, loc="left", pad=10)
    fig.tight_layout()
    fig.savefig(os.path.join(MEDIA, "1.png"), bbox_inches="tight")
    plt.close(fig)


def graph_vault_growth():
    """2.png — sUSDS balance growth across the ALLOW deposits."""
    ev = load_evidence()
    points = [(0, 0)]
    for r in ev["runs"]:
        if r.get("action", "").startswith("deposit ALLOW"):
            shares = r.get("shares")
            if shares is not None:
                points.append((len(points), shares))
        if r.get("action") == "verify_position":
            v = r.get("result") or {}
            if v.get("shares_formatted") is not None and points:
                points[-1] = (points[-1][0], v["shares_formatted"])
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    fig, ax = plt.subplots(figsize=(7.6, 3.4), dpi=150)
    ax.plot(xs, ys, marker="o", color=PURPLE, linewidth=2.2, markersize=6, markerfacecolor="white", markeredgecolor=PURPLE, markeredgewidth=1.8)
    ax.fill_between(xs, ys, color=PURPLE_LIGHT, alpha=0.35)
    for x, y in zip(xs, ys):
        ax.annotate(f"{y:,.0f}", (x, y), textcoords="offset points", xytext=(0, 9), ha="center", fontsize=9, color=NAVY, fontweight="bold")
    ax.set_xlabel("Deposit run", fontsize=9)
    ax.set_ylabel("sUSDS onchain", fontsize=9)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"run {x}" for x in xs], fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=9)
    ax.set_title("Vault balance growth — verified onchain after each deposit", fontsize=11, color=NAVY, loc="left", pad=10)
    fig.tight_layout()
    fig.savefig(os.path.join(MEDIA, "2.png"), bbox_inches="tight")
    plt.close(fig)


def graph_outcomes():
    """3.png — executions per step: sponsored txs vs the zero-tx DENY stop."""
    ev = load_evidence()
    steps = []
    for r in ev["runs"]:
        action = r.get("action", "")
        if action.startswith("deposit ALLOW"):
            steps.append(("approve\nexact", 1 if r.get("tx") else 0))
            steps.append(("deposit\nALLOW", 1 if r.get("tx") else 0))
        elif action.startswith("deposit DENY"):
            steps.append(("deposit\nDENY", r.get("txs") or 0))
    if not steps:
        return
    labels = [s[0] for s in steps]
    vals = [s[1] for s in steps]
    colors = [GREEN if v > 0 else RUBY for v in vals]
    fig, ax = plt.subplots(figsize=(7.6, 3.4), dpi=150)
    bars = ax.bar(labels, vals, width=0.5, color=colors, edgecolor="none")
    for b, v in zip(bars, vals):
        label = f"{v} tx" if v else "zero txs — blocked"
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.05, label, ha="center", fontsize=9, color=NAVY, fontweight="bold")
    ax.set_ylim(0, 1.6)
    ax.set_yticks([0, 1])
    ax.set_ylabel("transactions", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=9)
    ax.set_title("Gated execution — ALLOW lands, DENY broadcasts nothing", fontsize=11, color=NAVY, loc="left", pad=10)
    fig.tight_layout()
    fig.savefig(os.path.join(MEDIA, "3.png"), bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    graph_apy_ranking()
    graph_vault_growth()
    graph_outcomes()
    print("graphs written to docs/media/1.png, 2.png, 3.png")
