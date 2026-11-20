import os
import ccxt
import pandas as pd
from datetime import datetime, timezone

DATA_DIR = os.path.dirname(os.path.abspath(__file__)) + "/data"

def fetch_and_save_ohlcv(
    symbol="BTC/USDT:USDT",
    timeframe="1h",
    days=180,
    exchange_id="binance",
    output_filename="btc_futures_1h.csv"
):
    """
    Fetches real historical OHLCV data for perpetual futures using CCXT.
    Paginates back in time up to `days` days.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    out_path = os.path.join(DATA_DIR, output_filename)

    print(f"Connecting to {exchange_id} perpetual futures market for {symbol}...")
    exchange_class = getattr(ccxt, exchange_id)
    exchange = exchange_class({
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}
    })

    now_ms = exchange.milliseconds()
    start_ms = now_ms - (days * 24 * 60 * 60 * 1000)
    current_since = start_ms

    all_candles = []
    print(f"Fetching {days} days of {timeframe} candles since {datetime.fromtimestamp(start_ms/1000, tz=timezone.utc).strftime('%Y-%m-%d')}...")

    batch_count = 0
    while current_since < now_ms:
        try:
            candles = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=current_since, limit=1000)
            if not candles:
                break
            all_candles.extend(candles)
            batch_count += 1
            print(f"  Batch {batch_count}: fetched {len(candles)} candles. Latest: {datetime.fromtimestamp(candles[-1][0]/1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')}")
            
            # Update since to 1 ms after the last candle's timestamp
            last_ts = candles[-1][0]
            if last_ts == current_since:
                break
            current_since = last_ts + 1

            if len(candles) < 1000:
                # No more data in this range
                break
        except Exception as e:
            print(f"Error fetching batch: {e}")
            break

    if not all_candles:
        raise ValueError(f"Failed to fetch any candles for {symbol} from {exchange_id}.")

    # Format into DataFrame
    df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df.drop_duplicates(subset=['timestamp'], inplace=True)
    df.sort_values(by='timestamp', inplace=True)
    df.reset_index(drop=True, inplace=True)

    df.to_csv(out_path, index=False)
    print(f"Successfully saved {len(df)} candles to {out_path}")
    print(f"Date range: {df['timestamp'].iloc[0]} -> {df['timestamp'].iloc[-1]}")
    return df

def load_data(filename="btc_futures_1h.csv"):
    """
    Loads saved OHLCV CSV data into a pandas DataFrame.
    """
    file_path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Data file {file_path} does not exist. Run data fetcher first.")
    
    df = pd.read_csv(file_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

if __name__ == "__main__":
    fetch_and_save_ohlcv(days=120)
