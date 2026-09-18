import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import math

st.set_page_config(page_title="Zerodha FULL + OPTIONS + 95%", layout="wide")

# STOCKS
NSE_STOCKS = ["NIFTY","BANKNIFTY","SENSEX","INFY","TCS","RELIANCE","HDFCBANK","ICICIBANK","SBIN","BHARTIARTL","ITC","LT"]
stock_map = {"NIFTY":"^NSEI","BANKNIFTY":"^NSEBANK","SENSEX":"^BSESN","INFY":"INFY.NS","TCS":"TCS.NS","RELIANCE":"RELIANCE.NS","HDFCBANK":"HDFCBANK.NS","ICICIBANK":"ICICIBANK.NS","SBIN":"SBIN.NS","BHARTIARTL":"BHARTIARTL.NS","ITC":"ITC.NS","LT":"LT.NS"}

c1,c2,c3 = st.columns([2,1,1])
with c1: selected = st.selectbox("Search Stock / Index ▼", NSE_STOCKS, index=0); stock = stock_map[selected]
with c2: timeframe = st.selectbox("Time Frame", ["5m","15m","30m","1h","1d"], index=3)
with c3: candle_type = st.selectbox("Candle", ["Heikin Ashi","Normal"], index=0)

period_map = {"5m":"5d","15m":"1mo","30m":"1mo","1h":"3mo","1d":"1y"}
interval_map = {"5m":"5m","15m":"15m","30m":"30m","1h":"60m","1d":"1d"}

df = yf.download(stock, period=period_map[timeframe], interval=interval_map[timeframe], auto_adjust=True)
if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
df = df.reset_index()
if df.empty: st.error("No data"); st.stop()

# Heikin Ashi
ha = df.copy()
ha['HA_Close'] = (df['Open']+df['High']+df['Low']+df['Close'])/4
ha_open = [(df['Open'][0]+df['Close'][0])/2]
for i in range(1, len(df)): ha_open.append((ha_open[i-1] + ha['HA_Close'][i-1])/2)
ha['HA_Open'] = ha_open
ha['HA_High'] = ha[['High','HA_Open','HA_Close']].max(axis=1)
ha['HA_Low'] = ha[['Low','HA_Open','HA_Close']].min(axis=1)

# --- INDICATORS - ALL OLD TOOLS BACK ---
# EMA
df['EMA20'] = df['Close'].ewm(span=20).mean()
df['EMA50'] = df['Close'].ewm(span=50).mean()

