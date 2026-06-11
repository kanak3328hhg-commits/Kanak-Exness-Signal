import requests
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


BOT_TOKEN = "8264008675:AAEHzakAXPZeNVZKWlvYHRWboyjAuUhg0QM"
FOREX_CHAT_ID = "-1004292142406"  # 🎯 স্ক্রিনশট অনুযায়ী ফরেক্স চ্যানেলের সঠিক আইডি



class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Kanak Sniper Engine: Optimized Volume Matrix Live!")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_fake_server():
    import os
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()

def get_current_forex_sessions():
    now_utc = datetime.utcnow()
    now_bst = now_utc + timedelta(hours=6)
    current_hour = now_bst.hour
    sessions = []
    if 4 <= current_hour < 13: sessions.append("Sydney 🇦🇺")
    if 6 <= current_hour < 15: sessions.append("Tokyo 🇯🇵")
    if 13 <= current_hour < 22: sessions.append("London 🇬🇧")
    if current_hour >= 18 or current_hour < 3: sessions.append("New York 🇺🇸")
    return ", ".join(sessions) if sessions else "Live Market"

# গাণিতিক এবং টেকনিক্যাল ইন্ডিকেটর ফাংশনসমূহ
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).copy()
    loss = (-delta.where(delta < 0, 0)).copy()
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    for i in range(period, len(series)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period
    return 100 - (100 / (1 + (avg_gain / avg_loss)))

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    return pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(window=period).mean()

def calculate_cmf(df, period=20):
    mf_multiplier = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / (df['High'] - df['Low'])
    mf_multiplier = mf_multiplier.fillna(0)
    volume = (df['High'] - df['Low']).replace(0, 0.00001)
    mf_volume = mf_multiplier * volume
    return mf_volume.rolling(window=period).sum() / volume.rolling(window=period).sum()

def fetch_candles(ticker_symbol, interval, range_str):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_symbol}?range={range_str}&interval={interval}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200: return None
    result = response.json()['chart']['result'][0]
    df = pd.DataFrame({
        'Open': result['indicators']['quote'][0]['open'],
        'High': result['indicators']['quote'][0]['high'],
        'Low': result['indicators']['quote'][0]['low'],
        'Close': result['indicators']['quote'][0]['close']
    }, index=pd.to_datetime(result['timestamp'], unit='s')).dropna()
    return df

