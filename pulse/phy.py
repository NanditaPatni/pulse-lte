"""PHY abstraction: SINR -> CQI -> spectral efficiency, and BLER model (3GPP TS 36.213 CQI table)."""
import numpy as np

# SINR (dB) at which each CQI 1..15 reaches ~10% BLER (AWGN, link-level curves)
CQI_SINR_DB = np.array([-6.7, -4.7, -2.3, 0.2, 2.4, 4.3, 5.9, 8.1,
                        10.3, 11.7, 14.1, 16.3, 18.7, 21.0, 22.7])
# Spectral efficiency (bits/RE) for CQI 0..15 (CQI 0 = out of range)
CQI_EFF = np.array([0.0, 0.1523, 0.2344, 0.3770, 0.6016, 0.8770, 1.1758, 1.4766,
                    1.9141, 2.4063, 2.7305, 3.3223, 3.9023, 4.5234, 5.1152, 5.5547])
CQI_MOD = ["-"] + ["QPSK"] * 6 + ["16QAM"] * 3 + ["64QAM"] * 6


def sinr_to_cqi(sinr_db):
    """Highest CQI whose 10%-BLER threshold is below the given SINR (0 = no transmission)."""
    return np.searchsorted(CQI_SINR_DB, sinr_db, side="right")


def cqi_to_eff(cqi):
    return CQI_EFF[np.clip(cqi, 0, 15)]


def bler(sinr_eff_db, cqi):
    """Logistic BLER curve: 10% at the CQI threshold, ~1.5 dB per decade slope."""
    thr = CQI_SINR_DB[np.clip(cqi, 1, 15) - 1]
    return 1.0 / (1.0 + np.exp(1.5 * (sinr_eff_db - thr) + 2.197))
