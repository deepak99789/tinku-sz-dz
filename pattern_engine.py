"""
pattern_engine.py

Python port of the Pine Script "Demand & Supply Dashboard" indicator.

This module re-implements, bar-for-bar, the same rules used in the original
TradingView Pine Script:

    - RBD (Rally-Base-Drop)  -> Supply zone
    - DBD (Drop-Base-Drop)   -> Supply zone
    - DBR (Drop-Base-Rally)  -> Demand zone
    - RBR (Rally-Base-Rally) -> Demand zone

Each pattern is detected in 4 variants, exactly mirroring the Pine logic:
    - std     : 1 base candle  (base = candle 1 bar back)
    - ext     : 1 base candle  (base = candle 2 bars back, leg-out can span 2 candles)
    - 2base   : 2 base candles (base = candles 1 & 2 bars back)
    - 3base   : 3 base candles (base = candles 1, 2 & 3 bars back)

A "base_count_filter" lets you restrict detection to only 1, 2, 3 base-candle
patterns, or "All" of them - same as the Pine Script dropdown input.

Zone lifecycle (pre-alert -> entry -> SL / Target) is tracked bar by bar,
just like the Pine `active_boxes` / `zone_*` arrays.
"""

from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np
import pandas as pd


# --------------------------------------------------------------------------
# ATR (Wilder's smoothing) - used for the zone buffer & the "upcoming alert"
# distance. This mirrors Pine's ta.atr().
# --------------------------------------------------------------------------
def wilder_atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    return atr


@dataclass
class Zone:
    start_bar: int
    end_bar: int
    proximal: float
    distal: float
    target: float
    is_supply: bool
    pattern_name: str
    base_count: int = 1
    legout_count: int = 1
    trigger_bar: int = -1
    status: str = "active"
    activated: bool = False
    pre_alerted: bool = False


@dataclass
class DetectionResult:
    df: pd.DataFrame
    all_zones: List[Zone]
    sl_count: int
    tp_count: int
    events: List[dict] = field(default_factory=list)


