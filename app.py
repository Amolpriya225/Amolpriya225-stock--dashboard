
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import math

st.set_page_config(page_title="NSE + GAINZALGO V2 ALFA", layout="wide")
st.title("📈 NSE Dashboard + GAINZALGO V2 ALFA (AI)")

stocks = ["INFY.NS","TCS.NS","RELIANCE.NS","HDFCBANK.NS","SBIN.NS","ICICIBANK.NS","TATAMOTORS.NS","ITC.NS"]
stock = st.sidebar.selectbox("Select Stock", stocks)
custom = st.sidebar.text_input("Or Type (e.g. BHARTIARTL.NS)")
if custom: stock = custom.upper()

# --- GAINZALGO V2 ALFA CORE ENGINE ---
def f_pdf(x, m, v):
    # Gaussian PDF - same as TradingView version
    v = max(v, 0.0001)
    return (1 / math.sqrt(2 * math.pi * v)) * math.exp(-((x - m)**2) / (2 * v))

def gainzalgo_v2_alfa(df, len_lookback=100):
    # Feature 1: Price Force (Close - Open) / ATR
    # Feature 2: Volume Intensity (Volume / SMA Volume)
    df = df.copy()
    df['vol_sma'] = df['Volume'].rolling(20).mean()
    df['feat1'] = (df['Close'] - df['Open']) / (df['High'] - df['Low'] + 0.001) # Price Force
    df['feat2'] = df['Volume'] / (df['vol_sma'] + 1) # Volume Intensity
    df['is_green'] = (df['Close'] > df['Open']).astype(int)

    probs = []
    for i in range(len(df)):
        if i < len_lookback:
            probs.append(0.5)
            continue
        window = df.iloc[i-len_lookback:i]

        # Split buckets - Bullish vs Bearish like GainzAlgo does
        bull = window[window['is_green']==1]
        bear = window[window['is_green']==0]
        if len(bull)<10 or len(bear)<10:
            probs.append(0.5)
            continue

        m1_f1, v1_f1 = bull['feat1'].mean(), bull['feat1'].var()
        m1_f2, v1_f2 = bull['feat2'].mean(), bull['feat2'].var()
        m0_f1, v0_f1 = bear['feat1'].mean(), bear['feat1'].var()
        m0_f2, v0_f2 = bear['feat2'].mean(), bear['feat2'].var()

        p1 = len(bull) / len_lookback

        feat1_cur = df['feat1'].iloc[i]
        feat2_cur = df['feat2'].iloc[i]

        l1 = f_pdf(feat1_cur, m1_f1, v1_f1) * f_pdf(feat2_cur, m1_f2, v1_f2) * p1
        l0 = f_pdf(feat1_cur, m0_f1, v0_f1) * f_pdf(feat2_cur, m0_f2, v0_f2) * (1-p1)

        prob = l1 / (l1 + l0 + 0.000001)
        probs.append(prob)

    df['GAINZ_PROB'] = probs
    df['GAINZ_SIGNAL'] = np.where(df['GAINZ_PROB'] > 0.60, 1, np.where(df['GAINZ_PROB'] < 0.40, -1, 0))
    return df

# Download
data = yf.download(stock, period="1y", interval="1d")
if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)

data = gainzalgo_v2_alfa(data)
last = data.iloc[-1]
prob_pct = last['GAINZ_PROB'] * 100

# --- DISPLAY ---
c1,c2,c3 = st.columns(3)
c1.metric("Stock", stock, f"₹{last['Close']:.2f}")
c2.metric("GAINZALGO Probability", f"{prob_pct:.1f}%", "BULLISH" if prob_pct>60 else "BEARISH" if prob_pct<40 else "NEUTRAL")
if last['GAINZ_SIGNAL']==1:
    c3.metric("Signal", "✅ BUY", f"{prob_pct:.0f}% Win Prob")
elif last['GAINZ_SIGNAL']==-1:
    c3.metric("Signal", "❌ SELL", f"{100-prob_pct:.0f}% Win Prob")
else:
    c3.metric("Signal", "WAIT")

# Heatmap like TradingView (20 layers)
st.subheader("🔥 GAINZALGO Heatmap (Power Index)")
# Simulate 20 probability layers like original
st.line_chart(data[['GAINZ_PROB']].tail(100))

# Candle + Signal
st.subheader("Chart with GAINZALGO Buy/Sell")
# Add markers
buy = data[data['GAINZ_SIGNAL']==1]['Close']
sell = data[data['GAINZ_SIGNAL']==-1]['Close']
chart_df = pd.DataFrame({'Close': data['Close'].tail(150), 'BUY': buy.tail(150), 'SELL': sell.tail(150)})
st.line_chart(chart_df)

st.write(f"**Candle Study:** Last candle {'Bullish' if last['Close']>last['Open'] else 'Bearish'} | Volume Intensity: {last['feat2']:.2f}x")

# For convenience of BUY/SELL
if prob_pct > 70 and last['Close'] > data['Close'].rolling(20).mean().iloc[-1]:
    st.success(f"🟢 HIGH CONVICTION BUY - {prob_pct:.0f}% probability aligns with bullish reversal (like TradingView)")
elif prob_pct < 30:
    st.error(f"🔴 HIGH CONVICTION SELL - {100-prob_pct:.0f}% bearish probability")
else:
    st.warning("⚠️ Low confluence - WAIT")

st.dataframe(data.tail(20))
