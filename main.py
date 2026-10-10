import os
import json
import logging
import yaml
import datetime
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from alert_rules import AlertEngine
from data_provider import get_quote_with_fallback

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

USER_DATA_FILE = "user_data.json"

def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load {USER_DATA_FILE}: {e}")
    return {}

def save_user_data(data):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def is_market_open(config: dict) -> bool:
    now = datetime.datetime.now(ZoneInfo(config.get('market_hours', {}).get('timezone', 'Asia/Kolkata')))
    if now.weekday() >= 5:
        return False
    start_time = config.get('market_hours', {}).get('start', '09:15')
    end_time = config.get('market_hours', {}).get('end', '15:30')
    current_time_str = now.strftime("%H:%M")
    if current_time_str < start_time or current_time_str > end_time:
        return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "📈 Welcome to your Personal Stock Screener!\n\n"
        "Here you can create your own custom watchlist. I will monitor only the stocks you watch and send you alerts + AI sentiment when they move.\n\n"
        "Commands:\n"
        "/watch TICKER [threshold_pct] - Watch a stock (e.g., /watch TCS 2.0)\n"
        "/unwatch TICKER - Stop watching a stock\n"
        "/list - Show your watchlist\n"
        "/analyze TICKER - Instant news & sentiment fetch"
    )
    await update.message.reply_text(welcome_text)

async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /watch TICKER [threshold_pct] (e.g., /watch TCS 3.0)")
        return

    ticker = args[0].upper()
    threshold = 3.0
    if len(args) > 1:
        try:
            threshold = float(args[1])
        except ValueError:
            await update.message.reply_text("Invalid threshold. Using default 3.0%.")

    data = load_user_data()
    if chat_id not in data:
        data[chat_id] = {}
        
    data[chat_id][ticker] = {"threshold_pct": threshold, "ticker": ticker}
    save_user_data(data)
    
    await update.message.reply_text(f"✅ Added {ticker} to your watchlist with a {threshold}% alert threshold.")

async def unwatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /unwatch TICKER")
        return

    ticker = args[0].upper()
    data = load_user_data()
    
    if chat_id in data and ticker in data[chat_id]:
        del data[chat_id][ticker]
        save_user_data(data)
        await update.message.reply_text(f"❌ Removed {ticker} from your watchlist.")
    else:
        await update.message.reply_text(f"You aren't watching {ticker}.")

async def list_watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    data = load_user_data()
    
    if chat_id not in data or not data[chat_id]:
        await update.message.reply_text("Your watchlist is empty. Add some using /watch TICKER.")
        return
        
    msg = "📋 <b>Your Watchlist:</b>\n\n"
    for ticker, config in data[chat_id].items():
        msg += f"• {ticker} (Threshold: {config.get('threshold_pct', 3.0)}%)\n"
        
    await update.message.reply_text(msg, parse_mode="HTML")

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /analyze TICKER")
        return
        
    ticker = args[0].upper()
    await update.message.reply_text(f"⏳ Analyzing {ticker}... This may take a moment.")
    
    # We use a dummy engine just to access _enrich_alert
    engine = AlertEngine("config.yaml", "dummy_state.json")
    try:
        enrichment = engine._enrich_alert(ticker)
        await update.message.reply_text(f"📊 <b>Analysis for {ticker}:</b>\n{enrichment}", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Failed to analyze {ticker}. Make sure the ticker is correct.")
        logger.error(f"Analysis failed: {e}")

async def run_scanner(context: ContextTypes.DEFAULT_TYPE):
    """Background task that scans the market and messages subscribers."""
    try:
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
    except Exception:
        config = {}

    if not is_market_open(config):
        return

    data = load_user_data()
    if not data:
        return

    # Collect unique tickers
    all_tickers = set()
    for chat_id, watchlist in data.items():
        for ticker in watchlist.keys():
            all_tickers.add(ticker)

    use_bulk = len(all_tickers) > 20
    bulk_data = {}
    if use_bulk:
        import yfinance as yf
        tickers_ns = [f"{t}.NS" for t in all_tickers]
        try:
            df = yf.download(tickers_ns, period="10d", group_by="ticker", progress=False)
            for t in all_tickers:
                t_ns = f"{t}.NS"
                if t_ns in df.columns.levels[0]:
                    try:
                        ticker_data = df[t_ns].dropna()
                        if len(ticker_data) < 1: continue
                        latest = ticker_data.iloc[-1]
                        prev = ticker_data.iloc[-2] if len(ticker_data) > 1 else latest
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
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Bulk download failed: {e}")

    provider_names = config.get("providers", ["jugaad-data", "nsepython", "yfinance"])
    retries = config.get("retry", {}).get("attempts", 3)
    backoff = config.get("retry", {}).get("backoff_factor", 2)

    # Dictionary to cache alert enrichments so we don't fetch news multiple times for the same ticker
    enriched_alerts = {}

    for chat_id, watchlist in data.items():
        engine = AlertEngine("config.yaml", f"state_{chat_id}.json")
        for ticker, watch_config in watchlist.items():
            if use_bulk and ticker in bulk_data:
                quote = bulk_data[ticker]
            else:
                quote = get_quote_with_fallback(ticker, provider_names, retries=retries, backoff=backoff)
            
            if not quote: continue
            
            # Temporarily disable enrichment inside check_alerts by overriding it 
            # We will enrich manually and cache it
            original_enrich = engine._enrich_alert
            engine._enrich_alert = lambda t: "" 
            
            alerts = engine.check_alerts(quote, watch_config)
            
            # Restore
            engine._enrich_alert = original_enrich
            
            if alerts:
                # Get or compute enrichment
                if ticker not in enriched_alerts:
                    enriched_alerts[ticker] = engine._enrich_alert(ticker)
                    
                for msg in alerts:
                    full_msg = msg + enriched_alerts[ticker]
                    try:
                        await context.bot.send_message(chat_id=chat_id, text=full_msg, parse_mode="HTML")
                    except Exception as e:
                        logger.error(f"Failed to send alert to {chat_id}: {e}")
        
        # Save state manually after we process their list
        engine._save_state()

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN is missing!")
        return

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("watch", watch))
    application.add_handler(CommandHandler("unwatch", unwatch))
    application.add_handler(CommandHandler("list", list_watchlist))
    application.add_handler(CommandHandler("analyze", analyze))

    # Add scanner to run every 5 minutes
    job_queue = application.job_queue
    job_queue.run_repeating(run_scanner, interval=300, first=10)

    logger.info("Bot is starting up... Press Ctrl-C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