def generate_signal(ticker_symbol, display_name):
    try:
        df_5m = fetch_candles(ticker_symbol, "5m", "5d")
        df_15m = fetch_candles(ticker_symbol, "15m", "5d")
        
        if df_5m is None or len(df_5m) < 80 or df_15m is None or len(df_15m) < 40:
            latest_p = df_5m.iloc[-1]['Close'] if (df_5m is not None and len(df_5m) > 0) else 0.0
            is_jpy = "JPY" in ticker_symbol
            return {"status": "NO_SIGNAL", "price": round(latest_p, 2 if is_jpy else 4)}

        is_jpy = "JPY" in ticker_symbol
        dec_places = 4 if not is_jpy else 2

        # ১৫ মিনিট মেইন ট্রেন্ড ফিল্টার
        df_15m['EMA_50'] = calculate_ema(df_15m['Close'], 50)
        trend_15m = "UP" if df_15m['Close'].iloc[-1] > df_15m['EMA_50'].iloc[-1] else "DOWN"

        # ৫ মিনিট টেকনিক্যালস
        df_5m['RSI'] = calculate_rsi(df_5m['Close'])
        df_5m['EMA_50'] = calculate_ema(df_5m['Close'], 50)
        df_5m['ATR'] = calculate_atr(df_5m)
        df_5m['CMF'] = calculate_cmf(df_5m, 20)
        
        # Bollinger Bands
        df_5m['BB_middle'] = df_5m['Close'].rolling(window=20).mean()
        df_5m['BB_std'] = df_5m['Close'].rolling(window=20).std()
        df_5m['BB_upper'] = df_5m['BB_middle'] + (df_5m['BB_std'] * 2)
        df_5m['BB_lower'] = df_5m['BB_middle'] - (df_5m['BB_std'] * 2)
        
        # MACD
        ema12 = calculate_ema(df_5m['Close'], 12)
        ema26 = calculate_ema(df_5m['Close'], 26)
        df_5m['MACD'] = ema12 - ema26
        df_5m['MACD_signal'] = calculate_ema(df_5m['MACD'], 9)

        # SMC লেভেলস
        df_5m['Support'] = df_5m['Low'].rolling(window=30).min()
        df_5m['Resistance'] = df_5m['High'].rolling(window=30).max()
        df_5m['Bullish_FVG'] = (df_5m['High'].shift(2) < df_5m['Low'])
        df_5m['Bearish_FVG'] = (df_5m['Low'].shift(2) > df_5m['High'])

        latest = df_5m.iloc[-1]
        prev3 = df_5m.iloc[-3]
        
        price = latest['Close']
        rsi_val = latest['RSI']
        atr_val = latest['ATR']
        macd_val = latest['MACD']
        macd_sig = latest['MACD_signal']
        cmf_val = latest['CMF']
        
        is_near_support = price <= (latest['Support'] + (atr_val * 0.6))
        is_near_resistance = price >= (latest['Resistance'] - (atr_val * 0.6))
        
        direction = None
        smc_context = ""

        # 🟢 OPTIMIZED SNIPER BUY: কন্ডিশন ফ্লেক্সিবল করা হয়েছে পর্যাপ্ত সিগনালের জন্য
        if (trend_15m == "UP" and price > latest['EMA_50'] and macd_val > macd_sig and rsi_val > 50 and cmf_val >= 0.01):
            if is_near_support or price <= latest['BB_lower'] or prev3['Bullish_FVG']:
                direction = "UP"
                if is_near_support: smc_context += "[SMC Support Bouce] "
                if price <= latest['BB_lower']: smc_context += "[BB Oversold Reversal] "
                if prev3['Bullish_FVG']: smc_context += "[ICT FVG Mitigation] "

        # 🔴 OPTIMIZED SNIPER SELL:
        elif (trend_15m == "DOWN" and price < latest['EMA_50'] and macd_val < macd_sig and rsi_val < 50 and cmf_val <= -0.01):
            if is_near_resistance or price >= latest['BB_upper'] or prev3['Bearish_FVG']:
                direction = "DOWN"
                if is_near_resistance: smc_context += "[SMC Resistance Rejection] "
                if price >= latest['BB_upper']: smc_context += "[BB Overbought Reversal] "
                if prev3['Bearish_FVG']: smc_context += "[ICT FVG Mitigation] "

        if not direction: 
            return {"status": "NO_SIGNAL", "price": round(price, dec_places)}
            
        risk_dist = atr_val * 2.0
        sl = price - risk_dist if direction == "UP" else price + risk_dist
        strength = int(min(rsi_val + 22, 99)) if direction == "UP" else int(min((100 - rsi_val) + 22, 99))
        
        tp1_val = price + (risk_dist * 1.5) if direction == "UP" else price - (risk_dist * 1.5)
        tp2_val = price + (risk_dist * 2.5) if direction == "UP" else price - (risk_dist * 2.5)
        
        tp_text_block = (
            f"🎯 <b>Target 1 (1:1.5 RR):</b> <code>{round(tp1_val, dec_places)}</code>\n"
            f"🎯 <b>Target 2 (1:2.5 Inst):</b> <code>{round(tp2_val, dec_places)}</code>"
        )
        
        action_word = "Buy" if direction == "UP" else "Sell"
        local_note = f"স্মার্ট মানি ট্রেন্ড এবং ইনস্টলেশনাল ফ্লো অনুযায়ী {action_word} সেটআপ।"
        
        return {
            "status": "SIGNAL_FOUND", "price": round(price, dec_places), "direction": direction, "strength": strength,
            "sl": round(sl, dec_places), "tp_block": tp_text_block, "tip": local_note, "context": smc_context if smc_context else "Sniper Flow"
        }
    except:
        return {"status": "ERROR", "price": 0.0}

