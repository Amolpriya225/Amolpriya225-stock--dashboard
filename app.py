import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="NSE AI Dashboard", layout="wide")
st.title("📈 NSE AI - My Permanent Dashboard")

stocks = ["TCS.NS","RELIANCE.NS","INFY.NS","SBIN.NS","HDFCBANK.NS","ICICIBANK.NS","ITC.NS"]
stock = st.sidebar.selectbox("Select Stock", stocks)

data = yf.download(stock, period="6mo", auto_adjust=True, progress=False)
if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.get_level_values(0)

data['SMA_20'] = data['Close'].rolling(20).mean()
data['SMA_50'] = data['Close'].rolling(50).mean()

price = float(data['Close'].iloc[-1])
s20 = float(data['SMA_20'].iloc[-1])
s50 = float(data['SMA_50'].iloc[-1])

signal = "🟢 BUY" if s20 > s50 else "🔴 SELL / WAIT"

c1, c2, c3 = st.columns(3)
c1.metric(stock, f"₹{price:.2f}")
c2.metric("SMA 20", f"₹{s20:.2f}")
c3.metric("Signal", signal)

st.line_chart(data[['Close','SMA_20','SMA_50']])
st.write("Last 10 Days")
st.dataframe(data.tail(10).sort_index(ascending=False))
