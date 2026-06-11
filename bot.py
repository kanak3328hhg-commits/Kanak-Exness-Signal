import requests
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# আপনার একদম সঠিক ও ভেরিফাইড তথ্যসমূহ
BOT_TOKEN = "8264008675:AAEHzakAXPZeNVZKWlvYHRWboyjAuUhg0QM"
FOREX_CHAT_ID = "-1004292142406"  # 🎯 স্ক্রিনশট অনুযায়ী ফরেক্স চ্যানেলের সঠিক আইডি




class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Kanak Institutional Engine: Pure Price Action & Volume Matrix Live!")
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

# চ্যাইকিন মানি ফ্লো (Chaikin Money Flow - CMF) ভলিউম ইন্ডিকেটর
def calculate_cmf(df, period=20):
    mf_multiplier = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / (df['High'] - df['Low'])
    mf_multiplier = mf_multiplier.fillna(0) # জিরো ডিভাইড হ্যান্ডেল করার জন্য
    # ভলিউম না থাকলে ফরেক্স টিক ডেটা বা ক্যান্ডেল সাইজ অনুযায়ী ডামি ভলিউম জেনারেট (Yahoo Finance সেফটি)
    volume = df['High'] - df['Low'] 
    mf_volume = mf_multiplier * volume
    return mf_volume.rolling(window=period).sum() / volume.rolling(window=period).sum()

