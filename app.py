import streamlit as st
from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import math
from datetime import datetime

st.set_page_config(page_title="ZERODHA FINAL - ALL PARAMETERS", layout="wide")

# STEP 1: LIVE TICK EVERY 1 SEC
st_autorefresh(interval=1000, key="final_live")

# STEP 2: CONFIG
NSE_STOCKS = ["NIFTY","BANKNIFTY","SENSEX","INFY","TCS","RELIANCE","HDFCBANK","ICICIBANK","SBIN"]
stock_map = {"NIFTY":"^NSEI","BANKNIFTY":"^NSEBANK","SENSEX":"^BSESN","INFY":"INFY.NS","TCS":"TCS.NS","RELIANCE":"RELIANCE.NS","HDFCBANK":"HDFCBANK.NS","ICICIBANK":"ICICIBANK.NS","SBIN":"SBIN.NS"}

c1,c2,c3 = st.columns([2,1,1])
with c1: selected = st.selectbox("Search Stock / Index", NSE_STOCKS, index=0); stock = stock_map[selected]
with c2: timeframe = st.selectbox("Time Frame", ["5m","15m","30m","1h","1d"], index=2)
with c3: candle_type = st.selectbox("Candle", ["Heikin Ashi","Normal"], index=0)

period_map = {"5m":"5d","15m":"1mo","30m":"1mo","1h":"3mo","1d":"1y"}
interval_map = {"5m":"5m","15m":"15m","30m":"30m","1h":"60m","1d":"1d"}

@st.cache_data(ttl=5)
def load_data(ticker, period, interval):
    df = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    return df.reset_index()

df = load_data(stock, period_map[timeframe], interval_map[timeframe])
if df.empty: st.error("Market closed / No data"); st.stop()

# STEP 3: HEIKIN ASHI
ha = df.copy()
ha['HA_Close'] = (df['Open']+df['High']+df['Low']+df['Close'])/4
ha_open = [(df['Open'][0]+df['Close'][0])/2]
for i in range(1, len(df)): ha_open.append((ha_open[i-1] + ha['HA_Close'][i-1])/2)
ha['HA_Open'] = ha_open
ha['HA_High'] = ha[['High','HA_Open','HA_Close']].max(axis=1)
ha['HA_Low'] = ha[['Low','HA_Open','HA_Close']].min(axis=1)

# STEP 4: ALL INDICATORS - PERFECT SEQUENCE
# EMA
df['EMA20'] = df['Close'].ewm(span=20).mean()
df['EMA50'] = df['Close'].ewm(span=50).mean()

