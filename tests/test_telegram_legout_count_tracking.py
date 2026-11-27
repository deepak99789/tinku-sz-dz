import unittest

import pandas as pd

from pattern_engine import run_full_pipeline


def make_sequence(pattern, legout_count):
    is_demand = pattern in ("DBR", "RBR")
    legin_green = pattern in ("RBR", "RBD")

    if legin_green:
        legin = {"Open": 10.0, "High": 12.1, "Low": 9.9, "Close": 12.0}
    else:
        legin = {"Open": 12.0, "High": 12.1, "Low": 9.9, "Close": 10.0}

    base = {"Open": 11.0, "High": 11.2, "Low": 10.8, "Close": 11.1}
    if is_demand:
        first_legout = {"Open": 11.0, "High": 13.5, "Low": 10.9, "Close": 13.0}
    else:
        first_legout = {"Open": 11.0, "High": 11.1, "Low": 8.5, "Close": 8.8}

    rows = [legin, base, first_legout]
    for offset in range(legout_count - 1):
        if is_demand:
            open_price = 13.0 + offset * 0.4
            rows.append({
                "Open": open_price,
                "High": open_price + 0.6,
                "Low": open_price - 0.1,
                "Close": open_price + 0.5,
            })
        else:
            open_price = 8.8 - offset * 0.4
            rows.append({
                "Open": open_price,
                "High": open_price + 0.1,
                "Low": open_price - 0.6,
                "Close": open_price - 0.5,
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

    def test_all_four_patterns_count_the_full_same_direction_run(self):
        # Include counts beyond the two examples from the original regression
        # tests: there is no fixed 2- or 4-candle cap.
        for pattern in ("DBR", "RBR", "RBD", "DBD"):
            for expected_count in (1, 2, 3, 4, 6):
                with self.subTest(pattern=pattern, expected_count=expected_count):
                    result = self.run_detection(make_sequence(pattern, expected_count))
                    self.assertEqual(len(result.all_zones), 1)
                    zone = result.all_zones[0]
                    self.assertEqual(zone.pattern_name, pattern)
                    self.assertEqual(zone.legout_count, expected_count)

                    zone_events = [
                        event for event in result.events
                        if event["type"] == "zone_found"
                    ]
                    self.assertEqual(len(zone_events), 1)
                    self.assertEqual(zone_events[0]["zone"].legout_count, expected_count)


if __name__ == "__main__":
    unittest.main()
