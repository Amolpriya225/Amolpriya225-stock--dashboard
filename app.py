import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="NSE AI Pro Dashboard", layout="wide")
st.title("📈 NSE AI Pro Dashboard - EMA | RSI | Supertrend | Candle Study")

# Hide menu
hide_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
"""
st.markdown(hide_style, unsafe_allow_html=True)

# --- STOCKS LIST - Add as many as you want ---
stocks = ["INFY.NS", "TCS.NS", "RELIANCE.NS", "WIPRO.NS", "HDFCBANK.NS", "SBIN.NS", "ICICIBANK.NS", "ITC.NS", "BHARTIARTL.NS", "LT.NS", "AXISBANK.NS", "TATAMOTORS.NS", "BAJFINANCE.NS", "MARUTI.NS"]
stock = st.sidebar.selectbox("Select Stock", stocks)
# Allow typing any stock too
custom = st.sidebar.text_input("Or Type Any NSE Stock (e.g. SBIN.NS)")
if custom:
    stock = custom.upper()

# --- FUNCTIONS FOR INDICATORS ---
def calculate_rsi(data, period=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_supertrend(df, period=10, multiplier=3):
    hl2 = (df['High'] + df['Low']) / 2
    atr = (df['High'] - df['Low']).rolling(period).mean() # Simplified ATR
    # More accurate ATR
    tr1 = df['High'] - df['Low']
    tr2 = (df['High'] - df['Close'].shift()).abs()
    tr3 = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()

    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)

    supertrend = [True] * len(df)
    for i in range(1, len(df)):
        if df['Close'].iloc[i] <= lower_band.iloc[i-1]:
            supertrend[i] = True
        elif df['Close'].iloc[i] >= upper_band.iloc[i-1]:
            supertrend[i] = False
        else:
            supertrend[i] = supertrend[i-1]
            if supertrend[i] and lower_band.iloc[i] < lower_band.iloc[i-1]:
                lower_band.iloc[i] = lower_band.iloc[i-1]
            if not supertrend[i] and upper_band.iloc[i] > upper_band.iloc[i-1]:
                upper_band.iloc[i] = upper_band.iloc[i-1]

    return upper_band, lower_band, supertrend

# --- DOWNLOAD DATA ---
data = yf.download(stock, period="1y", interval="1d")
if data.empty:
    st.error("No data found! Check stock symbol.")
    st.stop()

# Flatten if multi-index
if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.get_level_values(0)

# --- CALCULATE ALL INDICATORS ---
data['SMA20'] = data['Close'].rolling(20).mean()
data['SMA50'] = data['Close'].rolling(50).mean()
data['EMA20'] = data['Close'].ewm(span=20, adjust=False).mean()
data['EMA50'] = data['Close'].ewm(span=50, adjust=False).mean()
data['EMA200'] = data['Close'].ewm(span=200, adjust=False).mean()
data['RSI'] = calculate_rsi(data)

upper_band, lower_band, st_trend = calculate_supertrend(data)
data['ST_Upper'] = upper_band
data['ST_Lower'] = lower_band
data['ST_Trend'] = st_trend # True = Buy, False = Sell

# --- CANDLE STUDY ---
last = data.iloc[-1]
prev = data.iloc[-2]
body = abs(last['Close'] - last['Open'])
prev_body = abs(prev['Close'] - prev['Open'])
is_bullish = last['Close'] > last['Open']
is_bearish = last['Close'] < last['Open']

candle_signal = "Normal"
if (last['Low'] < last['Open'] and last['Low'] < last['Close']) and body < (last['High'] - last['Low']) * 0.3:
    candle_signal = "🔨 Hammer - Potential BUY Reversal"
elif last['Close'] > prev['Open'] and last['Open'] < prev['Close'] and is_bullish and not (prev['Close'] > prev['Open']):
    candle_signal = "🟢 Bullish Engulfing - STRONG BUY"
elif last['Close'] < prev['Open'] and last['Open'] > prev['Close'] and is_bearish:
    candle_signal = "🔴 Bearish Engulfing - STRONG SELL"
elif body < (last['High'] - last['Low']) * 0.1:
    candle_signal = "➕ Doji - Confusion / Reversal Coming"

# --- FINAL SIGNAL LOGIC ---
price = float(last['Close'])
rsi_val = float(last['RSI'])
st_buy = last['ST_Trend']

buy_score = 0
if price > last['EMA20']: buy_score+=1
if last['EMA20'] > last['EMA50']: buy_score+=1
if rsi_val > 30 and rsi_val < 65: buy_score+=1
if st_buy == True: buy_score+=1
if "BUY" in candle_signal: buy_score+=2

if buy_score >= 4:
    final_signal = "✅ STRONG BUY"
elif buy_score >= 2:
    final_signal = "⚠️ WAIT / HOLD"
else:
    final_signal = "❌ SELL"

# --- DISPLAY ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Price", f"₹{price:.2f}")
col2.metric("RSI (14)", f"{rsi_val:.1f}", "Overbought" if rsi_val>70 else "Oversold" if rsi_val<30 else "Neutral")
col3.metric("Supertrend", "BUY 🟢" if st_buy else "SELL 🔴")
col4.metric("Signal", final_signal)

st.info(f"**Candle Study:** {candle_signal}")

# --- CHARTS ---
st.subheader(f"{stock} Chart with EMA & Supertrend")
st.line_chart(data[['Close','EMA20','EMA50','ST_Upper','ST_Lower']].tail(100))

st.subheader("RSI Chart")
st.line_chart(data[['RSI']].tail(100))
st.caption("RSI >70 = Overbought (Sell), RSI <30 = Oversold (Buy)")

st.dataframe(data.tail(10))
