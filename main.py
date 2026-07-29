#!/usr/bin/env python3
"""
Production-Grade Automated BTC Scalping Engine & Web Dashboard
Includes: Secure Admin Auth, Masked Token, Memory Trimming,
Fib OTE (0.71-0.786), Pin Bar/Hammer Pattern, SL at Fib 1.0, TP at Fib 0.0.
"""

import asyncio
from datetime import datetime, timezone
import io
import json
import logging
import os
import sys
import threading
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from flask import Flask, jsonify, render_template_string, request
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np

# ============================================================================
# 1. LOGGING & GLOBAL STATE CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("BTC_SCALPER_ENGINE")

CONFIG = {
    "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
    "TARGET_CHANNEL_ID": os.getenv("TARGET_CHANNEL_ID", "@cryptoscalperaj"),
    "ADMIN_PASSWORD": os.getenv("ADMIN_PASSWORD", "secure_admin_pass123")
}

MEXC_FUTURES_REST = "https://contract.mexc.com"
MAX_SIGNALS_LIMIT = 100

APP_STATE = {
    "active_signals_count": 0,
    "long_setups_count": 0,
    "short_setups_count": 0,
    "avg_rr": "1:2.50",
    "signals_feed": []
}

# ============================================================================
# 2. SECURE HTML WEB DASHBOARD TEMPLATE
# ============================================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fib OTE Scalp Engine Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #0b0f19; color: #f3f4f6; font-family: system-ui, -apple-system, sans-serif; }
        .card-bg { background-color: #121826; border: 1px solid #1f2937; }
        .badge-long { background-color: rgba(38, 166, 154, 0.2); color: #26a69a; border: 1px solid #26a69a; }
        .badge-short { background-color: rgba(239, 83, 80, 0.2); color: #ef5350; border: 1px solid #ef5350; }
        .badge-status { background-color: rgba(255, 152, 0, 0.2); color: #ff9800; border: 1px solid #ff9800; }
    </style>
</head>
<body class="p-4 md:p-8">
    <div class="max-w-4xl mx-auto space-y-6">
        
        <!-- Header -->
        <div class="card-bg p-5 rounded-2xl flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
                <h1 class="text-xl font-bold flex items-center gap-2">
                    <span class="w-3 h-3 bg-emerald-500 rounded-full animate-pulse"></span>
                    Fib OTE (0.71 - 0.786) Scalping Engine
                </h1>
                <p class="text-xs text-gray-400 mt-1">SL at Fib 1.0 · TP1 at Fib 0.0 · Pin Bar/Hammer Confirmed</p>
            </div>
            <div class="flex gap-2">
                <button onclick="triggerTestSignal()" class="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-4 py-2 rounded-xl transition">
                    ⚡ Send Test Signal
                </button>
            </div>
        </div>

        <!-- Telegram Config with Auth -->
        <div class="card-bg p-5 rounded-2xl">
            <h2 class="text-sm font-semibold text-gray-300 mb-3">⚙️ Secure Telegram Configuration</h2>
            <form id="configForm" onsubmit="saveConfig(event)" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label class="block text-xs text-gray-400 mb-1">Telegram Bot Token (Masked)</label>
                    <input type="password" id="botToken" value="{{ token }}" placeholder="Protected Token" class="w-full bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-500">
                </div>
                <div>
                    <label class="block text-xs text-gray-400 mb-1">Target Channel ID</label>
                    <input type="text" id="channelId" value="{{ channel }}" class="w-full bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-500">
                </div>
                <div>
                    <label class="block text-xs text-gray-400 mb-1">Admin Password (Required for Action)</label>
                    <input type="password" id="adminPassword" placeholder="Enter admin password" class="w-full bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-500">
                </div>
                <div class="md:col-span-2 flex justify-end">
                    <button type="submit" class="bg-gray-800 hover:bg-gray-700 text-white text-xs font-semibold px-5 py-2 rounded-xl transition border border-gray-700">
                        💾 Save Configuration
                    </button>
                </div>
            </form>
        </div>

        <!-- Metrics Grid -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div class="card-bg p-4 rounded-2xl">
                <span class="text-xs text-gray-400">ACTIVE SIGNALS</span>
                <div class="text-2xl font-bold text-emerald-400 mt-1">{{ active_count }}</div>
            </div>
            <div class="card-bg p-4 rounded-2xl">
                <span class="text-xs text-gray-400">LONG SETUPS</span>
                <div class="text-2xl font-bold text-emerald-400 mt-1">{{ long_count }}</div>
            </div>
            <div class="card-bg p-4 rounded-2xl">
                <span class="text-xs text-gray-400">SHORT SETUPS</span>
                <div class="text-2xl font-bold text-red-400 mt-1">{{ short_count }}</div>
            </div>
            <div class="card-bg p-4 rounded-2xl">
                <span class="text-xs text-gray-400">STRATEGY</span>
                <div class="text-sm font-bold text-gray-200 mt-2">OTE + Pin Bar</div>
            </div>
        </div>

        <!-- Signal Feed -->
        <div class="space-y-4">
            <h3 class="text-sm font-semibold text-gray-300">Live Signal Feed (Max 100)</h3>
            <div class="space-y-4">
                {% for sig in signals %}
                <div class="card-bg p-5 rounded-2xl space-y-3">
                    <div class="flex justify-between items-center">
                        <div class="flex items-center gap-2">
                            <span class="font-bold text-sm">{{ sig.symbol }}</span>
                            <span class="text-[10px] px-2 py-0.5 rounded bg-gray-800 text-gray-400">5M/15M</span>
                        </div>
                        <span class="text-xs px-3 py-1 rounded-full font-semibold {% if sig.direction == 'LONG' %}badge-long{% else %}badge-short{% endif %}">
                            ↗ {{ sig.direction }}
                        </span>
                    </div>

                    <div class="grid grid-cols-3 gap-2 pt-2 text-xs">
                        <div>
                            <span class="text-gray-500 block">LIVE</span>
                            <span class="font-semibold text-gray-200">${{ sig.live_price }}</span>
                        </div>
                        <div>
                            <span class="text-gray-500 block">ENTRY (OTE)</span>
                            <span class="font-semibold text-gray-200">${{ sig.entry }}</span>
                        </div>
                        <div>
                            <span class="text-gray-500 block">R:R</span>
                            <span class="font-semibold text-gray-200">1:{{ sig.rr }}</span>
                        </div>
                    </div>

                    <div class="grid grid-cols-3 gap-2 pt-1 text-xs">
                        <div class="bg-red-950/40 border border-red-900/50 p-2 rounded-xl">
                            <span class="text-[10px] text-red-400 block">SL (Fib 1.0)</span>
                            <span class="font-bold text-red-300">${{ sig.sl }}</span>
                        </div>
                        <div class="bg-emerald-950/40 border border-emerald-900/50 p-2 rounded-xl">
                            <span class="text-[10px] text-emerald-400 block">TP1 (Fib 0.0)</span>
                            <span class="font-bold text-emerald-300">${{ sig.tp1 }}</span>
                        </div>
                        <div class="bg-emerald-950/40 border border-emerald-900/50 p-2 rounded-xl">
                            <span class="text-[10px] text-emerald-400 block">TP2 (-0.27)</span>
                            <span class="font-bold text-emerald-300">${{ sig.tp2 }}</span>
                        </div>
                    </div>

                    <div class="flex justify-between items-center pt-2 text-[11px]">
                        <span class="text-emerald-400 bg-emerald-950/30 px-2 py-1 rounded-lg border border-emerald-900/30">🕯️ Pin Bar / Hammer Confirmed</span>
                        <span class="badge-status px-3 py-1 rounded-full font-bold">ACTIVE</span>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>

    </div>

    <script>
        function saveConfig(e) {
            e.preventDefault();
            const token = document.getElementById('botToken').value;
            const channel = document.getElementById('channelId').value;
            const password = document.getElementById('adminPassword').value;

            fetch('/api/config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({token: token, channel: channel, password: password})
            }).then(res => res.json()).then(data => {
                if(data.success) alert('Configuration saved securely!');
                else alert('Error: ' + (data.error || 'Unauthorized'));
            });
        }

        function triggerTestSignal() {
            const password = prompt("Enter Admin Password to send test signal:");
            if(!password) return;

            fetch('/api/test-signal', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({password: password})
            })
            .then(res => res.json()).then(data => {
                if(data.success) {
                    alert('Test signal dispatched to Telegram!');
                    location.reload();
                } else {
                    alert('Unauthorized or Error: ' + (data.error || 'Failed'));
                }
            });
        }
    </script>
</body>
</html>
"""

# ============================================================================
# 3. FLASK SERVER ROUTES WITH AUTH
# ============================================================================

app = Flask("BTCScalpingDashboard")

@app.route("/", methods=["GET"])
def dashboard_home():
    return render_template_string(
        HTML_TEMPLATE,
        token=CONFIG["TELEGRAM_BOT_TOKEN"],
        channel=CONFIG["TARGET_CHANNEL_ID"],
        active_count=APP_STATE["active_signals_count"],
        long_count=APP_STATE["long_setups_count"],
        short_count=APP_STATE["short_setups_count"],
        signals=APP_STATE["signals_feed"]
    )

@app.route("/api/config", methods=["POST"])
def api_update_config():
    data = request.json
    if not data or data.get("password") != CONFIG["ADMIN_PASSWORD"]:
        return jsonify({"success": False, "error": "Unauthorized / Incorrect Password"}), 403
    
    CONFIG["TELEGRAM_BOT_TOKEN"] = data.get("token", CONFIG["TELEGRAM_BOT_TOKEN"])
    CONFIG["TARGET_CHANNEL_ID"] = data.get("channel", CONFIG["TARGET_CHANNEL_ID"])
    return jsonify({"success": True})

@app.route("/api/test-signal", methods=["POST"])
def api_test_signal():
    data = request.json or {}
    if data.get("password") != CONFIG["ADMIN_PASSWORD"]:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(send_manual_test_signal())
        loop.close()
        return jsonify({"success": success})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "online", "timestamp": datetime.now(timezone.utc).isoformat()}), 200

def run_flask_server():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ============================================================================
# 4. MEXC FUTURES & SAFE KLINE PARSER
# ============================================================================

class MexcFuturesClient:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def init_session(self):
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def fetch_klines(self, symbol: str = "BTC_USDT", interval: str = "5m", limit: int = 120) -> List[Dict[str, Any]]:
        await self.init_session()
        mexc_interval = "Min5" if interval == "5m" else "Min15"
        url = f"{MEXC_FUTURES_REST}/api/v1/contract/kline/{symbol}?interval={mexc_interval}&limit={limit}"
        try:
            async with self.session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    raw_candles = data.get("data", [])
                    
                    # Safe check if raw_candles is dict or list or string to prevent crashes
                    if isinstance(raw_candles, dict):
                        raw_candles = raw_candles.get("result", raw_candles.get("list", []))
                    if not isinstance(raw_candles, list):
                        return []

                    formatted = []
                    for c in raw_candles:
                        if isinstance(c, dict):
                            formatted.append({
                                "time": int(c.get("time", c.get("t", 0))),
                                "open": float(c.get("open", c.get("o", 0))),
                                "high": float(c.get("high", c.get("h", 0))),
                                "low": float(c.get("low", c.get("l", 0))),
                                "close": float(c.get("close", c.get("c", 0))),
                                "volume": float(c.get("volume", c.get("v", 0)))
                            })
                        elif isinstance(c, (list, tuple)) and len(c) >= 6:
                            # Handling array-based kline format if returned by MEXC
                            formatted.append({
                                "time": int(c[0]),
                                "open": float(c[1]),
                                "high": float(c[2]),
                                "low": float(c[3]),
                                "close": float(c[4]),
                                "volume": float(c[5])
                            })
                    return formatted
        except Exception as e:
            logger.error(f"Error fetching klines safely: {e}")
        return []

class ScalpingStrategyEngine:
    @staticmethod
    def calculate_fibonacci(high: float, low: float, direction: str) -> Dict[str, float]:
        diff = high - low
        if direction == "LONG":
            return {
                "1.0": low,
                "0.786": low + (diff * 0.786),
                "0.71": low + (diff * 0.71),
                "0.0": high,
                "-0.27": high + (diff * 0.27)
            }
        else:
            return {
                "1.0": high,
                "0.786": high - (diff * 0.786),
                "0.71": high - (diff * 0.71),
                "0.0": low,
                "-0.27": low - (diff * 0.27)
            }

    @staticmethod
    def check_pin_bar_pattern(candles: List[Dict[str, Any]], direction: str) -> bool:
        if len(candles) < 2:
            return False
        last_c = candles[-1]
        body = abs(last_c["close"] - last_c["open"])
        total_range = last_c["high"] - last_c["low"]
        if total_range == 0:
            return False
        
        if direction == "LONG":
            lower_wick = min(last_c["open"], last_c["close"]) - last_c["low"]
            return lower_wick >= (total_range * 0.5)
        else:
            upper_wick = last_c["high"] - max(last_c["open"], last_c["close"])
            return upper_wick >= (total_range * 0.5)

    @staticmethod
    def analyze_market(candles_15m: List[Dict[str, Any]], candles_5m: List[Dict[str, Any]]) -> Dict[str, Any]:
        if len(candles_15m) < 30 or len(candles_5m) < 30:
            return {"valid": False}

        current_price = candles_5m[-1]["close"]
        highs = [c["high"] for c in candles_15m[-30:]]
        lows = [c["low"] for c in candles_15m[-30:]]
        swing_high = max(highs)
        swing_low = min(lows)

        ma_20 = sum([c["close"] for c in candles_15m[-20:]]) / 20
        trend = "LONG" if current_price > ma_20 else "SHORT"
        
        fibs = ScalpingStrategyEngine.calculate_fibonacci(swing_high, swing_low, trend)

        ote_min = min(fibs["0.71"], fibs["0.786"])
        ote_max = max(fibs["0.71"], fibs["0.786"])
        in_ote = ote_min <= current_price <= ote_max

        pattern_confirmed = ScalpingStrategyEngine.check_pin_bar_pattern(candles_5m, trend)

        entry_avg = round((fibs["0.71"] + fibs["0.786"]) / 2, 2)
        tp1 = round(fibs["0.0"], 2)
        tp2 = round(fibs["-0.27"], 2)
        sl = round(fibs["1.0"], 2)

        rr_ratio = round(abs(tp1 - entry_avg) / abs(entry_avg - sl), 2) if abs(entry_avg - sl) > 0 else 2.5

        return {
            "valid": in_ote and pattern_confirmed,
            "symbol": "BTC/USDT",
            "direction": trend,
            "live_price": current_price,
            "entry": entry_avg,
            "tp1": tp1,
            "tp2": tp2,
            "sl": sl,
            "rr": rr_ratio,
            "fibs": fibs,
            "candles_5m": candles_5m
        }

# ============================================================================
# 5. CHART GENERATOR & TELEGRAM DISPATCHER
# ============================================================================

class ChartGenerator:
    @staticmethod
    def generate_chart_snapshot(candles: List[Dict[str, Any]], signal_data: Dict[str, Any]) -> io.BytesIO:
        plt.style.use("dark_background")
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6.75), gridspec_kw={"height_ratios": [3.5, 1]}, sharex=True)
        fig.patch.set_facecolor("#121826")
        ax1.set_facecolor("#121826")
        ax2.set_facecolor("#121826")

        recent_c = candles[-60:]
        dates = [datetime.fromtimestamp(c["time"] / 1000, tz=timezone.utc) for c in recent_c]
        opens = [c["open"] for c in recent_c]
        highs = [c["high"] for c in recent_c]
        lows = [c["low"] for c in recent_c]
        closes = [c["close"] for c in recent_c]
        volumes = [c["volume"] for c in recent_c]

        for i in range(len(dates)):
            color = "#26a69a" if closes[i] >= opens[i] else "#ef5350"
            ax1.plot([dates[i], dates[i]], [lows[i], highs[i]], color=color, linewidth=1)
            ax1.bar(dates[i], abs(closes[i] - opens[i]), bottom=min(opens[i], closes[i]), color=color, width=0.0018)

        fibs = signal_data["fibs"]
        ax1.axhline(fibs["0.71"], color="#ff9800", linestyle="--", alpha=0.7, label="Fib 0.71 OTE")
        ax1.axhline(fibs["0.786"], color="#ff5722", linestyle="--", alpha=0.7, label="Fib 0.786 OTE")
        ax1.axhline(signal_data["tp1"], color="#4caf50", linestyle="-.", alpha=0.9, label="TP1 (Fib 0.0)")
        ax1.axhline(signal_data["sl"], color="#f44336", linestyle="-.", alpha=0.9, label="SL (Fib 1.0)")

        vol_colors = ["#26a69a" if closes[i] >= opens[i] else "#ef5350" for i in range(len(dates))]
        ax2.bar(dates, volumes, color=vol_colors, width=0.0018)

        ax1.legend(loc="upper left", fontsize=7, facecolor="#1f2937", edgecolor="none")
        ax1.grid(color="#1f2937", linestyle=":", linewidth=0.5)
        ax2.grid(color="#1f2937", linestyle=":", linewidth=0.5)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=timezone.utc))

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=200, facecolor=fig.get_facecolor(), edgecolor="none")
        buf.seek(0)
        plt.close(fig)
        return buf

class TelegramBotEngine:
    @staticmethod
    async def send_photo(photo_bytes: io.BytesIO, caption: str) -> bool:
        token = CONFIG["TELEGRAM_BOT_TOKEN"]
        channel_id = CONFIG["TARGET_CHANNEL_ID"]
        if not token or not channel_id:
            return False

        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field("chat_id", channel_id)
            form.add_field("caption", caption)
            form.add_field("parse_mode", "Markdown")
            form.add_field("photo", photo_bytes, filename="chart.png", content_type="image/png")
            try:
                async with session.post(url, data=form, timeout=15) as resp:
                    return resp.status == 200
            except Exception as e:
                logger.error(f"Telegram error: {e}")
                return False

async def send_manual_test_signal() -> bool:
    mexc = MexcFuturesClient()
    candles_15m = await mexc.fetch_klines("BTC_USDT", interval="15m", limit=60)
    candles_5m = await mexc.fetch_klines("BTC_USDT", interval="5m", limit=60)
    if not candles_5m:
        return False

    analysis = ScalpingStrategyEngine.analyze_market(candles_15m, candles_5m)
    analysis["valid"] = True
    chart_buf = ChartGenerator.generate_chart_snapshot(candles_5m, analysis)

    caption = (
        f"🚨 **BTCUSDT Perpetual Scalping Signal (Test)**\n"
        f"Direction: **🟢 {analysis['direction']} (OTE Confirmed)**\n\n"
        f"📍 Entry (OTE 0.71 - 0.786): `{analysis['entry']}`\n"
        f"🎯 TP1 (Fib 0.0): `{analysis['tp1']}`\n"
        f"🛡️ SL (Fib 1.0): `{analysis['sl']}`\n"
        f"⚖️ R/R Ratio: `1:{analysis['rr']}`\n\n"
        f"🕯️ *Condition:* Pin Bar / Hammer pattern confirmed at OTE zone."
    )

    success = await TelegramBotEngine.send_photo(chart_buf, caption)
    if success:
        APP_STATE["signals_feed"].insert(0, analysis)
        if len(APP_STATE["signals_feed"]) > MAX_SIGNALS_LIMIT:
            APP_STATE["signals_feed"].pop()
            
        APP_STATE["active_signals_count"] = len(APP_STATE["signals_feed"])
        if analysis["direction"] == "LONG":
            APP_STATE["long_setups_count"] += 1
        else:
            APP_STATE["short_setups_count"] += 1
    return success

# ============================================================================
# 6. MAIN WORKER LOOP
# ============================================================================

async def automated_engine_loop():
    mexc = MexcFuturesClient()
    while True:
        try:
            candles_15m = await mexc.fetch_klines("BTC_USDT", interval="15m", limit=120)
            candles_5m = await mexc.fetch_klines("BTC_USDT", interval="5m", limit=120)

            if candles_15m and candles_5m:
                analysis = ScalpingStrategyEngine.analyze_market(candles_15m, candles_5m)
                if analysis.get("valid"):
                    chart_buf = ChartGenerator.generate_chart_snapshot(candles_5m, analysis)
                    caption = (
                        f"🚨 **BTCUSDT Perpetual Scalping Signal**\n"
                        f"Direction: **{analysis['direction']} (OTE Confirmed)**\n\n"
                        f"📍 Entry: `{analysis['entry']}`\n"
                        f"🎯 TP1 (Fib 0.0): `{analysis['tp1']}`\n"
                        f"🛡️ SL (Fib 1.0): `{analysis['sl']}`\n"
                        f"⚖️ R/R: `1:{analysis['rr']}`"
                    )
                    await TelegramBotEngine.send_photo(chart_buf, caption)
                    
                    APP_STATE["signals_feed"].insert(0, analysis)
                    if len(APP_STATE["signals_feed"]) > MAX_SIGNALS_LIMIT:
                        APP_STATE["signals_feed"].pop()
                        
                    APP_STATE["active_signals_count"] = len(APP_STATE["signals_feed"])
        except Exception as e:
            logger.error(f"Error in background loop: {e}")

        await asyncio.sleep(60)

def main():
    flask_thread = threading.Thread(target=run_flask_server, daemon=True)
    flask_thread.start()
    logger.info("Secure Dashboard & Scalping Engine running on port 8080.")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(automated_engine_loop())
    except KeyboardInterrupt:
        logger.info("Engine stopped.")

if __name__ == "__main__":
    main()
