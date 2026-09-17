import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import math
import streamlit.components.v1 as components

st.set_page_config(page_title="Zerodha Style Chart", layout="wide")
st.title("📊 NSE + GAINZALGO V2 ALFA - Pro Chart")

# --- SETTINGS ---
st.sidebar.header("⚙️ Chart Settings")
stock = st.sidebar.selectbox("Stock", ["INFY.NS","TCS.NS","RELIANCE.NS","HDFCBANK.NS","SBIN.NS","TATAMOTORS.NS","ICICIBANK.NS","ITC.NS","BHARTIARTL.NS","LT.NS"])
custom = st.sidebar.text_input("Or Type Stock")
if custom: stock = custom.upper()

timeframe = st.sidebar.selectbox("Time", ["5m","15m","30m","1h","1d","1wk"], index=4)
period_map = {"5m":"5d","15m":"1mo","30m":"1mo","1h":"3mo","1d":"1y","1wk":"2y"}
interval_map = {"5m":"5m","15m":"15m","30m":"30m","1h":"60m","1d":"1d","1wk":"1wk"}

# --- GAINZALGO ENGINE ---
def f_pdf(x,m,v):
    v=max(v,0.0001)
    return (1 / math.sqrt(2*math.pi*v)) * math.exp(-((x-m)**2)/(2*v))

def gainzalgo(df):
    df=df.copy()
    df['vol_sma']=df['Volume'].rolling(20).mean()
    df['f1']=(df['Close']-df['Open'])/(df['High']-df['Low']+0.001)
    df['f2']=df['Volume']/(df['vol_sma']+1)
    df['is_green']=(df['Close']>df['Open']).astype(int)
    probs=[]
    for i in range(len(df)):
        if i<100: probs.append(0.5); continue
        win=df.iloc[i-100:i]
        bull=win[win['is_green']==1]; bear=win[win['is_green']==0]
        if len(bull)<10 or len(bear)<10: probs.append(0.5); continue
        m1_f1,v1_f1=bull['f1'].mean(),bull['f1'].var()
        m1_f2,v1_f2=bull['f2'].mean(),bull['f2'].var()
        m0_f1,v0_f1=bear['f1'].mean(),bear['f1'].var()
        m0_f2,v0_f2=bear['f2'].mean(),bear['f2'].var()
        p1=len(bull)/100
        l1=f_pdf(df['f1'].iloc[i],m1_f1,v1_f1)*f_pdf(df['f2'].iloc[i],m1_f2,v1_f2)*p1
        l0=f_pdf(df['f1'].iloc[i],m0_f1,v0_f1)*f_pdf(df['f2'].iloc[i],m0_f2,v0_f2)*(1-p1)
        probs.append(l1/(l1+l0+0.000001))
    df['PROB']=probs
    df['SIGNAL']=np.where(df['PROB']>0.60,1,np.where(df['PROB']<0.40,-1,0))
    return df

data = yf.download(stock, period=period_map[timeframe], interval=interval_map[timeframe])
if isinstance(data.columns, pd.MultiIndex): data.columns=data.columns.get_level_values(0)
data = gainzalgo(data)

data['EMA20']=data['Close'].ewm(span=20).mean()
data['EMA50']=data['Close'].ewm(span=50).mean()

# --- CHART WITH VERTICAL + HORIZONTAL ZOOM ---
fig = go.Figure(data=[go.Candlestick(x=data.index, open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="Candle")])
fig.add_trace(go.Scatter(x=data.index, y=data['EMA20'], name="EMA20", line=dict(color='yellow', width=1)))
fig.add_trace(go.Scatter(x=data.index, y=data['EMA50'], name="EMA50", line=dict(color='orange', width=1)))

buys = data[data['SIGNAL']==1]
sells = data[data['SIGNAL']==-1]
fig.add_trace(go.Scatter(x=buys.index, y=buys['Low']*0.99, mode='markers', name='BUY', marker=dict(symbol='triangle-up', size=15, color='#00FF00')))
fig.add_trace(go.Scatter(x=sells.index, y=sells['High']*1.01, mode='markers', name='SELL', marker=dict(symbol='triangle-down', size=15, color='red')))

# THIS IS THE FIX FOR ZOOM
fig.update_layout(
    title=f"{stock} - {timeframe}",
    xaxis_rangeslider_visible=False,
    height=700,
    dragmode='zoom',
    hovermode='x unified',
    template='plotly_dark',
    xaxis=dict(fixedrange=False),
    yaxis=dict(fixedrange=False)
)
fig.update_xaxes(showspikes=True)
fig.update_yaxes(showspikes=True)

st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True, 'doubleClick': 'reset'})

st.caption("HOW TO ZOOM: Mouse Wheel = Zoom | Drag Mouse = Box Zoom | Double Click = Reset | Right side drag = Vertical Zoom | Bottom drag = Horizontal Zoom")

# --- REAL TRADINGVIEW ---
st.subheader("Real TradingView Full Chart")
symbol = stock.replace(".NS","")
tv_widget = f"""
<div class="tradingview-widget-container">
  <div id="tradingview_abc" style="height:600px;"></div>
  <script type="text/javascript" src="https://s.tradingview.com/tv.js"></script>
  <script type="text/javascript">
  new TradingView.widget({{"autosize": true, "symbol": "NSE:{symbol}", "interval": "60", "timezone": "Asia/Kolkata", "theme": "dark", "style": "1", "locale": "in", "container_id": "tradingview_abc"}});
  </script>
</div>
"""
components.html(tv_widget, height=600)

last = data.iloc[-1]
st.success(f"Last: {stock} @ {last['Close']:.2f} | GAINZ Prob: {last['PROB']*100:.1f}% | Signal: {'BUY' if last['SIGNAL']==1 else 'SELL' if last['SIGNAL']==-1 else 'WAIT'}")