# RSI 30/70
delta = df['Close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
rs = gain / (loss + 0.001)
df['RSI'] = 100 - (100 / (1 + rs))

# SuperTrend
atr_period = 10
mult = 3
df['TR'] = np.maximum(df['High']-df['Low'], np.maximum(abs(df['High']-df['Close'].shift()), abs(df['Low']-df['Close'].shift())))
df['ATR_ST'] = df['TR'].rolling(atr_period).mean()
hl2 = (df['High'] + df['Low'])/2
df['UpperBand'] = hl2 + (mult * df['ATR_ST'])
df['LowerBand'] = hl2 - (mult * df['ATR_ST'])
df['SuperTrend'] = 0.0
for i in range(1, len(df)):
    if df['Close'].iloc[i] <= df['LowerBand'].iloc[i-1]: df.loc[df.index[i], 'SuperTrend'] = df['UpperBand'].iloc[i]
    else: df.loc[df.index[i], 'SuperTrend'] = df['LowerBand'].iloc[i]
df['ST_Signal'] = np.where(df['Close'] > df['SuperTrend'], 1, -1)

# GAINZALGO + 95% BOOSTER
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
df['ATR']=(df['High']-df['Low']).rolling(14).mean()

last=df.iloc[-1]; atr=last['ATR'] if not pd.isna(last['ATR']) else last['Close']*0.01
prob_percent=last['PROB']*100
change=last['Close']-df.iloc[-2]['Close']; pct=change/df.iloc[-2]['Close']*100
clr="#26a69a" if change>=0 else "#ef5350"
sig_color="#26a69a" if last['SIGNAL']==1 else "#ef5350" if last['SIGNAL']==-1 else "grey"
sig_name="BUY" if last['SIGNAL']==1 else "SELL" if last['SIGNAL']==-1 else "WAIT"

# TIME
entry_time = last['Datetime'] if 'Datetime' in df.columns else pd.Timestamp.now()
entry_price = last['Close']

if last['SIGNAL']==1:
    sl = entry_price - atr*1.0
    t1 = entry_price + atr*1.5
    t2 = entry_price + atr*3.0
else:
    sl = entry_price + atr*1.0
    t1 = entry_price - atr*1.5
    t2 = entry_price - atr*3.0

# HEADER - ZERODHA
st.markdown(f"""<div style="background:white; border:1px solid #e0e0e0; padding:12px; border-radius:4px; display:flex; justify-content:space-between;">
<div><b>{selected}</b> {entry_price:.2f} <span style="color:{clr};">{change:+.2f} ({pct:+.2f}%)</span> | RSI {last['RSI']:.1f} | ST {"BUY" if last['ST_Signal']==1 else "SELL"}</div>
<div style="background:{sig_color}; color:white; padding:5px 15px; border-radius:4px; font-weight:700;">{sig_name} {prob_percent:.0f}%</div>
</div>""", unsafe_allow_html=True)

# CHART
fig=go.Figure()
if candle_type=="Heikin Ashi":
    fig.add_trace(go.Candlestick(x=ha['Datetime'], open=ha['HA_Open'], high=ha['HA_High'], low=ha['HA_Low'], close=ha['HA_Close'], increasing_line_color='#26a69a', decreasing_line_color='#ef5350', name="HA"))
    x_data=ha['Datetime']
else:
    fig.add_trace(go.Candlestick(x=df['Datetime'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], increasing_line_color='#26a69a', decreasing_line_color='#ef5350'))
    x_data=df['Datetime']

fig.add_trace(go.Scatter(x=x_data, y=df['EMA20'], line=dict(color='orange', width=1), name="EMA20"))
fig.add_trace(go.Scatter(x=x_data, y=df['EMA50'], line=dict(color='blue', width=1), name="EMA50"))
fig.add_trace(go.Scatter(x=x_data, y=df['SuperTrend'], line=dict(color='purple', width=1, dash='dot'), name="SuperTrend"))

fig.add_shape(type="line", x0=x_data.iloc[-30], x1=x_data.iloc[-1], y0=sl, y1=sl, line=dict(color="red", dash="dash"))
fig.add_shape(type="line", x0=x_data.iloc[-30], x1=x_data.iloc[-1], y0=t1, y1=t1, line=dict(color="green", dash="dash"))
fig.add_shape(type="line", x0=x_data.iloc[-30], x1=x_data.iloc[-1], y0=t2, y1=t2, line=dict(color="darkgreen", dash="dash"))
fig.add_shape(type="line", x0=x_data.iloc[-30], x1=x_data.iloc[-1], y0=entry_price, y1=entry_price, line=dict(color="black", dash="solid"))

fig.update_layout(height=600, template='plotly_white', xaxis=dict(rangeslider=dict(visible=True, thickness=0.08)), yaxis=dict(side="right"), margin=dict(l=10,r=10,t=10,b=10), showlegend=True)
st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})

# DETAILS - ENTRY, TARGET1, TARGET2, SL, TIME - ALL BACK
col1,col2,col3,col4,col5,col6 = st.columns(6)
col1.metric("Entry Price", f"{entry_price:.2f}")
col2.metric("Target 1", f"{t1:.2f}")
col3.metric("Target 2", f"{t2:.2f}")
col4.metric("Stoploss", f"{sl:.2f}")
col5.metric("RSI (30/70)", f"{last['RSI']:.1f} {'Overbought' if last['RSI']>70 else 'Oversold' if last['RSI']<30 else 'Neutral'}")
col6.metric("Time", f"{pd.to_datetime(entry_time).strftime('%H:%M:%S %d-%m')}")

st.caption(f"EMA20 {last['EMA20']:.1f} | EMA50 {last['EMA50']:.1f} | SuperTrend {last['SuperTrend']:.1f} | Confirmation {prob_percent:.0f}%")

# OPTIONS
if selected in ["NIFTY","BANKNIFTY","SENSEX"]:
    atm=round(entry_price/50)*50 if selected=="NIFTY" else round(entry_price/100)*100
    if last['SIGNAL']==1: st.success(f"🟢 OPTION: BUY {selected} {atm} CE | Entry {entry_price:.0f} | T1 {t1:.0f} | T2 {t2:.0f} | SL {sl:.0f} | {prob_percent:.0f}%")
    elif last['SIGNAL']==-1: st.error(f"🔴 OPTION: BUY {selected} {atm} PE | Entry {entry_price:.0f} | T1 {t1:.0f} | T2 {t2:.0f} | SL {sl:.0f} | {100-prob_percent:.0f}%")
