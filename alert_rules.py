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