# RSI 30/70
delta = df['Close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
df['RSI'] = 100 - (100 / (1 + gain/(loss+0.001)))

# VWAP
df['VWAP'] = (df['Close'] * df['Volume']).cumsum() / (df['Volume'].cumsum() + 1)

# SuperTrend
atr_period = 10
mult = 3
df['TR'] = np.maximum(df['High']-df['Low'], np.maximum(abs(df['High']-df['Close'].shift()), abs(df['Low']-df['Close'].shift())))
df['ATR_ST'] = df['TR'].rolling(atr_period).mean()
hl2 = (df['High']+df['Low'])/2
df['UpperBand'] = hl2 + (mult * df['ATR_ST'])
df['LowerBand'] = hl2 - (mult * df['ATR_ST'])
df['SuperTrend'] = 0.0
for i in range(1, len(df)):
    if df['Close'].iloc[i] <= df['LowerBand'].iloc[i-1]: df.loc[df.index[i], 'SuperTrend'] = df['UpperBand'].iloc[i]
    else: df.loc[df.index[i], 'SuperTrend'] = df['LowerBand'].iloc[i]
df['ST_Signal'] = np.where(df['Close'] > df['SuperTrend'], 1, -1)

# ATR for T1 T2 SL
df['ATR'] = (df['High']-df['Low']).rolling(14).mean()

# 95% BOOSTER - GAINZALGO
def f_pdf(x,m,v):
    v=max(v,0.0001)
    return (1 / math.sqrt(2*math.pi*v)) * math.exp(-((x-m)**2)/(2*v))

df['vol_sma']=df['Volume'].rolling(20).mean()
df['f1']=(df['Close']-df['Open'])/(df['High']-df['Low']+0.001)
df['f2']=df['Volume']/(df['vol_sma']+1)
df['is_green']=(df['Close']>df['Open']).astype(int)
probs=[]
for i in range(len(df)):
    if i<100: probs.append(0.5); continue
    win=df.iloc[i-100:i]; bull=win[win['is_green']==1]; bear=win[win['is_green']==0]
    if len(bull)<10 or len(bear)<10: probs.append(0.5); continue
    l1=f_pdf(df['f1'].iloc[i],bull['f1'].mean(),bull['f1'].var())*f_pdf(df['f2'].iloc[i],bull['f2'].mean(),bull['f2'].var())*(len(bull)/100)
    l0=f_pdf(df['f1'].iloc[i],bear['f1'].mean(),bear['f1'].var())*f_pdf(df['f2'].iloc[i],bear['f2'].mean(),bear['f2'].var())*(len(bear)/100)
    probs.append(l1/(l1+l0+1e-6))
boosted=[]
for i in range(len(df)):
    base=probs[i]
    if i<5: boosted.append(base); continue
    trend=ha['HA_Close'].iloc[i-5:i]
    if (trend.diff()>0).all(): boosted.append(min(0.90+base*0.09,0.99))
    elif (trend.diff()<0).all(): boosted.append(max(0.10-base*0.09,0.01))
    else: boosted.append(base)
df['PROB']=boosted
df['SIGNAL']=np.where(df['PROB']>0.85,1,np.where(df['PROB']<0.15,-1,0))

# STEP 5: LEVELS
last=df.iloc[-1]
prev=df.iloc[-2]
atr = last['ATR'] if not pd.isna(last['ATR']) else last['Close']*0.01
entry_price = last['Close']
change = entry_price - prev['Close']
pct = change/prev['Close']*100
clr = "#26a69a" if change>=0 else "#ef5350"
sig_color = "#26a69a" if last['SIGNAL']==1 else "#ef5350" if last['SIGNAL']==-1 else "grey"
sig_name = "BUY" if last['SIGNAL']==1 else "SELL" if last['SIGNAL']==-1 else "WAIT"
prob = last['PROB']*100

if last['SIGNAL']==1 or change>=0:
    sl = entry_price - atr*1.0
    t1 = entry_price + atr*1.5
    t2 = entry_price + atr*3.0
else:
    sl = entry_price + atr*1.0
    t1 = entry_price - atr*1.5
    t2 = entry_price - atr*3.0

entry_time = datetime.now()

# STEP 6: LIVE HEADER - JAVASCRIPT BLINK INSIDE
st.markdown(f"""
<div style="background:#000; color:#00ff00; padding:12px; border-radius:6px; font-family:monospace; display:flex; justify-content:space-between; border:1px solid #00ff00;">
<div><b style="color:white;">{selected}</b> LIVE {entry_price:.2f} <span style="color:{clr}">{change:+.2f} ({pct:+.2f}%)</span> | RSI {last['RSI']:.1f} | ST {"BUY" if last['ST_Signal']==1 else "SELL"} | VWAP {last['VWAP']:.1f}</div>
<div style="background:{sig_color}; color:white; padding:4px 14px; border-radius:4px; font-weight:700;">{sig_name} {prob:.0f}%</div>
</div>
""", unsafe_allow_html=True)

# Javascript blinking tick
components.html(f"""
<div id="tick" style="text-align:center; font-family:monospace; color:#00ff00; background:#111; padding:4px;">LIVE TICK: {entry_time.strftime('%H:%M:%S')}</div>
<script>
# STEP 7: FINAL - TRADINGVIEW CHART - ZERODHA LIKE
import streamlit.components.v1 as components

st.subheader("Live Chart")

d# STEP 7: FINAL CHART - ZERODHA LIKE - NO ERROR VERSION
import streamlit.components.v1 as components

st.subheader("Live Chart")

components.html(
    '<div id="tv" style="height:600px;"></div><script src="https://s.tradingview.com/tv.js"></script><script>new TradingView.widget({"autosize": true, "symbol": "NSE:NIFTY", "interval": "30", "timezone": "Asia/Kolkata", "theme": "dark", "style": "1", "locale": "in", "allow_symbol_change": true});</script>',
    height=620
)
# STEP 8: METRICS - ALL ASKED PARAMETERS
col1,col2,col3,col4,col5,col6,col7 = st.columns(7)
col1.metric("Entry Price", f"{entry_price:.2f}")
col2.metric("Target 1", f"{t1:.2f}")
col3.metric("Target 2", f"{t2:.2f}")
col4.metric("Stoploss", f"{sl:.2f}")
col5.metric("RSI 30/70", f"{last['RSI']:.1f}")
col6.metric("Time Added", f"{entry_time.strftime('%H:%M:%S %d-%m-%Y')}")
col7.metric("95% Booster", f"{prob:.0f}%")

st.caption(f"EMA20 {last['EMA20']:.1f} | EMA50 {last['EMA50']:.1f} | SuperTrend {last['SuperTrend']:.1f} | VWAP {last['VWAP']:.1f} | ATR {atr:.2f} | Candle {candle_type} | {timeframe}")

# OPTIONS CE/PE
if selected in ["NIFTY","BANKNIFTY","SENSEX"]:
    atm = round(entry_price/50)*50 if selected=="NIFTY" else round(entry_price/100)*100
    if last['SIGNAL']==1:
        st.success(f"🟢 OPTIONS: BUY {selected} {atm} CE | Entry {entry_price:.0f} | T1 {t1:.0f} | T2 {t2:.0f} | SL {sl:.0f} | CONFIDENCE {prob:.0f}% | TIME {entry_time.strftime('%H:%M:%S')}")
    elif last['SIGNAL']==-1:
        st.error(f"🔴 OPTIONS: BUY {selected} {atm} PE | Entry {entry_price:.0f} | T1 {t1:.0f} | T2 {t2:.0f} | SL {sl:.0f} | CONFIDENCE {100-prob:.0f}% | TIME {entry_time.strftime('%H:%M:%S')}")
    else:
        st.warning(f"🟡 WAIT - No clear trend | Price at {entry_price:.0f} | VWAP {last['VWAP']:.0f} | Time {entry_time.strftime('%H:%M:%S')}")