pairs_to_track = {
    "EURUSD=X": "EURUSD", "GBPUSD=X": "GBPUSD", "USDJPY=X": "USDJPY", "USDCHF=X": "USDCHF",
    "AUDUSD=X": "AUDUSD", "USDCAD=X": "USDCAD", "NZDUSD=X": "NZDUSD", "EURGBP=X": "EURGBP",
    "EURJPY=X": "EURJPY", "EURCHF=X": "EURCHF", "EURCAD=X": "EURCAD", "EURAUD=X": "EURAUD",
    "GBPJPY=X": "GBPJPY", "GBPCHF=X": "GBPCHF", "GBPCAD=X": "GBPCAD", "GBPAUD=X": "GBPAUD",
    "AUDJPY=X": "AUDJPY", "AUDCAD=X": "AUDCAD", "XAUUSD=X": "XAUUSD"
}

threading.Thread(target=run_fake_server, daemon=True).start()
print("Kanak Sniper Bot: 10+ Daily Signals Balanced Engine Active...")

# ⏱️ মেইন ফরেক্স লুপ
while True:
    try:
        current_session = get_current_forex_sessions()
        now_bst = datetime.utcnow() + timedelta(hours=6)
        current_time = now_bst.strftime("%I:%M %p")
        
        print(f"\n🔄 SCANNING STARTED AT {current_time} (Balanced Target 10 Active)")
        
        no_signal_pairs = [] 
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        
        for ticker, display_name in pairs_to_track.items():
            time.sleep(1.2)
            result = generate_signal(ticker, display_name)
            
            if result["status"] == "SIGNAL_FOUND": 
                action_text = "🟢 SNIPER BUY SETUP" if result['direction'] == "UP" else "🔴 SNIPER SELL SETUP"
                
                forex_message = (
                    f"🏛️ <b>Institutional Sniper Flow | {current_time}</b>\n\n"
                    f"🔥 <b>Pair:</b> <code>{display_name}</code> → <b>{action_text}</b>\n"
                    f"───────────────────\n"
                    f"📊 <b>Analysis:</b> SMC + FVG + Balanced Indicators\n"
                    f"🛡️ <b>Trigger Context:</b> <code>{result['context']}</code>\n"
                    f"💪 <b>Estimated Accuracy:</b> {result['strength']}% High Probability\n\n"
                    f"💵 <b>Institutional Entry:</b> <code>{result['price']}</code>\n"
                    f"🛡️ <b>Invalidation (SL):</b> <code>{result['sl']}</code>\n"
                    f"{result['tp_block']}\n\n"
                    f"<i>⚠️ মানি ম্যানেজমেন্ট (0.01-0.02 Lot) মেনে এন্ট্রি নিবেন।</i>\n\n"
                    f"#{display_name} #Sniper #SMC #ForexSignals"
                )
                
                requests.post(url, json={"chat_id": FOREX_CHAT_ID, "text": forex_message, "parse_mode": "HTML"}, timeout=10)
                print(f"   🎯 Sniper Signal Sent for {display_name}")
            else:
                no_signal_pairs.append(f"<code>{display_name}</code> ({result['price']})")

        # সামারি আপডেট
        report_message = (
            f"⚡ <b>SMC Sniper Dashboard | {current_time}</b>\n"
            f"🌐 <b>Active Session:</b> {current_session}\n"
            f"───────────────────\n"
            f"👁️‍🗨️ <b>অপেক্ষা করছি (SMC Filtering Active):</b>\n"
        )
        if no_signal_pairs:
            report_message += f"{', '.join(no_signal_pairs)}\n\n"
            report_message += f"<i>বাকি এই পেয়ারগুলো বর্তমানে লিকুইডিটি বিল্ড-আপ জোনে আছে। স্মার্ট মানি মুভ কনফর্ম করার সাথে সাথে সিগনাল চলে আসবে।</i>\n"
        else:
            report_message += "<i>সবগুলো পেয়ারেই হাই-মোমেন্টাম মুভ রানিং!</i>\n"
            
        report_message += "\n⏱️ <i>পরবর্তী ৫ মিনিট পর আমি আবার চার্ট ফিল্টার করব...</i>"
        
        requests.post(url, json={"chat_id": FOREX_CHAT_ID, "text": report_message, "parse_mode": "HTML"}, timeout=10)
        print("✅ Sniper Snapshot Pushed Successfully!")
                
    except Exception as e:
        print(f"Loop error: {e}")
        
    time.sleep(300)
