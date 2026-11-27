import unittest

import pandas as pd

from pattern_engine import run_full_pipeline


def make_demand_sequence(pattern, legout_count):
    # One valid leg-in, one base candle, then a same-colour Leg-out run.
    legin = (
        {"Open": 12.0, "High": 12.1, "Low": 9.9, "Close": 10.0}
        if pattern == "DBR"
        else {"Open": 10.0, "High": 12.1, "Low": 9.9, "Close": 12.0}
    )
    rows = [
        legin,
        {"Open": 11.0, "High": 11.2, "Low": 10.8, "Close": 11.1},
        {"Open": 11.0, "High": 13.5, "Low": 10.9, "Close": 13.0},
    ]
    for offset in range(legout_count - 1):
        open_price = 13.0 + offset * 0.4
        rows.append({
            "Open": open_price,
            "High": open_price + 0.5,
            "Low": open_price - 0.1,
            "Close": open_price + 0.4,
        })
    return pd.DataFrame(rows)


class TelegramLegoutCountTrackingTests(unittest.TestCase):
    def run_detection(self, frame):
        return run_full_pipeline(
            frame,
            atr_length=1,
            atr_multiplier=0.35,
            rr_target=3.0,
            pre_entry_mult=1.5,
            base_count_filter="1",
            max_base_count=1,
            proximal_method="Wick to Wick",
            base_range_max_legin=True,
            legin_to_base_range_ratio=1.0,
            legout_to_legin_range_ratio=1.0,
            legin_body_min=60.0,
            base_body_max=55.0,
            legout_body_min=65.0,
            legin_must_strictly_exceed_base=True,
            legout_must_respect_base_distal=True,
            legout_open_within_legin_range=True,
            telegram_first_legout_only_rules=True,
            telegram_fast_scan=True,
        )

    def test_dbr_zone_count_grows_from_one_to_two(self):
        result = self.run_detection(make_demand_sequence("DBR", 2))
        self.assertEqual(len(result.all_zones), 1)
        self.assertEqual(result.all_zones[0].pattern_name, "DBR")
        self.assertEqual(result.all_zones[0].legout_count, 2)

    def test_rbr_zone_count_grows_from_one_to_four(self):
        result = self.run_detection(make_demand_sequence("RBR", 4))
        self.assertEqual(len(result.all_zones), 1)
        self.assertEqual(result.all_zones[0].pattern_name, "RBR")
        self.assertEqual(result.all_zones[0].legout_count, 4)
        zone_events = [event for event in result.events if event["type"] == "zone_found"]
        self.assertEqual(len(zone_events), 1)
        self.assertEqual(zone_events[0]["zone"].legout_count, 4)


if __name__ == "__main__":
    unittest.main()
