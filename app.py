import streamlit as st
from streamlit_autorefresh import st_autorefresh
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import math
from datetime import datetime

st.set_page_config(page_title="LIVE TICKING + FULL INDICATORS", layout="wide")

# LIVE REFRESH EVERY 1 SECOND
st_autorefresh(interval=1000, key="live1sec")

NSE_STOCKS = ["NIFTY","BANKNIFTY","SENSEX","INFY","TCS","RELIANCE","HDFCBANK"]
stock_map = {"NIFTY":"^NSEI","BANKNIFTY":"^NSEBANK","SENSEX":"^BSESN","INFY":"INFY.NS","TCS":"TCS.NS","RELIANCE":"RELIANCE.NS","HDFCBANK":"HDFCBANK.NS"}

selected = st.selectbox("Stock", NSE_STOCKS, index=0)
stock = stock_map[selected]

# FAST DOWNLOAD 1m
df = yf.download(stock, period="1d", interval="1m", auto_adjust=True, progress=False)
if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
df = df.reset_index()
if df.empty: st.stop()

last = df.iloc[-1]
prev = df.iloc[-2]
change = last['Close']-prev['Close']
pct = change/prev['Close']*100
clr = "#00ff00" if change>=0 else "#ff0000"

# LIVE TICK HEADER - UPDATES EVERY SECOND
now = datetime.now().strftime('%H:%M:%S')
st.markdown(f"""
<div style="background:#000; color:#00ff00; padding:10px; border-radius:5px; font-family:monospace; font-size:24px; text-align:center; border:1px solid #00ff00;">
{selected} ● LIVE {last['Close']:.2f} <span style="color:{clr}">{change:+.2f} ({pct:+.2f}%)</span>
<span style="font-size:14px; color:white;">| TICK {now} | 1 Sec Auto Refresh</span>
</div>
""", unsafe_allow_html=True)

# INDICATORS (EMA, RSI, ST, ATR)
df['EMA20']=df['Close'].ewm(span=20).mean()
df['EMA50']=df['Close'].ewm(span=50).mean()
delta=df['Close'].diff(); gain=(delta.where(delta>0,0)).rolling(14).mean(); loss=(-delta.where(delta<0,0)).rolling(14).mean()
df['RSI']=100-(100/(1+gain/(loss+0.001)))
df['ATR']=(df['High']-df['Low']).rolling(14).mean()

atr = last['ATR'] if not pd.isna(df['ATR'].iloc[-1]) else last['Close']*0.005
entry = last['Close']
sl = entry - atr if change>=0 else entry + atr
t1 = entry + atr*1.5 if change>=0 else entry - atr*1.5
t2 = entry + atr*3 if change>=0 else entry - atr*3

# CHART
fig=go.Figure()
fig.add_trace(go.Candlestick(x=df['Datetime'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close']))
fig.add_trace(go.Scatter(x=df['Datetime'], y=df['EMA20'], line=dict(color='orange')))
fig.update_layout(height=500, template='plotly_white', xaxis_rangeslider_visible=False, margin=dict(l=10,r=10,t=10,b=10))
st.plotly_chart(fig, use_container_width=True)

c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric("Entry", f"{entry:.2f}")
c2.metric("T1", f"{t1:.2f}")
c3.metric("T2", f"{t2:.2f}")
c4.metric("SL", f"{sl:.2f}")
c5.metric("RSI", f"{df['RSI'].iloc[-1]:.1f}")
c6.metric("Time", now)

# OPTIONS
if selected in ["NIFTY","BANKNIFTY","SENSEX"]:
    atm=round(entry/50)*50
    if change>0: st.success(f"LIVE OPTION BUY {atm} CE - Tick {now}")
    else: st.error(f"LIVE OPTION BUY {atm} PE - Tick {now}")

st.caption("Free version ticks every 1 second. With Zerodha API it ticks every 100ms.")