def _bool(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(bool)


def detect_patterns(
    df: pd.DataFrame,
    base_count_filter: str = "All",
) -> pd.DataFrame:
    """
    Vectorised, per-bar pattern detection.
    Adds boolean/aux columns to a copy of df and returns it.
    base_count_filter: "1", "2", "3" or "All"
    """
    d = df.copy()
    o, c, h, l = d["Open"], d["Close"], d["High"], d["Low"]

    p1_o, p1_c = o.shift(1), c.shift(1)
    p2_o, p2_c = o.shift(2), c.shift(2)
    p3_o, p3_c = o.shift(3), c.shift(3)
    p4_o, p4_c = o.shift(4), c.shift(4)

    h1, h2, h3 = h.shift(1), h.shift(2), h.shift(3)
    l1, l2, l3 = l.shift(1), l.shift(2), l.shift(3)

    t_c = h - l
    t_p1 = h1 - l1
    t_p2 = h2 - l2
    t_p3 = h3 - l3
    t_p4 = h.shift(4) - l.shift(4)

    is_p4_green, is_p4_red = p4_c > p4_o, p4_c < p4_o
    is_p3_green, is_p3_red = p3_c > p3_o, p3_c < p3_o
    is_p2_green, is_p2_red = p2_c > p2_o, p2_c < p2_o
    is_p1_green, is_p1_red = p1_c > p1_o, p1_c < p1_o
    is_c_green, is_c_red = c > o, c < o

    l_in_norm = (p2_c - p2_o).abs() >= t_p2 * 0.6
    l_out_norm = (c - o).abs() >= t_c * 0.6
    l_in_ext = (p3_c - p3_o).abs() >= t_p3 * 0.6
    l_out_ext = ((p1_c - p1_o).abs() >= t_p1 * 0.6) & ((c - o).abs() >= t_c * 0.6)
    l_in_3 = (p4_c - p4_o).abs() >= t_p4 * 0.6

    allow_1 = base_count_filter in ("All", "1")
    allow_2 = base_count_filter in ("All", "2")
    allow_3 = base_count_filter in ("All", "3")

    def build(direction_leg_in_green, direction_leg_out_green, allow1, allow2, allow3):
        legin1 = is_p2_green if direction_leg_in_green else is_p2_red
        legin_ext = is_p3_green if direction_leg_in_green else is_p3_red
        legin_3 = is_p4_green if direction_leg_in_green else is_p4_red
        legout = is_c_green if direction_leg_out_green else is_c_red
        p1_cont = is_p1_green if direction_leg_out_green else is_p1_red

        std_cond = legin1 & legout & l_in_norm & l_out_norm & (t_p1 <= t_p2 * 0.6) & (t_p2 >= t_p1 * 1.7)
        std = std_cond & ((t_c >= t_p2 * 1.7) | (p1_cont & (t_p1 + t_c >= t_p2 * 1.7))) & allow1

        ext_cond = legin_ext & legout & l_in_ext & l_out_ext & (t_p2 <= t_p3 * 0.6) & (t_p3 >= t_p2 * 1.7)
        ext = ext_cond & ((t_p1 >= t_p3 * 1.7) | (p1_cont & (t_p1 + t_c >= t_p3 * 1.7))) & allow1

        base2_cond = (
            legin_ext & legout & l_in_ext & l_out_norm
            & (t_p2 <= t_p3 * 0.6) & (t_p1 <= t_p3 * 0.6)
            & (t_p3 >= t_p2 * 1.7) & (t_p3 >= t_p1 * 1.7)
        )
        base2 = base2_cond & ((t_c >= t_p3 * 1.7) | (p1_cont & (t_p1 + t_c >= t_p3 * 1.7))) & allow2

        base3_cond = (
            legin_3 & legout & l_in_3 & l_out_norm
            & (t_p3 <= t_p4 * 0.6) & (t_p2 <= t_p4 * 0.6) & (t_p1 <= t_p4 * 0.6)
            & (t_p4 >= t_p3 * 1.7) & (t_p4 >= t_p2 * 1.7) & (t_p4 >= t_p1 * 1.7)
        )
        base3 = base3_cond & ((t_c >= t_p4 * 1.7) | (p1_cont & (t_p1 + t_c >= t_p4 * 1.7))) & allow3

        return _bool(std), _bool(ext), _bool(base2), _bool(base3)

    rbd_std, rbd_ext, rbd_2b, rbd_3b = build(True, False, allow_1, allow_2, allow_3)
    dbd_std, dbd_ext, dbd_2b, dbd_3b = build(False, False, allow_1, allow_2, allow_3)
    dbr_std, dbr_ext, dbr_2b, dbr_3b = build(False, True, allow_1, allow_2, allow_3)
    rbr_std, rbr_ext, rbr_2b, rbr_3b = build(True, True, allow_1, allow_2, allow_3)

    def combine_supply(std, ext, b2, b3):
        base_high = np.where(
            b3, np.maximum(np.maximum(h3, h2), h1),
            np.where(b2, np.maximum(h2, h1), np.where(std, h1, h2)),
        )
        w_ok = h <= base_high
        is_pat = (std | ext | b2 | b3) & w_ok
        return _bool(pd.Series(is_pat, index=d.index))

    def combine_demand(std, ext, b2, b3):
        base_low = np.where(
            b3, np.minimum(np.minimum(l3, l2), l1),
            np.where(b2, np.minimum(l2, l1), np.where(std, l1, l2)),
        )
        w_ok = l >= base_low
        is_pat = (std | ext | b2 | b3) & w_ok
        return _bool(pd.Series(is_pat, index=d.index))

    d["is_RBD"] = combine_supply(rbd_std, rbd_ext, rbd_2b, rbd_3b)
    d["is_DBD"] = combine_supply(dbd_std, dbd_ext, dbd_2b, dbd_3b)
    d["is_DBR"] = combine_demand(dbr_std, dbr_ext, dbr_2b, dbr_3b)
    d["is_RBR"] = combine_demand(rbr_std, rbr_ext, rbr_2b, rbr_3b)

    d["rbd_2base"], d["rbd_3base"], d["rbd_ext"] = rbd_2b, rbd_3b, rbd_ext
    d["dbd_2base"], d["dbd_3base"], d["dbd_ext"] = dbd_2b, dbd_3b, dbd_ext
    d["dbr_2base"], d["dbr_3base"], d["dbr_ext"] = dbr_2b, dbr_3b, dbr_ext
    d["rbr_2base"], d["rbr_3base"], d["rbr_ext"] = rbr_2b, rbr_3b, rbr_ext

    for n, s in [("o1", p1_o), ("c1", p1_c), ("o2", p2_o), ("c2", p2_c),
                 ("o3", p3_o), ("c3", p3_c), ("h1", h1), ("h2", h2), ("h3", h3),
                 ("l1", l1), ("l2", l2), ("l3", l3)]:
        d[n] = s

    return d


def _zone_from_supply_row(d: pd.DataFrame, i: int, atr_buffer: float) -> Zone:
    is3 = bool(d["rbd_3base"].iloc[i] or d["dbd_3base"].iloc[i])
    is2 = bool(d["rbd_2base"].iloc[i] or d["dbd_2base"].iloc[i])
    isExt = bool(d["rbd_ext"].iloc[i] or d["dbd_ext"].iloc[i])
    is_rbd = bool(d["is_RBD"].iloc[i])

    o1, c1 = d["o1"].iloc[i], d["c1"].iloc[i]
    o2, c2 = d["o2"].iloc[i], d["c2"].iloc[i]
    o3, c3 = d["o3"].iloc[i], d["c3"].iloc[i]
    h1, h2, h3 = d["h1"].iloc[i], d["h2"].iloc[i], d["h3"].iloc[i]

    if is3:
        proximal = min(min(o3, c3), min(o2, c2), min(o1, c1))
        distal = max(h3, h2, h1) + atr_buffer
        base_idx = 3
        tag = " 3C"
    elif is2:
        proximal = min(min(o2, c2), min(o1, c1))
        distal = max(h2, h1) + atr_buffer
        base_idx = 2
        tag = " 2C"
    else:
        base_idx = 2 if isExt else 1
        o_b, c_b = (o2, c2) if isExt else (o1, c1)
        h_b = h2 if isExt else h1
        proximal = min(o_b, c_b)
        distal = h_b + atr_buffer
        tag = ""

    risk = distal - proximal
    target = proximal - risk * 3.0
    name = ("RBD" if is_rbd else "DBD") + tag
    base_count = 3 if is3 else (2 if is2 else 1)
    legout_count = 2 if (isExt and not is3 and not is2) else 1
    return Zone(
        start_bar=i - base_idx,
        end_bar=i,
        proximal=proximal,
        distal=distal,
        target=target,
        is_supply=True,
        pattern_name=name,
        base_count=base_count,
        legout_count=legout_count,
    )


def _zone_from_demand_row(d: pd.DataFrame, i: int, atr_buffer: float) -> Zone:
    is3 = bool(d["dbr_3base"].iloc[i] or d["rbr_3base"].iloc[i])
    is2 = bool(d["dbr_2base"].iloc[i] or d["rbr_2base"].iloc[i])
    isExt = bool(d["dbr_ext"].iloc[i] or d["rbr_ext"].iloc[i])
    is_dbr = bool(d["is_DBR"].iloc[i])

    o1, c1 = d["o1"].iloc[i], d["c1"].iloc[i]
    o2, c2 = d["o2"].iloc[i], d["c2"].iloc[i]
    o3, c3 = d["o3"].iloc[i], d["c3"].iloc[i]
    l1, l2, l3 = d["l1"].iloc[i], d["l2"].iloc[i], d["l3"].iloc[i]

    if is3:
        proximal = max(max(o3, c3), max(o2, c2), max(o1, c1))
        distal = min(l3, l2, l1) - atr_buffer
        base_idx = 3
        tag = " 3C"
    elif is2:
        proximal = max(max(o2, c2), max(o1, c1))
        distal = min(l2, l1) - atr_buffer
        base_idx = 2
        tag = " 2C"
    else:
        base_idx = 2 if isExt else 1
        o_b, c_b = (o2, c2) if isExt else (o1, c1)
        l_b = l2 if isExt else l1
        proximal = max(o_b, c_b)
        distal = l_b - atr_buffer
        tag = ""

    risk = proximal - distal
    target = proximal + risk * 3.0
    name = ("DBR" if is_dbr else "RBR") + tag
    base_count = 3 if is3 else (2 if is2 else 1)
    legout_count = 2 if (isExt and not is3 and not is2) else 1
    return Zone(
        start_bar=i - base_idx,
        end_bar=i,
        proximal=proximal,
        distal=distal,
        target=target,
        is_supply=False,
        pattern_name=name,
        base_count=base_count,
        legout_count=legout_count,
    )


def track_zones(
    d: pd.DataFrame,
    atr_series: pd.Series,
    atr_multiplier: float,
    rr_target: float,
    pre_entry_mult: float,
) -> DetectionResult:
    n = len(d)
    active: List[Zone] = []
    all_zones: List[Zone] = []
    sl_count = 0
    tp_count = 0
    events = []

    highs = d["High"].values
    lows = d["Low"].values

    # 🔥 STRONG DUPLICATE DETECTION - 0.5 tolerance
    seen_zones = {}  # key -> (proximal, distal)

    for i in range(n):
        atr_buffer = atr_series.iloc[i] * atr_multiplier if not np.isnan(atr_series.iloc[i]) else 0.0
        pre_dist = atr_series.iloc[i] * pre_entry_mult if not np.isnan(atr_series.iloc[i]) else 0.0

        # 1) new zone creation
        if d["is_RBD"].iloc[i] or d["is_DBD"].iloc[i]:
            z = _zone_from_supply_row(d, i, atr_buffer)
            
            # 🔥 Check duplicate with 0.5 tolerance
            is_dup = False
            for key, (p, d_val) in seen_zones.items():
                if abs(p - z.proximal) < 0.5 and abs(d_val - z.distal) < 0.5:
                    is_dup = True
                    break
            
            if is_dup:
                continue
                
            seen_zones[f"{z.pattern_name}|{round(z.proximal, 2)}"] = (z.proximal, z.distal)
            
            risk = z.distal - z.proximal
            z.target = z.proximal - risk * rr_target
            z.trigger_bar = i
            active.append(z)
            all_zones.append(z)
            events.append({"bar": i, "type": "zone_found", "zone": z})

        if d["is_DBR"].iloc[i] or d["is_RBR"].iloc[i]:
            z = _zone_from_demand_row(d, i, atr_buffer)
            
            # 🔥 Check duplicate with 0.5 tolerance
            is_dup = False
            for key, (p, d_val) in seen_zones.items():
                if abs(p - z.proximal) < 0.5 and abs(d_val - z.distal) < 0.5:
                    is_dup = True
                    break
            
            if is_dup:
                continue
                
            seen_zones[f"{z.pattern_name}|{round(z.proximal, 2)}"] = (z.proximal, z.distal)
            
            risk = z.proximal - z.distal
            z.target = z.proximal + risk * rr_target
            z.trigger_bar = i
            active.append(z)
            all_zones.append(z)
            events.append({"bar": i, "type": "zone_found", "zone": z})

        # 2) update every currently active zone
        still_active = []
        for z in active:
            if i <= z.trigger_bar:
                still_active.append(z)
                continue

            hi, lo = highs[i], lows[i]
            pre_hit = sl_hit = target_hit = entered = False

            if not z.activated and not z.pre_alerted:
                if z.is_supply and (z.proximal - pre_dist) <= hi <= z.proximal:
                    pre_hit = True
                elif (not z.is_supply) and (z.proximal <= lo <= z.proximal + pre_dist):
                    pre_hit = True

            if not z.activated:
                if z.is_supply and hi > z.proximal and lo <= z.proximal:
                    entered = True
                elif (not z.is_supply) and lo < z.proximal and hi >= z.proximal:
                    entered = True

            if z.activated or entered:
                if z.is_supply:
                    if hi > z.distal:
                        sl_hit = True
                    elif lo <= z.target:
                        target_hit = True
                else:
                    if lo < z.distal:
                        sl_hit = True
                    elif hi >= z.target:
                        target_hit = True

            if pre_hit:
                z.pre_alerted = True
                events.append({"bar": i, "type": "pre_alert", "zone": z})

            if entered:
                z.activated = True
                events.append({"bar": i, "type": "entered", "zone": z})

            if sl_hit:
                sl_count += 1
                z.status = "sl"
                z.end_bar = i
                events.append({"bar": i, "type": "sl_hit", "zone": z})
                continue
            elif target_hit:
                tp_count += 1
                z.status = "tp"
                z.end_bar = i
                events.append({"bar": i, "type": "tp_hit", "zone": z})
                continue
            else:
                z.end_bar = i
                still_active.append(z)

        active = still_active

    return DetectionResult(df=d, all_zones=all_zones, sl_count=sl_count, tp_count=tp_count, events=events)


def run_full_pipeline(
    df: pd.DataFrame,
    atr_length: int = 14,
    atr_multiplier: float = 0.35,
    rr_target: float = 3.0,
    pre_entry_mult: float = 1.5,
    base_count_filter: str = "All",
) -> DetectionResult:
    d = detect_patterns(df, base_count_filter=base_count_filter)
    atr_series = wilder_atr(df, atr_length)
    result = track_zones(d, atr_series, atr_multiplier, rr_target, pre_entry_mult)
    return result
