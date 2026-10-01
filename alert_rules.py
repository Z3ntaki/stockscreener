import json
import logging
import datetime
from zoneinfo import ZoneInfo
import os

logger = logging.getLogger(__name__)


class AlertEngine:
    def __init__(self, config_path: str, state_path: str):
        self.state_path = state_path
        self.state = self._load_state()

        self.daily_cap = 10
        if os.path.exists(config_path):
            import yaml
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                self.daily_cap = config.get('limits', {}).get('daily_alert_cap', 10)

        self._rotate_state_if_needed()

    def _load_state(self):
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load state: {e}")
        return {}

    def _save_state(self):
        try:
            with open(self.state_path, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _get_today_ist(self):
        return datetime.datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")

    def _rotate_state_if_needed(self):
        today = self._get_today_ist()
        if self.state.get("date") != today:
            self.state = {
                "date": today,
                "alerts_sent_today": 0,
                "history": {}
            }
            self._save_state()

    def _enrich_alert(self, ticker: str) -> str:
        """Fetch news/sentiment, technicals, and delivery data for a triggered alert."""
        enrichment = ""

        # 1. Technical indicators
        try:
            from technical_indicators import get_technicals_for_ticker, format_technicals
            technicals = get_technicals_for_ticker(ticker)
            enrichment += format_technicals(technicals)
        except Exception as e:
            logger.warning(f"Technicals enrichment failed for {ticker}: {e}")

        # 2. Delivery % data
        try:
            from delivery_tracker import get_delivery_data, format_delivery_data
            delivery = get_delivery_data(ticker)
            enrichment += format_delivery_data(delivery)
        except Exception as e:
            logger.warning(f"Delivery enrichment failed for {ticker}: {e}")

        # 3. News & Sentiment (Gemini AI or VADER)
        try:
            from sentiment import get_news_and_sentiment
            enrichment += get_news_and_sentiment(ticker)
        except Exception as e:
            logger.warning(f"Sentiment enrichment failed for {ticker}: {e}")

        return enrichment

    def check_alerts(self, quote: dict, watch_config: dict) -> list[str]:
        """Returns a list of alert messages to send, and updates state."""
        self._rotate_state_if_needed()

        if self.state["alerts_sent_today"] >= self.daily_cap:
            logger.info("Daily alert cap reached. Skipping.")
            return []

        ticker = quote['ticker']
        price = quote['price']
        prev_close = quote['prev_close']

        pct_change = ((price - prev_close) / prev_close) * 100
        threshold_pct = watch_config.get('threshold_pct', 3.0)
        support = watch_config.get('support')
        resistance = watch_config.get('resistance')

        ticker_history = self.state["history"].setdefault(ticker, [])
        alerts = []

        # Rule 1: Threshold
        if abs(pct_change) >= threshold_pct:
            if "threshold" not in ticker_history:
                msg = (f"🚨 {ticker} moved {pct_change:.2f}%!\n"
                       f"Price: {price} (Prev: {prev_close})\n"
                       f"Rule: Threshold > {threshold_pct}%\n"
                       f"Source: {quote['source']} at {quote['timestamp_ist']}")
                alerts.append(msg)
                ticker_history.append("threshold")

        # Rule 2: Support / Resistance
        if support and price <= support:
            if "support" not in ticker_history:
                msg = (f"📉 {ticker} crossed support!\n"
                       f"Price: {price} (Support: {support})\n"
                       f"Change: {pct_change:.2f}%\n"
                       f"Source: {quote['source']} at {quote['timestamp_ist']}")
                alerts.append(msg)
                ticker_history.append("support")

        if resistance and price >= resistance:
            if "resistance" not in ticker_history:
                msg = (f"📈 {ticker} crossed resistance!\n"
                       f"Price: {price} (Resistance: {resistance})\n"
                       f"Change: {pct_change:.2f}%\n"
                       f"Source: {quote['source']} at {quote['timestamp_ist']}")
                alerts.append(msg)
                ticker_history.append("resistance")

        # Rule 3: Heavy Volume with Positive Sentiment (5-10% UP)
        volume = quote.get('volume')
        avg_volume = quote.get('avg_volume')

        # If the current provider didn't return avg_volume (e.g. jugaad-data), we could
        # try fetching it specifically here from yfinance if it's important.
        # For now, if we have it, we evaluate:
        if not avg_volume and quote['source'] != 'yfinance':
            # Try fetching from yfinance just for this rule
            try:
                import yfinance as yf
                yf_info = yf.Ticker(f"{ticker}.NS").info
                volume = volume or yf_info.get('volume') or yf_info.get('regularMarketVolume')
                avg_volume = yf_info.get('averageVolume') or yf_info.get('averageVolume10days')
            except Exception as e:
                logger.debug(f"Could not fetch avg_volume for {ticker} from yf: {e}")

        if volume and avg_volume:
            vol_multiplier = watch_config.get('volume_multiplier', 1.5)
            sentiment_pct = watch_config.get('sentiment_pct', 5.0)

            if volume > (avg_volume * vol_multiplier) and pct_change >= sentiment_pct:
                if "volume_breakout" not in ticker_history:
                    msg = (f"🚀 {ticker} HEAVY TRADE ALERT!\n"
                           f"Price: {price} ({pct_change:.2f}% UP)\n"
                           f"Volume: {volume:,} (Avg: {avg_volume:,})\n"
                           f"Source: {quote['source']} at {quote['timestamp_ist']}")
                    alerts.append(msg)
                    ticker_history.append("volume_breakout")

        # Enrich alerts with technicals, delivery %, and news/sentiment
        if alerts:
            enrichment = self._enrich_alert(ticker)
            alerts = [a + enrichment for a in alerts]

        # Update daily cap count based on how many we are actually going to send
        alerts_to_send = []
        for alert in alerts:
            if self.state["alerts_sent_today"] < self.daily_cap:
                alerts_to_send.append(alert)
                self.state["alerts_sent_today"] += 1
            else:
                logger.info("Hit daily cap while generating alerts.")
                break

        if alerts_to_send:
            self._save_state()

        return alerts_to_send
