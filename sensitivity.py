"""Two sensitivity studies.

1. Energy-delay knob: sweep rt_hold_frac (how much of the delay budget ECO may spend waiting).
2. CQI feedback delay: same PF scheduler, with and without PULSE's ICA + OLLA link adaptation.

Usage: python sensitivity.py   ->  results/sens_energy_delay.csv, results/sens_cqi_delay.csv
"""
import os
from multiprocessing import Pool

import pandas as pd

from pulse import SimConfig, LTESimulator

FULL = dict(scheduler="pulse", ica=True, olla=True, sfr=True, energy=True)
TTI, SEEDS = 2500, (1, 2)


def _energy(a):
    frac, load, seed = a
    kw = dict(FULL, rt_hold_frac=frac, batch_window=max(int(frac * 300), 5), eco_batching=frac > 0)
    m = LTESimulator(SimConfig(n_tti=TTI, load_scale=load, seed=seed, **kw)).run()
    m["rt_hold_frac"] = frac
    return m


def _cqi(a):
    key, delay, seed = a
    kw = {"pf": dict(scheduler="pf"),
          "pf_ica_olla": dict(scheduler="pf", ica=True, olla=True)}[key]
    m = LTESimulator(SimConfig(n_tti=TTI, load_scale=0.9, seed=seed, cqi_delay_tti=delay, **kw)).run()
    m["key"], m["cqi_delay"] = key, delay
    return m


if __name__ == "__main__":
    import sys
    only_cqi = "--cqi-only" in sys.argv
    os.makedirs("results", exist_ok=True)
    with Pool() as p:
        e = [] if only_cqi else p.map(_energy, [(f, l, s) for f in (0, 0.05, 0.1, 0.15, 0.25, 0.4)
                            for l in (0.3, 0.6) for s in SEEDS], chunksize=1)
        c = p.map(_cqi, [(k, d, s) for k in ("pf", "pf_ica_olla")
                         for d in (1, 2, 4, 6, 8, 10) for s in SEEDS], chunksize=1)
    if e:
        pd.DataFrame(e).groupby(["rt_hold_frac", "load"]).mean(numeric_only=True).reset_index() \
            .to_csv("results/sens_energy_delay.csv", index=False)
    pd.DataFrame(c).groupby(["key", "cqi_delay"]).mean(numeric_only=True).reset_index() \
        .to_csv("results/sens_cqi_delay.csv", index=False)
    print("Saved sensitivity results")
