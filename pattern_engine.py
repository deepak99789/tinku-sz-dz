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
    max_base_count: int = 3,
    proximal_method: str = "Wick to Wick",
    legin_body_min: float = 60.0,
    base_body_max: float = 55.0,
    legout_body_min: float = 65.0,
    base_range_max_legin: bool = True,
    legin_to_base_range_ratio: float = 1.0,
    legout_to_legin_range_ratio: float = 1.0,
) -> pd.DataFrame:
    """
    Detect RBD/DBD/DBR/RBR patterns using closed OHLC candles.

    Range-strength filter:
      * 1 leg-out candle: its High-Low range must be > leg-in range.
      * 2 leg-out candles: sum of both High-Low ranges must be > leg-in range.

    Existing body-percentage filters and base/departure rules remain active.
    When base_range_max_legin=True, the leg-in range must be at least
    legin_to_base_range_ratio times each base candle's range.
    Combined leg-out range must be strictly greater than
    legout_to_legin_range_ratio times the leg-in range.
    """
    d = df.copy()
    n = len(d)

    # Shifted OHLC values are retained for the optional validation checklist.
    for offset in range(1, 6):
        d[f"h{offset}"] = d["High"].shift(offset)
        d[f"l{offset}"] = d["Low"].shift(offset)
        d[f"o{offset}"] = d["Open"].shift(offset)
        d[f"c{offset}"] = d["Close"].shift(offset)

    max_base_count = max(1, min(int(max_base_count), 3))
    allowed = set(range(1, max_base_count + 1))
    if str(base_count_filter) in {"1", "2", "3"}:
        allowed &= {int(base_count_filter)}

    flag_columns = (
        "is_RBD", "is_DBD", "is_DBR", "is_RBR",
        "rbd_2base", "rbd_3base", "rbd_ext",
        "dbd_2base", "dbd_3base", "dbd_ext",
        "dbr_2base", "dbr_3base", "dbr_ext",
        "rbr_2base", "rbr_3base", "rbr_ext",
    )
    for name in flag_columns:
        d[name] = False

    d["selected_base_count"] = 0
    d["selected_legout_count"] = 0
    d["selected_zone_top"] = np.nan
    d["selected_zone_bottom"] = np.nan
    d["selected_pattern"] = ""

    o = d["Open"].to_numpy(dtype=float)
    c = d["Close"].to_numpy(dtype=float)
    h = d["High"].to_numpy(dtype=float)
    l = d["Low"].to_numpy(dtype=float)

    def body_pct(idx: int) -> float:
        candle_range = h[idx] - l[idx]
        if candle_range <= 0:
            return -1.0
        return abs(c[idx] - o[idx]) / candle_range * 100.0

    for i in range(n):
        if not np.isfinite([o[i], c[i], h[i], l[i]]).all() or c[i] == o[i]:
            continue

        is_demand = c[i] > o[i]
        direction = 1 if is_demand else -1
        selected = None

        # Prefer a valid two-candle departure when both variants qualify.
        # Longer base sequences still take priority, as in the Pine script.
        for count in range(1, max_base_count + 1):
            if count not in allowed:
                continue

            for legout_count in (1, 2):
                first_legout_idx = i - legout_count + 1
                last_base_idx = first_legout_idx - 1
                first_base_idx = last_base_idx - count + 1
                legin_idx = first_base_idx - 1

                if legin_idx < 0:
                    continue

                # Every leg-out candle must be in the departure direction
                # and pass the existing minimum body/range percentage filter.
                legout_valid = True
                combined_legout_range = 0.0
                for k in range(first_legout_idx, i + 1):
                    if not np.isfinite([o[k], c[k], h[k], l[k]]).all():
                        legout_valid = False
                        break
                    if (c[k] - o[k]) * direction <= 0:
                        legout_valid = False
                        break
                    if body_pct(k) < legout_body_min:
                        legout_valid = False
                        break
                    candle_range = h[k] - l[k]
                    if candle_range <= 0:
                        legout_valid = False
                        break
                    combined_legout_range += candle_range

                if not legout_valid:
                    continue

                legin_range = h[legin_idx] - l[legin_idx]
                if legin_range <= 0:
                    continue
                legin_pct = body_pct(legin_idx)
                if legin_pct < legin_body_min:
                    continue

                # Configurable leg-out versus leg-in range strength.
                if combined_legout_range <= legin_range * max(float(legout_to_legin_range_ratio), 0.01):
                    continue

                base_valid = True
                base_high = -np.inf
                base_low = np.inf
                body_high = -np.inf
                body_low = np.inf

                for j in range(first_base_idx, last_base_idx + 1):
                    base_range = h[j] - l[j]
                    if base_range <= 0 or body_pct(j) < 0 or body_pct(j) >= base_body_max:
                        base_valid = False
                        break
                    if base_range_max_legin and base_range * max(float(legin_to_base_range_ratio), 0.01) > legin_range:
                        base_valid = False
                        break
                    base_high = max(base_high, h[j])
                    base_low = min(base_low, l[j])
                    body_high = max(body_high, max(o[j], c[j]))
                    body_low = min(body_low, min(o[j], c[j]))

                if not base_valid:
                    continue

                departure_valid = c[i] > base_high if is_demand else c[i] < base_low
                if not departure_valid:
                    continue

                if proximal_method == "Wick to Body":
                    zone_top = body_high if is_demand else base_high
                    zone_bottom = base_low if is_demand else body_low
                else:
                    zone_top, zone_bottom = base_high, base_low

                selected = (
                    count, legout_count, zone_top, zone_bottom, legin_idx
                )

        if selected is None:
            continue

        count, legout_count, zone_top, zone_bottom, legin_idx = selected
        legin_green = c[legin_idx] > o[legin_idx]
        if is_demand:
            pattern = "RBR" if legin_green else "DBR"
        else:
            pattern = "RBD" if legin_green else "DBD"

        d.iat[i, d.columns.get_loc("selected_base_count")] = count
        d.iat[i, d.columns.get_loc("selected_legout_count")] = legout_count
        d.iat[i, d.columns.get_loc("selected_zone_top")] = zone_top
        d.iat[i, d.columns.get_loc("selected_zone_bottom")] = zone_bottom
        d.iat[i, d.columns.get_loc("selected_pattern")] = pattern
        d.iat[i, d.columns.get_loc("is_" + pattern)] = True

        if count == 2:
            d.iat[i, d.columns.get_loc(pattern.lower() + "_2base")] = True
        elif count == 3:
            d.iat[i, d.columns.get_loc(pattern.lower() + "_3base")] = True
        if legout_count == 2:
            d.iat[i, d.columns.get_loc(pattern.lower() + "_ext")] = True

    return d


