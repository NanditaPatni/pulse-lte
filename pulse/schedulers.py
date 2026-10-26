"""Downlink packet schedulers.

Each scheduler fills the PRBs of one cell for one TTI. Allocation is greedy per PRB: the PRB goes
to the user with the highest metric, and that user's expected backlog is reduced so a nearly empty
queue does not soak up PRBs it cannot fill.

Baselines : Round Robin, Max C/I, Proportional Fair, M-LWDF
Proposed  : PULSE (Priority-Urgency-Load-aware Scheduler with Energy saving)
"""
import numpy as np

VOIP, VIDEO, BE = 0, 1, 2


def allocate(metric_fn, users, est_rate, backlog, n_rb):
    """Generic greedy allocator. metric_fn(rb, active_mask) -> metric for each user."""
    alloc = -np.ones(n_rb, dtype=int)
    remaining = backlog.astype(float).copy()
    for rb in range(n_rb):
        active = remaining > 0
        if not active.any():
            break
        m = metric_fn(rb)
        m = np.where(active & (est_rate[:, rb] > 0), m, -np.inf)
        k = int(np.argmax(m))
        if not np.isfinite(m[k]):
            continue
        alloc[rb] = users[k]
        remaining[k] -= est_rate[k, rb]
    return alloc


def schedule(cfg, ctx, users, est_rate):
    """Return the PRB allocation (global user index per PRB, -1 = unused) for one cell."""
    n_rb = cfg.n_rb
    backlog = ctx["buffer"][users]
    if backlog.sum() == 0:
        return -np.ones(n_rb, dtype=int)

    rbar = np.maximum(ctx["rbar"][users], 1.0)
    hol = ctx["hol"][users].astype(float)
    cls = ctx["cls"][users]
    deadline = ctx["deadline"][users].astype(float)
    s = cfg.scheduler

    if s == "rr":
        last = ctx["last_served"][users].astype(float).copy()
        alloc = -np.ones(n_rb, dtype=int)
        remaining = backlog.astype(float).copy()
        for rb in range(n_rb):
            m = np.where((remaining > 0) & (est_rate[:, rb] > 0), -last, -np.inf)
            k = int(np.argmax(m))
            if not np.isfinite(m[k]):
                continue
            alloc[rb] = users[k]
            remaining[k] -= est_rate[k, rb]
            last[k] = ctx["t"] + rb * 1e-3   # move to the back of the queue
        return alloc

    if s == "maxci":
        return allocate(lambda rb: est_rate[:, rb], users, est_rate, backlog, n_rb)

    if s == "pf":
        return allocate(lambda rb: est_rate[:, rb] / rbar, users, est_rate, backlog, n_rb)

    if s == "mlwdf":
        a = np.where(cls == BE, 0.0, -np.log(0.05) / deadline)
        w = np.where(cls == BE, 1.0, a * np.maximum(hol, 1.0))
        return allocate(lambda rb: w * est_rate[:, rb] / rbar, users, est_rate, backlog, n_rb)

    if s == "pulse":
        return _pulse(cfg, ctx, users, est_rate, backlog, rbar, hol, cls, deadline)

    raise ValueError(f"unknown scheduler {s}")


def _pulse(cfg, ctx, users, est_rate, backlog, rbar, hol, cls, deadline):
    n_rb = cfg.n_rb
    # 1) Priority + urgency weight: exponential in the share of the delay budget already used,
    #    so a packet near its deadline outranks channel quality. BE stays plain PF.
    class_w = np.array([2.0, 1.5, 1.0])[cls]
    slack_used = np.maximum(hol / deadline - cfg.urgency_theta, 0.0)
    urgency = np.where(cls == BE, 1.0, np.exp(np.minimum(cfg.urgency_k * slack_used, 6.0)))
    w = class_w * urgency

    # 2) QoS-slack-aware cell DTX (ECO): every packet has a delay budget; most of it is unused
    #    at low load. Hold traffic while all packets have slack, then serve everyone in one burst,
    #    so the cell can micro-sleep in the TTIs in between. Wake when any real-time packet has used
    #    rt_hold_frac of its budget, a BE packet waited batch_window ms, or the backlog fills
    #    batch_fill of a TTI. High load keeps the cell awake, so this only costs delay when idle.
    if cfg.energy and cfg.eco_batching:
        has = backlog > 0
        rt = has & (cls != BE)
        be = has & (cls == BE)
        urgent = (rt & (hol >= cfg.rt_hold_frac * deadline)).any() or \
                 (be & (hol >= cfg.batch_window)).any()
        cap = est_rate.mean(axis=0).sum()               # rough bits one full TTI can carry
        if not urgent and backlog.sum() < cfg.batch_fill * cap:
            return -np.ones(n_rb, dtype=int)            # cell sleeps (DTX) this TTI

    # 3) SFR-aware frequency preference: edge users favour the cell's boosted sub-band,
    #    centre users favour the rest, so the boosted power is spent where it is needed.
    if cfg.sfr:
        edge_rb = ctx["edge_rb_mask"]                  # (n_rb,) bool for this cell
        is_edge = ctx["edge"][users]
        pref = np.where(is_edge[:, None],
                        np.where(edge_rb[None, :], 1.6, 0.6),
                        np.where(edge_rb[None, :], 0.6, 1.0))
    else:
        pref = np.ones((len(users), n_rb))

    return allocate(lambda rb: w * pref[:, rb] * est_rate[:, rb] / rbar,
                    users, est_rate, backlog, n_rb)