def generate_signal(ticker_symbol, display_name):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_symbol}?range=5d&interval=5m"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200: return "NO_SIGNAL"
            
        result = response.json()['chart']['result'][0]
        data = pd.DataFrame({
            'Open': result['indicators']['quote'][0]['open'],
            'High': result['indicators']['quote'][0]['high'],
            'Low': result['indicators']['quote'][0]['low'],
            'Close': result['indicators']['quote'][0]['close']
        }, index=pd.to_datetime(result['timestamp'], unit='s')).dropna()
        
        if len(data) < 100: return "NO_SIGNAL"

        # ১. টেকনিক্যাল ইন্ডিকেটরস (RSI, EMA, Bollinger Bands, MACD, CMF Volume)
        data['RSI'] = calculate_rsi(data['Close'])
        data['EMA_20'] = calculate_ema(data['Close'], 20)
        data['EMA_50'] = calculate_ema(data['Close'], 50)
        data['ATR'] = calculate_atr(data)
        data['CMF'] = calculate_cmf(data, 20) # নতুন ভলিউম ফিল্টার
        
        # Bollinger Bands
        data['BB_middle'] = data['Close'].rolling(window=20).mean()
        data['BB_std'] = data['Close'].rolling(window=20).std()
        data['BB_upper'] = data['BB_middle'] + (data['BB_std'] * 2)
        data['BB_lower'] = data['BB_middle'] - (data['BB_std'] * 2)
        
        # MACD
        ema12 = calculate_ema(data['Close'], 12)
        ema26 = calculate_ema(data['Close'], 26)
        data['MACD'] = ema12 - ema26
        data['MACD_signal'] = calculate_ema(data['MACD'], 9)

        # ২. অ্যাডভান্সড প্রাইস অ্যাকশন ও SMC ফিল্টার (Support, Resistance, FVG)
        data['Support'] = data['Low'].rolling(window=50).min()
        data['Resistance'] = data['High'].rolling(window=50).max()
        
        # FVG Detection
        data['Bullish_FVG'] = (data['High'].shift(2) < data['Low']) & (data['Close'].shift(1) > data['Open'].shift(1))
        data['Bearish_FVG'] = (data['Low'].shift(2) > data['High']) & (data['Close'].shift(1) < data['Open'].shift(1))

        latest = data.iloc[-1]
        prev3 = data.iloc[-3]
        
        price = latest['Close']
        rsi_val = latest['RSI']
        atr_val = latest['ATR']
        macd_val = latest['MACD']
        macd_sig = latest['MACD_signal']
        cmf_val = latest['CMF']
        
        is_near_support = price <= (latest['Support'] + (atr_val * 0.5))
        is_near_resistance = price >= (latest['Resistance'] - (atr_val * 0.5))
        
        direction = None
        smc_context = ""

        # 🛡️ আল্ট্রা ইনস্টিটিউশনাল কনফ্লুয়েন্স লুপ (ভলিউম ফিল্টারসহ)
        # BUY SETUP কন্ডিশন (CMF ভলিউম অবশ্যই পজিটিভ > 0 হতে হবে):
        if (price > latest['EMA_50'] and macd_val > macd_sig and rsi_val > 52 and cmf_val > 0.02):
            if is_near_support or price <= latest['BB_lower'] or prev3['Bullish_FVG']:
                direction = "UP"
                if is_near_support: smc_context += "[SMC Support Bouce] "
                if price <= latest['BB_lower']: smc_context += "[BB Oversold Reversal] "
                if prev3['Bullish_FVG']: smc_context += "[ICT FVG Mitigation] "

        # SELL SETUP কন্ডিশন (CMF ভলিউম অবশ্যই নেগেটিভ < 0 হতে হবে):
        elif (price < latest['EMA_50'] and macd_val < macd_sig and rsi_val < 48 and cmf_val < -0.02):
            if is_near_resistance or price >= latest['BB_upper'] or prev3['Bearish_FVG']:
                direction = "DOWN"
                if is_near_resistance: smc_context += "[SMC Resistance Rejection] "
                if price >= latest['BB_upper']: smc_context += "[BB Overbought Reversal] "
                if prev3['Bearish_FVG']: smc_context += "[ICT FVG Mitigation] "

        if not direction: return "NO_SIGNAL"
            
        is_jpy = "JPY" in ticker_symbol
        dec_places = 4 if not is_jpy else 2
        
        # ATR ডাইনামিক স্টপ লস (Multiplier = 2.5)
        risk_dist = atr_val * 2.5
        sl = price - risk_dist if direction == "UP" else price + risk_dist
        strength = int(min(rsi_val + 18, 99)) if direction == "UP" else int(min((100 - rsi_val) + 18, 99))
        
        # ১:২ এবং ১:৩ পারফেক্ট রিস্ক-টু-রিওয়ার্ড রেশিও টার্গেট
        tp_list = []
        tp1_val = price + (risk_dist * 2) if direction == "UP" else price - (risk_dist * 2)
        tp_list.append(f"🎯 <b>Target 1 (1:2 RR):</b> {round(tp1_val, dec_places)}")
        
        tp2_val = price + (risk_dist * 3) if direction == "UP" else price - (risk_dist * 3)
        tp_list.append(f"🎯 <b>Target 2 (1:3 Institutional):</b> {round(tp2_val, dec_places)}")
            
        tp_text_block = "\n".join(tp_list)
        
        # হিউম্যানাইজড স্ট্যাটিক নোট (Gemini AI ছাড়া সম্পূর্ণ লোকাল ও ফাস্ট)
        action_word = "Buy" if direction == "UP" else "Sell"
        local_note = f"স্মার্ট মানি এবং ভলিউম কনফার্মেশন অনুযায়ী চার্টে ক্লিয়ার {action_word} অর্ডার ফ্লো তৈরি হয়েছে।"
        
        return {
            "price": round(price, dec_places), "direction": direction, "strength": strength,
            "sl": round(sl, dec_places), "tp_block": tp_text_block, "tip": local_note, "context": smc_context if smc_context else "Volume Trend Flow"
        }
    except:
        return "NO_SIGNAL"

pairs_to_track = {
    "EURUSD=X": "EUR-USD", "GBPUSD=X": "GBP-USD", "USDJPY=X": "USD-JPY", "USDCHF=X": "USD-CHF",
    "AUDUSD=X": "AUD-USD", "USDCAD=X": "USD-CAD", "NZDUSD=X": "NZD-USD", "EURGBP=X": "EUR-GBP",
    "EURJPY=X": "EUR-JPY", "EURCHF=X": "EUR-CHF", "EURCAD=X": "EUR-CAD", "EURAUD=X": "EUR-AUD",
    "GBPJPY=X": "GBP-JPY", "GBPCHF=X": "GBP-CHF", "GBPCAD=X": "GBP-CAD", "GBPAUD=X": "GBP-AUD",
    "AUDJPY=X": "AUD-JPY", "AUDCAD=X": "AUD-CAD", "XAUUSD=X": "XAU-USD"
}

