"""Simulation configuration for PULSE-LTE."""
from dataclasses import dataclass, field


@dataclass
class SimConfig:
    # --- Deployment ---
    n_cells: int = 7              # 7-cell hexagonal cluster (1 centre + 6 ring)
    isd_m: float = 500.0          # inter-site distance (3GPP urban macro)
    users_per_cell: int = 15
    min_dist_m: float = 35.0

    # --- Radio ---
    n_rb: int = 25                # 5 MHz LTE carrier -> 25 PRBs
    rb_bw_hz: float = 180e3
    carrier_hz: float = 2.0e9
    tx_power_dbm: float = 43.0    # total eNB power (20 W)
    noise_figure_db: float = 9.0
    shadow_std_db: float = 8.0
    speed_kmh: float = 30.0
    subband_size: int = 5         # PRBs per CQI subband
    cqi_delay_tti: int = 4        # feedback delay (ms)
    harq_rtt: int = 8             # ms before a NACKed block can be retransmitted
    re_bits_per_rb: int = 120     # data REs per PRB per TTI after control/RS overhead

    # --- Time ---
    n_tti: int = 3000             # 1 TTI = 1 ms
    pf_tc: float = 100.0          # PF averaging window (TTIs)

    # --- Traffic ---
    mix: dict = field(default_factory=lambda: {"voip": 0.3, "video": 0.3, "be": 0.4})
    load_scale: float = 1.0       # multiplies video + best-effort offered load
    voip_bits: int = 328          # AMR 12.2 + headers every 20 ms
    voip_period: int = 20
    voip_deadline: int = 100      # ms (QCI 1)
    video_rate_bps: float = 450e3
    video_period: int = 40        # 25 fps
    video_deadline: int = 300     # ms (QCI 2)
    be_rate_bps: float = 250e3    # mean offered rate per BE user
    be_file_bits: float = 80e3

    # --- Features (proposed system toggles) ---
    scheduler: str = "pf"         # rr | maxci | pf | mlwdf | pulse
    olla: bool = False            # self-tuning outer-loop link adaptation
    ica: bool = False             # interference-coordinated link adaptation (C-RAN view)
    sfr: bool = False             # load-adaptive soft frequency reuse
    energy: bool = False          # cell DTX + best-effort batching

    # --- Proposed-scheme parameters ---
    urgency_k: float = 4.0        # steepness of deadline urgency
    urgency_theta: float = 0.0    # share of delay budget before urgency starts
    olla_target_bler: float = 0.10
    olla_step_down: float = 0.5
    sfr_max_ratio: float = 6.0    # max edge/centre power ratio
    sfr_update_tti: int = 100
    edge_geom_db: float = 3.0     # users below this geometry are "edge"
    eco_batching: bool = True     # False = plain DTX (sleep only when naturally idle)
    rt_hold_frac: float = 0.15    # real-time packets may wait this share of their budget
    batch_window: int = 40        # max ms a BE packet waits for batching
    batch_fill: float = 0.5       # transmit BE once backlog fills this share of a TTI

    # --- Energy model (EARTH, single TRX macro) ---
    p0_w: float = 130.0
    delta_p: float = 4.7
    pmax_w: float = 20.0
    psleep_w: float = 75.0

    seed: int = 1

    @property
    def label(self) -> str:
        if self.scheduler != "pulse":
            return {"rr": "Round Robin", "maxci": "Max C/I", "pf": "Prop. Fair",
                    "mlwdf": "M-LWDF"}[self.scheduler]
        parts = ["PULSE"]
        if self.ica:
            parts.append("ICA")
        if self.olla:
            parts.append("OLLA")
        if self.sfr:
            parts.append("SFR")
        if self.energy:
            parts.append("ECO" if self.eco_batching else "DTX")
        return "+".join(parts)
