"""Generate report figures from results/*.csv.  Usage: python plots.py"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

OUT = "results"
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
# Categorical slots in fixed order (validated reference palette)
COL = {"rr": "#eda100", "maxci": "#e87ba4", "pf": "#eb6834", "mlwdf": "#1baf7a", "pulse_full": "#2a78d6"}
NAME = {"rr": "Round Robin", "maxci": "Max C/I", "pf": "Prop. Fair", "mlwdf": "M-LWDF",
        "pulse_full": "PULSE (proposed)"}
MARK = {"rr": "s", "maxci": "D", "pf": "^", "mlwdf": "v", "pulse_full": "o"}

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
    "axes.titlecolor": INK, "axes.titlelocation": "left", "legend.frameon": False,
})


def sweep(df, metric, title, ylabel, fname, scale=1.0, note=None):
    fig, ax = plt.subplots(figsize=(6.4, 4))
    for k in COL:
        d = df[df.key == k].sort_values("load")
        lw = 2.6 if k == "pulse_full" else 1.8
        ax.plot(d.load, d[metric] * scale, color=COL[k], lw=lw, marker=MARK[k], ms=7,
                markeredgecolor=SURF, markeredgewidth=1.5, label=NAME[k], zorder=3 if k == "pulse_full" else 2)
    ax.set_title(title)
    ax.set_xlabel("Offered load (× nominal)")
    ax.set_ylabel(ylabel)
    if note:
        ax.text(0.0, -0.22, note, transform=ax.transAxes, fontsize=8.5, color=INK2)
    ax.legend(loc="best", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, fname), dpi=160)
    plt.close(fig)


def ablation(df, load, fname):
    keys = ["pf", "pulse", "pulse_ica", "pulse_ica_olla", "pulse_ica_sfr", "pulse_dtx", "pulse_full"]
    labels = ["Prop. Fair (baseline)", "+ PULSE scheduler", "+ ICA link adapt.", "+ OLLA",
              "+ Adaptive SFR", "+ Cell DTX", "+ Slack-aware ECO"]
    d = df[df.load == load].set_index("key").loc[keys]
    metrics = [("bler", "BLER (%)", 100), ("qos_satisfied_pct", "QoS-satisfied RT users (%)", 1),
               ("avg_power_w", "Avg power per cell (W)", 1), ("bits_per_joule", "Energy efficiency (kbit/J)", 1e-3)]
    fig, axes = plt.subplots(1, 4, figsize=(13, 3.6), sharey=True)
    for ax, (m, t, s) in zip(axes, metrics):
        vals = d[m].values * s
        colors = ["#b9b8b3"] + ["#2a78d6"] * (len(keys) - 1)
        ax.barh(range(len(keys)), vals, color=colors, height=0.62)
        for i, v in enumerate(vals):
            ax.text(v, i, f" {v:.1f}" if v < 100 else f" {v:.0f}", va="center", fontsize=8.5, color=INK)
        ax.set_title(t, fontsize=10.5)
        ax.grid(axis="y", visible=False)
        ax.set_xlim(0, vals.max() * 1.22)
    axes[0].set_yticks(range(len(keys)), labels)
    axes[0].invert_yaxis()
    fig.suptitle(f"Ablation: what each PULSE component adds (load = {load}×)", x=0.01, ha="left",
                 fontweight="bold", color=INK)
    fig.tight_layout(w_pad=3)
    fig.savefig(os.path.join(OUT, fname), dpi=160)
    plt.close(fig)


def energy_delay(path):
    if not os.path.exists(path):
        return
    df = pd.read_csv(path)
    fig, ax = plt.subplots(figsize=(6.4, 4))
    for load, col in ((0.3, "#2a78d6"), (0.6, "#eb6834")):
        d = df[df.load == load].sort_values("rt_hold_frac")
        ax.plot(d.voip_delay_ms, d.avg_power_w, color=col, lw=2, marker="o", ms=7,
                markeredgecolor=SURF, markeredgewidth=1.5, label=f"Load {load}×")
        for _, r in d.iterrows():
            ax.annotate(f"{int(r.rt_hold_frac*100)}%", (r.voip_delay_ms, r.avg_power_w),
                        textcoords="offset points", xytext=(6, 4), fontsize=8, color=INK2)
    ax.axvline(100, color="#e34948", lw=1, ls="--")
    ax.text(99, ax.get_ylim()[1], "VoIP budget 100 ms ", ha="right", va="top", fontsize=8, color=INK2)
    ax.set_title("Energy-delay knob of slack-aware DTX")
    ax.set_xlabel("Mean VoIP delay (ms)")
    ax.set_ylabel("Avg power per cell (W)")
    ax.text(0, -0.22, "Labels = share of each packet's delay budget ECO may spend waiting (0% = plain DTX).",
            transform=ax.transAxes, fontsize=8.5, color=INK2)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig7_energy_delay_tradeoff.png"), dpi=160)
    plt.close(fig)


def cqi_delay(path):
    if not os.path.exists(path):
        return
    df = pd.read_csv(path)
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    for key, col, lab in (("pf", "#eb6834", "Prop. Fair (reported CQI)"),
                          ("pf_ica_olla", "#2a78d6", "Prop. Fair + ICA + OLLA")):
        d = df[df.key == key].sort_values("cqi_delay")
        axes[0].plot(d.cqi_delay, d.bler * 100, color=col, lw=2, marker="o", ms=7,
                     markeredgecolor=SURF, markeredgewidth=1.5, label=lab)
        axes[1].plot(d.cqi_delay, d.cell_tput_mbps, color=col, lw=2, marker="o", ms=7,
                     markeredgecolor=SURF, markeredgewidth=1.5, label=lab)
    axes[0].set_title("BLER vs CQI feedback delay")
    axes[0].set_ylabel("BLER (%)")
    axes[1].set_title("Cell throughput vs CQI feedback delay")
    axes[1].set_ylabel("Mbps per cell")
    for ax in axes:
        ax.set_xlabel("CQI feedback delay (ms)")
        ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig8_cqi_delay_sensitivity.png"), dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    df = pd.read_csv(os.path.join(OUT, "summary.csv"))
    sweep(df, "qos_satisfied_pct", "Real-time users meeting QoS", "Users meeting PLR target (%)",
          "fig1_qos_satisfaction.png", note="Target: VoIP loss ≤ 1%, video loss ≤ 2% (per user).")
    sweep(df, "bler", "Block error rate", "BLER (%)", "fig2_bler.png", scale=100)
    sweep(df, "avg_power_w", "Base-station power consumption", "Avg power per cell (W)",
          "fig3_power.png", note="EARTH power model: 130 W idle, 75 W in DTX micro-sleep, +4.7×RF power.")
    sweep(df, "video_plr", "Video packet loss (deadline 300 ms)", "Packet loss (%)",
          "fig4_video_plr.png", scale=100)
    sweep(df, "cell_tput_mbps", "Cell throughput", "Mbps per cell (5 MHz)", "fig5_throughput.png")
    sweep(df, "bits_per_joule", "Energy efficiency", "kbit per joule", "fig6_energy_efficiency.png", scale=1e-3)
    ablation(df, 0.6, "fig9_ablation_load0.6.png")
    ablation(df, 1.2, "fig10_ablation_load1.2.png")
    energy_delay(os.path.join(OUT, "sens_energy_delay.csv"))
    cqi_delay(os.path.join(OUT, "sens_cqi_delay.csv"))
    print("Figures written to results/")
