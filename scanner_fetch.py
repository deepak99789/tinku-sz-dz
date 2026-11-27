"""Bounded, controlled parallel OHLC fetching for Telegram scanners."""
import logging
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

import pandas as pd

logger = logging.getLogger(__name__)


def iter_symbol_frames(tickers, intervals, fetcher, period, custom_source_cache,
                       max_workers=4):
    """Yield (ticker, {interval: OHLC frame}) with bounded parallel symbol fetches.

    At most 2 * max_workers symbols are in flight, limiting memory and provider
    pressure. Each symbol's timeframes are fetched sequentially; scan/pattern/
    alert processing remains on the main thread and therefore unchanged.
    """
    ticker_iter = iter(tickers)

    def fetch_symbol(ticker):
        frames = {}
        for interval in intervals:
            try:
                frames[interval] = fetcher(
                    ticker, interval, period, custom_source_cache
                )
            except Exception:
                logger.exception("OHLC fetch failed for %s %s", ticker, interval)
                frames[interval] = pd.DataFrame()
        return ticker, frames

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        pending = {}

        def submit_next():
            try:
                ticker = next(ticker_iter)
            except StopIteration:
                return False
            pending[executor.submit(fetch_symbol, ticker)] = ticker
            return True

        for _ in range(max_workers * 2):
            if not submit_next():
                break

        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                pending.pop(future)
                yield future.result()
                submit_next()
