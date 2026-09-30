# NSE Stock Alert Tool (Phase 1)

A lightweight Python worker that fetches stock prices for the Indian market (NSE) and sends simple Telegram alerts based on basic rules (threshold % movement, support, resistance).

This tool is designed for **delivery (multi-day) trading** where you do not need ultra-fast intraday responses. It runs via GitHub Actions on a schedule.

**Important Note**: GitHub cron schedules are not guaranteed to run precisely on time. They can run several minutes late or sometimes be skipped during peak GitHub loads. Therefore, this tool should NOT be used for fast intraday trading or split-second decisions.

## Features
- **Fallback Data Sources**: Tries `jugaad-data`, then `nsepython`, and finally falls back to `yfinance` to avoid failing if NSE blocks a cloud IP.
- **Anti-Spam**: Caps alerts per rule, per stock, per day. Stores state in `state.json` to prevent spam during overlap.
- **Configurable Rules**: Alerts on price % moves and crosses above/below support/resistance levels.
- **Market Hours Awareness**: Skips runs outside 9:15 AM - 3:30 PM IST on Monday-Friday.

## Prerequisites
1. A GitHub account.
2. A Telegram account.

## Setup Instructions

### 1. Create a Telegram Bot
1. Open Telegram and search for `@BotFather`.
2. Send the command `/newbot` and follow the instructions to name your bot and choose a username.
3. BotFather will give you a **Bot Token** (looks like `123456789:ABCDEF...`). Save this securely.

### 2. Find Your Chat ID
1. Search for your newly created bot in Telegram and click **Start** (or send any message).
2. Open a web browser and go to: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. Look for the `"chat":{"id": 123456789}` in the JSON response. The number is your **Chat ID**. (If it's empty, send another message to your bot and refresh the page).

### 3. Add GitHub Secrets
1. Fork or upload this repository to your GitHub account.
2. Go to your repository's **Settings** -> **Secrets and variables** -> **Actions**.
3. Click **New repository secret**.
4. Add `TELEGRAM_BOT_TOKEN` with your bot token.
5. Add `TELEGRAM_CHAT_ID` with your chat ID.

### 4. Enable the Workflow
1. Go to the **Actions** tab in your repository.
2. Click **I understand my workflows, go ahead and enable them**.
3. Select **NSE Stock Alert Tool** from the left menu.
4. Click **Run workflow** -> **Run workflow** to test it manually.

### 5. Configure Your Watchlist
Edit `watchlist.json` to add your stocks. You can add up to 10 stocks.
```json
[
  {
    "ticker": "TCS",
    "name": "Tata Consultancy Services",
    "threshold_pct": 3.0,
    "support": 1900,
    "resistance": 2200
  }
]
```

## Testing Locally
If you want to test the script on your computer without sending Telegram messages, you can use the `--dry-run` flag.

1. Install Python 3.11+.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run test mode (sends one message to verify bot):
   ```bash
   export TELEGRAM_BOT_TOKEN="your_token"
   export TELEGRAM_CHAT_ID="your_chat_id"
   python main.py --test-msg
   ```
4. Run locally and see what alerts *would* trigger:
   ```bash
   python main.py --dry-run --force
   ```
   *(Note: `--force` bypasses the market hours check)*

## Running Unit Tests
```bash
pytest tests/
```
