"""
pattern_engine.py

Python port of the Pine Script "Demand & Supply Dashboard" indicator.

This module re-implements, bar-for-bar, the same rules used in the original
TradingView Pine Script:

    - RBD (Rally-Base-Drop)  -> Supply zone
    - DBD (Drop-Base-Drop)   -> Supply zone
    - DBR (Drop-Base-Rally)  -> Demand zone
    - RBR (Rally-Base-Rally) -> Demand zone
    - BIG BASE (Supply/Demand) -> New pattern added

🔥 MODIFIED: Only 1 base candle allowed for ALL patterns (std only)
🔥 BIG BASE: NO ATR buffer (uses leg-in high/low directly)
🔥 BIG BASE: Big Base candle STRICTLY INSIDE leg-in candle
"""

from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np
import pandas as pd


# --------------------------------------------------------------------------
# ATR (Wilder's smoothing)
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
    
    🔥 MODIFIED: Only std (1 base candle) patterns are detected.
    2base, 3base, and ext variants are REMOVED.
    
    🔥 BIG BASE: Big Base candle STRICTLY INSIDE leg-in candle
    """
    d = df.copy()
    o, c, h, l = d["Open"], d["Close"], d["High"], d["Low"]

    # For BIG BASE: we need p1, p2, p3 (3 bars back)
    p1_o, p1_c = o.shift(1), c.shift(1)  # 1 bar back - leg-out
    p2_o, p2_c = o.shift(2), c.shift(2)  # 2 bars back - big base
    p3_o, p3_c = o.shift(3), c.shift(3)  # 3 bars back - leg-in

    h1, h2, h3 = h.shift(1), h.shift(2), h.shift(3)
    l1, l2, l3 = l.shift(1), l.shift(2), l.shift(3)

    t_c = h - l
    t_p1 = h1 - l1
    t_p2 = h2 - l2
    t_p3 = h3 - l3

    is_p3_green, is_p3_red = p3_c > p3_o, p3_c < p3_o
    is_p2_green, is_p2_red = p2_c > p2_o, p2_c < p2_o
    is_p1_green, is_p1_red = p1_c > p1_o, p1_c < p1_o
    is_c_green, is_c_red = c > o, c < o

    l_in_norm = (p2_c - p2_o).abs() >= t_p2 * 0.6
    l_out_norm = (c - o).abs() >= t_c * 0.6

    # ============================================================
    # 🔥 BIG BASE PATTERN DETECTION
    # FIXED: Big Base candle STRICTLY INSIDE leg-in candle
    # ============================================================
    # Type 1: Supply (RBD style)
    #   - Candle 1 (leg-in): p3 (3 bars back) - GREEN, body ≥ 65% of range
    #   - Candle 2 (big base): p2 (2 bars back) - RED, body ≥ 65% of range
    #     Open/Close STRICTLY INSIDE p3's range (>, < not >=, <=)
    #   - Candle 3 (leg-out): p1 (1 bar back) - RED (any body)
    # ============================================================
    body_p3 = (p3_c - p3_o).abs()  # leg-in body
    body_p2 = (p2_c - p2_o).abs()  # big base body
    body_p1 = (p1_c - p1_o).abs()  # leg-out body

    # 🔥 BIG SUPPLY
    # Leg-in: GREEN, body >= 65% of range
    legin_green_big = is_p3_green & (body_p3 >= t_p3 * 0.65)
    # Big Base: RED, body >= 65% of range, and STRICTLY INSIDE Candle 1's (p3) range
    big_base_red = is_p2_red & (body_p2 >= t_p2 * 0.65) & (p2_o > l3) & (p2_o < h3) & (p2_c > l3) & (p2_c < h3)
    # Leg-out: RED (any body)
    legout_red_any = is_p1_red
    
    # 🔥 BIG DEMAND
    # Leg-in: RED, body >= 65% of range
    legin_red_big = is_p3_red & (body_p3 >= t_p3 * 0.65)
    # Big Base: GREEN, body >= 65% of range, and STRICTLY INSIDE Candle 1's (p3) range
    big_base_green = is_p2_green & (body_p2 >= t_p2 * 0.65) & (p2_o > l3) & (p2_o < h3) & (p2_c > l3) & (p2_c < h3)
    # Leg-out: GREEN (any body)
    legout_green_any = is_p1_green

    # Detect on current bar (pattern completed at p1)
    is_big_supply = _bool(legin_green_big & big_base_red & legout_red_any)
    is_big_demand = _bool(legin_red_big & big_base_green & legout_green_any)

    # ============================================================
    # 🔥 STANDARD PATTERNS (Only 1 base candle - std)
    # ============================================================
    # RBD: Green leg-in (p2), Red leg-out (current)
    rbd_std = is_p2_green & is_c_red & l_in_norm & l_out_norm & (t_p1 <= t_p2 * 0.6) & (t_p2 >= t_p1 * 1.7)
    rbd_std = rbd_std & ((t_c >= t_p2 * 1.7) | (is_p1_red & (t_p1 + t_c >= t_p2 * 1.7)))

    # DBD: Red leg-in (p2), Red leg-out (current)
    dbd_std = is_p2_red & is_c_red & l_in_norm & l_out_norm & (t_p1 <= t_p2 * 0.6) & (t_p2 >= t_p1 * 1.7)
    dbd_std = dbd_std & ((t_c >= t_p2 * 1.7) | (is_p1_red & (t_p1 + t_c >= t_p2 * 1.7)))

    # DBR: Red leg-in (p2), Green leg-out (current)
    dbr_std = is_p2_red & is_c_green & l_in_norm & l_out_norm & (t_p1 <= t_p2 * 0.6) & (t_p2 >= t_p1 * 1.7)
    dbr_std = dbr_std & ((t_c >= t_p2 * 1.7) | (is_p1_green & (t_p1 + t_c >= t_p2 * 1.7)))

    # RBR: Green leg-in (p2), Green leg-out (current)
    rbr_std = is_p2_green & is_c_green & l_in_norm & l_out_norm & (t_p1 <= t_p2 * 0.6) & (t_p2 >= t_p1 * 1.7)
    rbr_std = rbr_std & ((t_c >= t_p2 * 1.7) | (is_p1_green & (t_p1 + t_c >= t_p2 * 1.7)))

    # Convert to boolean series
    rbd_std = _bool(rbd_std)
    dbd_std = _bool(dbd_std)
    dbr_std = _bool(dbr_std)
    rbr_std = _bool(rbr_std)

    # Check that price doesn't break the base
    d["is_RBD"] = rbd_std & (h <= h1)
    d["is_DBD"] = dbd_std & (h <= h1)
    d["is_DBR"] = dbr_std & (l >= l1)
    d["is_RBR"] = rbr_std & (l >= l1)

    # 🔥 Add BIG BASE columns
    d["is_BIG_SUPPLY"] = is_big_supply
    d["is_BIG_DEMAND"] = is_big_demand

    # Store shifted values for zone creation
    for n, s in [("o1", p1_o), ("c1", p1_c), ("o2", p2_o), ("c2", p2_c),
                 ("o3", p3_o), ("c3", p3_c),
                 ("h1", h1), ("h2", h2), ("h3", h3),
                 ("l1", l1), ("l2", l2), ("l3", l3)]:
        d[n] = s

    return d


def _zone_from_supply_row(d: pd.DataFrame, i: int, atr_buffer: float) -> Zone:
    # 🔥 Check if it's a BIG BASE pattern first
    if bool(d["is_BIG_SUPPLY"].iloc[i]):
        # For BIG SUPPLY: leg-in is p3 (3 bars back)
        h3, l3 = d["h3"].iloc[i], d["l3"].iloc[i]
        
        # BIG SUPPLY: Proximal = High of leg-in, Distal = Low of leg-in
        proximal = h3
        distal = l3
        risk = proximal - distal
        target = proximal - risk * 3.0
        
        return Zone(
            start_bar=i - 2,
            end_bar=i,
            proximal=proximal,
            distal=distal,
            target=target,
            is_supply=True,
            pattern_name="BIG SUPPLY",
            base_count=1,
            legout_count=1,
        )

    # Standard pattern (1 base candle) - WITH ATR buffer
    is_rbd = bool(d["is_RBD"].iloc[i])
    h1, l1 = d["h1"].iloc[i], d["l1"].iloc[i]
    o1, c1 = d["o1"].iloc[i], d["c1"].iloc[i]
    
    proximal = min(o1, c1)
    distal = h1 + atr_buffer
    
    risk = distal - proximal
    target = proximal - risk * 3.0
    name = "RBD" if is_rbd else "DBD"
    
    return Zone(
        start_bar=i - 1,
        end_bar=i,
        proximal=proximal,
        distal=distal,
        target=target,
        is_supply=True,
        pattern_name=name,
        base_count=1,
        legout_count=1,
    )


def _zone_from_demand_row(d: pd.DataFrame, i: int, atr_buffer: float) -> Zone:
    # 🔥 Check if it's a BIG BASE pattern first
    if bool(d["is_BIG_DEMAND"].iloc[i]):
        h3, l3 = d["h3"].iloc[i], d["l3"].iloc[i]
        
        # BIG DEMAND: Proximal = Low of leg-in, Distal = High of leg-in
        proximal = l3
        distal = h3
        risk = distal - proximal
        target = proximal + risk * 3.0
        
        return Zone(
            start_bar=i - 2,
            end_bar=i,
            proximal=proximal,
            distal=distal,
            target=target,
            is_supply=False,
            pattern_name="BIG DEMAND",
            base_count=1,
            legout_count=1,
        )

    # Standard pattern (1 base candle) - WITH ATR buffer
    is_dbr = bool(d["is_DBR"].iloc[i])
    h1, l1 = d["h1"].iloc[i], d["l1"].iloc[i]
    o1, c1 = d["o1"].iloc[i], d["c1"].iloc[i]
    
    proximal = max(o1, c1)
    distal = l1 - atr_buffer
    
    risk = proximal - distal
    target = proximal + risk * 3.0
    name = "DBR" if is_dbr else "RBR"
    
    return Zone(
        start_bar=i - 1,
        end_bar=i,
        proximal=proximal,
        distal=distal,
        target=target,
        is_supply=False,
        pattern_name=name,
        base_count=1,
        legout_count=1,
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
    seen_zones = {}

    for i in range(n):
        atr_buffer = atr_series.iloc[i] * atr_multiplier if not np.isnan(atr_series.iloc[i]) else 0.0
        pre_dist = atr_series.iloc[i] * pre_entry_mult if not np.isnan(atr_series.iloc[i]) else 0.0

        # 1) new zone creation
        # 🔥 BIG BASE patterns (priority)
        if d["is_BIG_SUPPLY"].iloc[i]:
            z = _zone_from_supply_row(d, i, atr_buffer)
            
            is_dup = False
            for key, (p, d_val) in seen_zones.items():
                if abs(p - z.proximal) < 0.5 and abs(d_val - z.distal) < 0.5:
                    is_dup = True
                    break
            if is_dup:
                continue
                
            seen_zones[f"{z.pattern_name}|{round(z.proximal, 2)}"] = (z.proximal, z.distal)
            
            risk = z.proximal - z.distal
            z.target = z.proximal - risk * rr_target
            z.trigger_bar = i
            active.append(z)
            all_zones.append(z)
            events.append({"bar": i, "type": "zone_found", "zone": z})

        if d["is_BIG_DEMAND"].iloc[i]:
            z = _zone_from_demand_row(d, i, atr_buffer)
            
            is_dup = False
            for key, (p, d_val) in seen_zones.items():
                if abs(p - z.proximal) < 0.5 and abs(d_val - z.distal) < 0.5:
                    is_dup = True
                    break
            if is_dup:
                continue
                
            seen_zones[f"{z.pattern_name}|{round(z.proximal, 2)}"] = (z.proximal, z.distal)
            
            risk = z.distal - z.proximal
            z.target = z.proximal + risk * rr_target
            z.trigger_bar = i
            active.append(z)
            all_zones.append(z)
            events.append({"bar": i, "type": "zone_found", "zone": z})

        # Original patterns
        if d["is_RBD"].iloc[i] or d["is_DBD"].iloc[i]:
            z = _zone_from_supply_row(d, i, atr_buffer)
            
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
