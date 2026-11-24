import unittest
from unittest.mock import patch

import pandas as pd

import data_sources


class DataSourceFallbackTests(unittest.TestCase):
    def test_twelve_data_intraday_fallback_uses_five_minute_source(self):
        index = pd.date_range(
            "2026-11-23 09:30",
            periods=6,
            freq="5min",
            tz="America/New_York",
        )
        five_minute_bars = pd.DataFrame(
            {
                "Open": [100, 101, 102, 103, 104, 105],
                "High": [102, 103, 104, 105, 106, 107],
                "Low": [99, 100, 101, 102, 103, 104],
                "Close": [101, 102, 103, 104, 105, 106],
                "Volume": [10, 10, 10, 20, 20, 20],
            },
            index=index,
        )

        with patch.object(data_sources, "_fetch_yahoo", return_value=pd.DataFrame()):
            with patch.object(
                data_sources,
                "_fetch_twelve_data",
                return_value=five_minute_bars,
            ) as twelve_fetch:
                result = data_sources.fetch_ohlcv(
                    "AAPL", "15m", period="1mo", market="us"
                )

        twelve_fetch.assert_called_once_with("AAPL", "5m")
        self.assertEqual(len(result), 2)
        self.assertEqual(result.iloc[0]["Open"], 100)
        self.assertEqual(result.iloc[0]["High"], 104)
        self.assertEqual(result.iloc[0]["Low"], 99)
        self.assertEqual(result.iloc[0]["Close"], 103)
        self.assertEqual(result.iloc[0]["Volume"], 30)


if __name__ == "__main__":
    unittest.main()
