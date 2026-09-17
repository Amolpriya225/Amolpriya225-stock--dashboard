import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import math
import streamlit.components.v1 as components

st.set_page_config(page_title="Pro Trading Chart", layout="wide")
st.title("📈 GAINZALGO V2 ALFA - TradingView + SL/Target")

# --- TIME FRAME SELECTOR LIKE ZERODHA ---
col1, col2, col3 = st.columns([2,1,2])
with col1:
    stock = st.selectbox("Stock", ["INFY.NS","TCS.NS","RELIANCE.NS","HDFCBANK.NS","SBIN.NS","TATAMOTORS.NS","ICICIBANK.NS","ITC.NS"], index=0)
    custom = st.text_input("Type NSE Stock (e.g. WIPRO.NS)")
    if custom: stock = custom.upper()
with col2:
    timeframe = st.select_slider("Time Frame", options=["5m","15m","30m","1h","1d","1wk"], value="1h")
with col3:
    rr_ratio = st.selectbox("Target Ratio", ["1:1.5","1:2","1:3"], index=1)

period_map = {"5m":"5d","15m":"1mo","30m":"1mo","1h":"3mo","1d":"1y","1wk":"2y"}
interval_map = {"5m":"5m","15m":"15m","30m":"30m","1h":"60m","1d":"1d","1wk":"1wk"}

# --- GAINZALGO ---
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
        l1=f_pdf(df['f1'].iloc[i],bull['f1'].mean(),bull['f1'].var())*f_pdf(df['f2'].iloc[i],bull['f2'].mean(),bull['f2'].var())*(len(bull)/100)
        l0=f_pdf(df['f1'].iloc[i],bear['f1'].mean(),bear['f1'].var())*f_pdf(df['f2'].iloc[i],bear['f2'].mean(),bear['f2'].var())*(len(bear)/100)
        probs.append(l1/(l1+l0+1e-6))
    df['PROB']=probs
    df['SIGNAL']=np.where(df['PROB']>0.62,1,np.where(df['PROB']<0.38,-1,0))
    return df

data = yf.download(stock, period=period_map[timeframe], interval=interval_map[timeframe])
if isinstance(data.columns, pd.MultiIndex): data.columns=data.columns.get_level_values(0)
if data.empty: st.error("No Data"); st.stop()
data = gainzalgo(data)

# ATR for SL/Target
data['H-L'] = data['High'] - data['Low']
data['ATR'] = data['H-L'].rolling(14).mean()
data['EMA20']=data['Close'].ewm(span=20).mean()

# --- MAIN CHART WITH DARK GREEN/RED + SL/TARGET ---
fig = go.Figure()

# CANDLE WITH DARK GREEN AND RED - ZERODHA STYLE
fig.add_trace(go.Candlestick(
    x=data.index, open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'],
    increasing_line_color='#00b386', increasing_fillcolor='#00b386', # Dark Green
    decreasing_line_color='#ff3c3c', decreasing_fillcolor='#ff3c3c', # Red
    name="Candle"
))

fig.add_trace(go.Scatter(x=data.index, y=data['EMA20'], name="EMA20", line=dict(color='yellow', width=1, dash='dot')))

# --- BUY/SELL + SL + TARGET LINES ---
rr = float(rr_ratio.split(":")[1])
trades = []
for idx in data[data['SIGNAL']!=0].index[-20:]: # last 20 signals
    row = data.loc[idx]
    entry = row['Close']
    atr = row['ATR'] if not np.isnan(row['ATR']) else entry*0.01
    if row['SIGNAL']==1: # BUY
        sl = entry - atr*1.5
        target = entry + (entry-sl)*rr
        color_sl = 'red'
        color_tg = 'green'
        fig.add_trace(go.Scatter(x=[idx, data.index[-1]], y=[sl, sl], mode='lines', line=dict(color='red', width=2, dash='dash'), name=f"SL {sl:.2f}"))
        fig.add_trace(go.Scatter(x=[idx, data.index[-1]], y=[target, target], mode='lines', line=dict(color='#00FF00', width=2, dash='dash'), name=f"Target {target:.2f}"))
        fig.add_annotation(x=idx, y=row['Low']*0.98, text=f"BUY<br>{row['PROB']*100:.0f}%", showarrow=True, arrowhead=2, bgcolor="green", font=dict(color="white"))
        trades.append(["BUY", idx.strftime("%d %H:%M"), f"{entry:.2f}", f"{sl:.2f}", f"{target:.2f}", f"{row['PROB']*100:.0f}%"])
    else: # SELL
        sl = entry + atr*1.5
        target = entry - (sl-entry)*rr
        fig.add_trace(go.Scatter(x=[idx, data.index[-1]], y=[sl, sl], mode='lines', line=dict(color='red', width=2, dash='dash'), name=f"SL {sl:.2f}"))
        fig.add_trace(go.Scatter(x=[idx, data.index[-1]], y=[target, target], mode='lines', line=dict(color='#00FF00', width=2, dash='dash'), name=f"Target {target:.2f}"))
        fig.add_annotation(x=idx, y=row['High']*1.02, text=f"SELL", showarrow=True, arrowhead=2, bgcolor="red", font=dict(color="white"))
        trades.append(["SELL", idx.strftime("%d %H:%M"), f"{entry:.2f}", f"{sl:.2f}", f"{target:.2f}", f"{row['PROB']*100:.0f}%"])

fig.update_layout(
    title=f"{stock} - {timeframe} - Dark Green/Red Candle + SL/Target",
    xaxis_rangeslider_visible=False, height=750, dragmode='zoom',
    hovermode='x unified', template='plotly_dark',
    xaxis=dict(fixedrange=False), yaxis=dict(fixedrange=False)
)

st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True, 'doubleClick': 'reset'})

# --- TRADE CONFIRMATION TABLE ---
st.subheader("✅ Trade Confirmation - GAINZALGO V2")
if trades:
    df_trades = pd.DataFrame(trades, columns=["Signal","Time","Entry","Stop Loss","Target", "Win Prob"])
    df_trades = df_trades.tail(5).iloc[::-1] # last 5
    st.table(df_trades)

    last = data.iloc[-1]
    if last['SIGNAL']==1:
        st.success(f"🟢 CONFIRMED BUY @ {last['Close']:.2f} | SL: {last['Close']-last['ATR']*1.5:.2f} | TARGET: {last['Close']+(last['ATR']*1.5*rr):.2f} | Time: {timeframe}")
    elif last['SIGNAL']==-1:
        st.error(f"🔴 CONFIRMED SELL @ {last['Close']:.2f} | SL: {last['Close']+last['ATR']*1.5:.2f} | TARGET: {last['Close']-(last['ATR']*1.5*rr):.2f} | Time: {timeframe}")
    else:
        st.warning(f"🟡 WAIT - No Signal now. Probability: {last['PROB']*100:.1f}%")
else:
    st.info("No signals in this timeframe, try 5m or 15m")

st.caption("Zoom: Mouse Wheel | Drag = Box Zoom | Double Click = Reset | Right edge drag = Vertical | Bottom edge = Horizontal")
