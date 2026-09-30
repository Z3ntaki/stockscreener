import argparse
import json
import yaml
import logging
import sys
import datetime
from zoneinfo import ZoneInfo
from data_provider import get_quote_with_fallback
from alert_rules import AlertEngine
from telegram_bot import TelegramBot
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def is_market_open(config: dict) -> bool:
    """Check if the Indian market is open based on config."""
    # This logic assumes Mon-Fri, and checks the configured time
    # This could be more sophisticated (handling holidays) but good for Phase 1.
    now = datetime.datetime.now(ZoneInfo(config.get('market_hours', {}).get('timezone', 'Asia/Kolkata')))
    
    if now.weekday() >= 5: # 5=Sat, 6=Sun
        logger.info("Weekend: Market is closed.")
        return False
        
    start_time = config.get('market_hours', {}).get('start', '09:15')
    end_time = config.get('market_hours', {}).get('end', '15:30')
    
    current_time_str = now.strftime("%H:%M")
    if current_time_str < start_time or current_time_str > end_time:
        logger.info(f"Time {current_time_str} is outside market hours ({start_time}-{end_time}).")
        return False
        
    # Checking for holidays via nsepython or a local holidays.json file
    if os.path.exists("holidays.json"):
        try:
            with open("holidays.json", "r") as f:
                holidays = json.load(f)
            today_str = now.strftime("%Y-%m-%d")
            if today_str in holidays:
                logger.info(f"Today is a holiday: {holidays[today_str]}. Market is closed.")
                return False
        except Exception as e:
            logger.warning(f"Error reading holidays.json: {e}")
            
    # Try nsepython holidays if it works
    try:
        from nsepython import nse_holidays
        h = nse_holidays()
        # nse_holidays might return a dict or similar, we just skip it if it fails
    except Exception:
        pass
        
    return True

def main():
    parser = argparse.ArgumentParser(description="NSE Stock Alert Tool")
    parser.add_argument("--dry-run", action="store_true", help="Print alerts instead of sending them.")
    parser.add_argument("--test-msg", action="store_true", help="Send a test message and exit.")
    parser.add_argument("--force", action="store_true", help="Run even if market is closed.")
    args = parser.parse_args()

    bot = TelegramBot()

    if args.test_msg:
        logger.info("Sending test message...")
        if args.dry_run:
            print("[DRY RUN] Test message: Hello from NSE Stock Alert Tool!")
        else:
            bot.send_message("Hello from <b>NSE Stock Alert Tool</b>! Your bot is working.")
        sys.exit(0)

    # Load config
    try:
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load config.yaml: {e}")
        sys.exit(1)

    if not args.force and not is_market_open(config):
        logger.info("Market is not open. Exiting.")
        sys.exit(0)

    # Load watchlist
    try:
        with open("watchlist.json", "r") as f:
            watchlist = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load watchlist.json: {e}")
        sys.exit(1)
        
    if not isinstance(watchlist, list) or len(watchlist) > 600:
        logger.error("Watchlist must be a list of up to 600 stocks.")
        sys.exit(1)

    provider_names = config.get("providers", ["jugaad-data", "nsepython", "yfinance"])
    retries = config.get("retry", {}).get("attempts", 3)
    backoff = config.get("retry", {}).get("backoff_factor", 2)

    engine = AlertEngine("config.yaml", "state.json")

    # If watchlist is large, use bulk yfinance to save time
    use_bulk = len(watchlist) > 20
    bulk_data = {}
    if use_bulk:
        logger.info(f"Large watchlist detected ({len(watchlist)} stocks). Using yfinance bulk download.")
        import yfinance as yf
        tickers = [f"{item['ticker']}.NS" for item in watchlist if item.get('ticker')]
        try:
            # Download all in one go
            df = yf.download(tickers, period="10d", group_by="ticker", progress=False)
            for item in watchlist:
                t = item['ticker']
                t_ns = f"{t}.NS"
                if t_ns in df.columns.levels[0]:
                    try:
                        ticker_data = df[t_ns]
                        # Get latest valid row
                        latest = ticker_data.dropna().iloc[-1]
                        prev = ticker_data.dropna().iloc[-2] if len(ticker_data.dropna()) > 1 else latest
                        # We also need average volume. We can approximate with the 10d mean
                        avg_vol = ticker_data['Volume'].mean()
                        
                        bulk_data[t] = {
                            "ticker": t,
                            "price": float(latest['Close']),
                            "prev_close": float(prev['Close']),
                            "volume": float(latest['Volume']),
                            "avg_volume": float(avg_vol),
                            "source": "yfinance-bulk",
                            "timestamp_ist": datetime.datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()
                        }
                    except Exception as e:
                        logger.debug(f"Error parsing bulk data for {t}: {e}")
        except Exception as e:
            logger.error(f"Bulk download failed: {e}")

    for item in watchlist:
        ticker = item.get("ticker")
        if not ticker:
            continue
            
        logger.info(f"Processing {ticker}...")
        
        if use_bulk and ticker in bulk_data:
            quote = bulk_data[ticker]
        else:
            quote = get_quote_with_fallback(ticker, provider_names, retries=retries, backoff=backoff)
            
        if not quote:
            logger.error(f"Could not fetch data for {ticker}. Skipping.")
            continue
            
        alerts = engine.check_alerts(quote, item)
        for msg in alerts:
            if args.dry_run:
                print(f"[DRY RUN] Would send:\n{msg}")
            else:
                success = bot.send_message(msg)
                if not success:
                    logger.error(f"Failed to send alert for {ticker}.")
                else:
                    logger.info(f"Sent alert for {ticker}.")

if __name__ == "__main__":
    main()