# --------------------------------------------------------------------------
# 🔥 EXTRA VALIDATION CHECKLIST (optional, off by default)
#
# Applies on top of the default zone-finding logic - does NOT change which
# candles form the pattern, only decides whether a detected RBD/DBD/DBR/RBR
# zone is "valid" enough to be created, when the user turns the checklist ON.
#
#   1) Legout candle's OPEN must fall within the legin candle's High-Low
#      range (i.e. legout should not open gapped above/below the legin
#      candle).
#
#   2) Legout candle's OPEN must have a clean gap beyond the base candle's
#      body (open/close) - i.e. the base candle's body must NOT be covered
#      by the legout candle's body. The legout's wick is allowed to dip
#      into / cover the base body, but its body may not.
# --------------------------------------------------------------------------
def _validate_legin_legout(d: pd.DataFrame, i: int, is_supply: bool) -> bool:
    """Apply the optional legacy open-gap checklist to the selected pattern."""
    count = int(d["selected_base_count"].iloc[i])
    legout_count = int(d["selected_legout_count"].iloc[i])
    if count <= 0 or legout_count <= 0:
        return False

    first_legout_idx = i - legout_count + 1
    last_base_idx = first_legout_idx - 1
    first_base_idx = last_base_idx - count + 1
    legin_idx = first_base_idx - 1

    if legin_idx < 0:
        return False

    legin_high = d["High"].iloc[legin_idx]
    legin_low = d["Low"].iloc[legin_idx]
    legout_open = d["Open"].iloc[first_legout_idx]
    base = d.iloc[first_base_idx:last_base_idx + 1]

    if base.empty or base[["Open", "Close"]].isna().any().any():
        return False
    if pd.isna(legin_high) or pd.isna(legin_low) or pd.isna(legout_open):
        return False

    # First leg-out candle must open inside the leg-in candle's full range.
    if not (legin_low <= legout_open <= legin_high):
        return False

    base_body_high = max(base["Open"].max(), base["Close"].max())
    base_body_low = min(base["Open"].min(), base["Close"].min())

    if is_supply:
        return bool(legout_open < base_body_low)
    return bool(legout_open > base_body_high)