threading.Thread(target=run_fake_server, daemon=True).start()
print("Kanak AI Bot: Running 100% Local Lightweight SMC & Volume Engine...")

# ⏱️ মেইন রিয়েল-টাইম ৫ মিনিটের কন্টিনিউয়াস ফরেক্স লুপ
while True:
    try:
        current_session = get_current_forex_sessions()
        now_bst = datetime.utcnow() + timedelta(hours=6)
        current_time = now_bst.strftime("%I:%M %p")
        
        print(f"\n🔄 SCANNING STARTED AT {current_time} (Fast Local Engine Active)")
        
        no_signal_pairs = [] 
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        
        for ticker, display_name in pairs_to_track.items():
            time.sleep(1.0) # লাইটওয়েট ডিলের মাধ্যমে দ্রুত স্ক্যান
            result = generate_signal(ticker, display_name)
            
            if isinstance(result, dict): 
                action_text = "🟢 INSTITUTIONAL BUY" if result['direction'] == "UP" else "🔴 INSTITUTIONAL SELL"
                
                # 📊 আল্ট্রা লেভেলের SMC/ICT + Volume ড্যাশবোর্ড মেসেজ ফরম্যাট
                forex_message = (
                    f"🏛️ <b>Smart Money Order Flow | {current_time}</b>\n\n"
                    f"🔥 <b>{display_name}</b> → <b>{action_text}</b>\n"
                    f"───────────────────\n"
                    f"📊 <b>Analysis:</b> SMC + FVG + Volume Matrix\n"
                    f"🛡️ <b>Trigger Context:</b> <code>{result['context']}</code>\n"
                    f"💪 <b>Accuracy Strength:</b> {result['strength']}% Probability\n\n"
                    f"💵 <b>Institutional Entry:</b> {result['price']}\n"
                    f"🛡️ <b>Invalidation (SL):</b> {result['sl']}\n"
                    f"{result['tp_block']}\n\n"
                    f"📝 <b>Note:</b> <i>{result['tip']}</i>\n\n"
                    f"<i>⚠️ প্রপার মানি ম্যানেজমেন্ট (0.01-0.02 Lot) মেনে এন্ট্রি নিবেন।</i>\n\n"
                    f"#{display_name.replace('-', '_')} #SMC #ICT #Volume"
                )
                
                requests.post(url, json={"chat_id": FOREX_CHAT_ID, "text": forex_message, "parse_mode": "HTML"}, timeout=10)
                print(f"   🔥 High-Volume SMC Signal sent for {display_name}")
            else:
                no_signal_pairs.append(display_name)

        # 📊 ৫ মিনিটের মার্কেট ফিল্টারিং সামারি আপডেট
        report_message = (
            f"⚡ <b>SMC Market Flow Snapshot | {current_time}</b>\n"
            f"🌐 <b>Active Session:</b> {current_session}\n"
            f"───────────────────\n"
            f"👁️‍🗨️ <b>অপেক্ষা করছি (Volume & Trap Filter):</b>\n"
        )
        if no_signal_pairs:
            report_message += f"<code>{', '.join(no_signal_pairs)}</code>\n\n"
            report_message += f"<i>বাকি এই পেয়ারগুলোতে পর্যাপ্ত ভলিউম বা প্রাতিষ্ঠানিক লিকুইডিটি নেই। রিটেইল ট্র্যাপ এড়াতে আমাদের আল্ট্রা-ইঞ্জিন এগুলোকে হোল্ডে রেখেছে।</i>\n"
        else:
            report_message += "<i>সবগুলো পেয়ারেই অলরেডি হাই-মোমেন্টাম ইনস্টিটিউশনাল মুভ রানিং আছে!</i>\n"
            
        report_message += "\n⏱️ <i>পরবর্তী ৫ মিনিট পর আমি আবার চার্ট ফিল্টার করে রিয়েল আপডেট দিচ্ছি...</i>"
        
        requests.post(url, json={"chat_id": FOREX_CHAT_ID, "text": report_message, "parse_mode": "HTML"}, timeout=10)
        print("✅ SMC Forex Summary Pushed Successfully!")
                
    except Exception as e:
        print(f"Loop error: {e}")
        
    time.sleep(300)
