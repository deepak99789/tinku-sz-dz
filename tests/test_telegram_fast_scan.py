import unittest

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from pattern_engine import detect_patterns


class TelegramFastScanEquivalenceTests(unittest.TestCase):
    def test_fast_telegram_scan_matches_reference_results(self):
        rng = np.random.default_rng(20261127)
        for case in range(12):
            count = 420
            close = 1.10 + np.cumsum(rng.normal(0, 0.0008, count))
            open_ = close + rng.normal(0, 0.0006, count)
            if case % 3 == 0:
                for start in range(40, count - 8, 70):
                    for offset in range(5):
                        idx = start + offset
                        open_[idx] = close[idx] - 0.0007
            spread = rng.uniform(0.0001, 0.0012, count)
            frame = pd.DataFrame({
                "Open": open_, "High": np.maximum(open_, close) + spread,
                "Low": np.minimum(open_, close) - spread, "Close": close,
            })
            kwargs = dict(
                max_base_count=3, legin_body_min=60.0, base_body_max=55.0,
                legout_body_min=65.0, base_range_max_legin=True,
                legin_must_strictly_exceed_base=True,
                legout_open_within_legin_range=True,
                telegram_first_legout_only_rules=True,
            )
            reference = detect_patterns(frame, **kwargs, telegram_fast_scan=False)
            optimized = detect_patterns(frame, **kwargs, telegram_fast_scan=True)
            assert_frame_equal(reference, optimized)

    def test_fast_flag_does_not_change_non_telegram_path(self):
        rng = np.random.default_rng(42)
        count = 180
        close = 100 + np.cumsum(rng.normal(0, 0.5, count))
        open_ = close + rng.normal(0, 0.4, count)
        spread = rng.uniform(0.1, 1.0, count)
        frame = pd.DataFrame({
            "Open": open_, "High": np.maximum(open_, close) + spread,
            "Low": np.minimum(open_, close) - spread, "Close": close,
        })
        reference = detect_patterns(frame, telegram_fast_scan=False)
        optimized = detect_patterns(frame, telegram_fast_scan=True)
        assert_frame_equal(reference, optimized)


if __name__ == "__main__":
    unittest.main()