def _zone_from_supply_row(d: pd.DataFrame, i: int, atr_buffer: float) -> Zone:
    count = int(d["selected_base_count"].iloc[i])
    legout_count = int(d["selected_legout_count"].iloc[i])
    top = float(d["selected_zone_top"].iloc[i])
    bottom = float(d["selected_zone_bottom"].iloc[i])
    name = str(d["selected_pattern"].iloc[i])
    entry = bottom
    stop = top
    return Zone(
        start_bar=i - count - legout_count + 1, end_bar=i, proximal=entry, distal=stop,
        target=entry - (stop - entry) * 3.0, is_supply=True,
        pattern_name=name, base_count=count, legout_count=legout_count,
    )


def _zone_from_demand_row(d: pd.DataFrame, i: int, atr_buffer: float) -> Zone:
    count = int(d["selected_base_count"].iloc[i])
    legout_count = int(d["selected_legout_count"].iloc[i])
    top = float(d["selected_zone_top"].iloc[i])
    bottom = float(d["selected_zone_bottom"].iloc[i])
    name = str(d["selected_pattern"].iloc[i])
    entry = top
    stop = bottom
    return Zone(
        start_bar=i - count - legout_count + 1, end_bar=i, proximal=entry, distal=stop,
        target=entry + (entry - stop) * 3.0, is_supply=False,
        pattern_name=name, base_count=count, legout_count=legout_count,
    )


def track_zones(
    d: pd.DataFrame,
    atr_series: pd.Series,
    atr_multiplier: float,
    rr_target: float,
    pre_entry_mult: float,
    validation_checklist: bool = False,
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
        supply_signal = bool(d["is_RBD"].iloc[i] or d["is_DBD"].iloc[i])
        if supply_signal and validation_checklist and not _validate_legin_legout(d, i, is_supply=True):
            supply_signal = False

        if supply_signal:
            z = _zone_from_supply_row(d, i, atr_buffer)
            
            # Exact-price duplicate check. A fixed 0.5 tolerance is far too
            # large for Forex quotes (e.g. EURUSD around 1.08) and hides
            # distinct zones. Only suppress the same pattern and same boundaries.
            duplicate_key = (
                z.pattern_name,
                round(float(z.proximal), 8),
                round(float(z.distal), 8),
            )
            if duplicate_key in seen_zones:
                continue
            seen_zones[duplicate_key] = (z.proximal, z.distal)
            
            risk = z.distal - z.proximal
            z.target = z.proximal - risk * rr_target
            z.trigger_bar = i
            active.append(z)
            all_zones.append(z)
            events.append({"bar": i, "type": "zone_found", "zone": z})

        demand_signal = bool(d["is_DBR"].iloc[i] or d["is_RBR"].iloc[i])
        if demand_signal and validation_checklist and not _validate_legin_legout(d, i, is_supply=False):
            demand_signal = False

        if demand_signal:
            z = _zone_from_demand_row(d, i, atr_buffer)
            
            # Exact-price duplicate check. A fixed 0.5 tolerance is far too
            # large for Forex quotes (e.g. EURUSD around 1.08) and hides
            # distinct zones. Only suppress the same pattern and same boundaries.
            duplicate_key = (
                z.pattern_name,
                round(float(z.proximal), 8),
                round(float(z.distal), 8),
            )
            if duplicate_key in seen_zones:
                continue
            seen_zones[duplicate_key] = (z.proximal, z.distal)
            
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
    validation_checklist: bool = False,
    proximal_method: str = "Wick to Wick",
    max_base_count: int = 3,
    base_range_max_legin: bool = True,
    legin_to_base_range_ratio: float = 1.0,
    legout_to_legin_range_ratio: float = 1.0,
    legin_body_min: float = 60.0,
    base_body_max: float = 55.0,
    legout_body_min: float = 65.0,
) -> DetectionResult:
    d = detect_patterns(
        df, base_count_filter=base_count_filter, proximal_method=proximal_method,
        max_base_count=max_base_count, base_range_max_legin=base_range_max_legin,
        legin_to_base_range_ratio=legin_to_base_range_ratio,
        legout_to_legin_range_ratio=legout_to_legin_range_ratio,
        legin_body_min=legin_body_min,
        base_body_max=base_body_max,
        legout_body_min=legout_body_min,
    )
    atr_series = wilder_atr(df, atr_length)
    result = track_zones(
        d, atr_series, atr_multiplier, rr_target, pre_entry_mult,
        validation_checklist=validation_checklist,
    )
    return result
