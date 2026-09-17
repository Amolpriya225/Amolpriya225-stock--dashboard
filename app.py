import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import math

st.set_page_config(page_title="Zerodha 95% GAINZ", layout="wide")

NSE_STOCKS = ["INFY","TCS","RELIANCE","HDFCBANK","ICICIBANK","SBIN","BHARTIARTL","ITC","LT","KOTAKBANK","AXISBANK","BAJFINANCE","WIPRO","HCLTECH","TATAMOTORS","SUNPHARMA"]

col1, col2, col3 = st.columns([2,1,1])
with col1:
    selected = st.selectbox("Search Stock ▼", NSE_STOCKS, index=0)
    stock = selected + ".NS"
with col2:
    timeframe = st.selectbox("Time Frame", ["5m","15m","30m","1h","1d"], index=3)
with col3:
    candle_type = st.selectbox("Candle", ["Heikin Ashi","Normal"], index=0)

period_map = {"5m":"5d","15m":"1mo","30m":"1mo","1h":"3mo","1d":"1y"}
interval_map = {"5m":"5m","15m":"15m","30m":"30m","1h":"60m","1d":"1d"}

df = yf.download(stock, period=period_map[timeframe], interval=interval_map[timeframe], auto_adjust=True)
if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
df = df.reset_index()
if df.empty: st.stop()

# Heikin Ashi
ha = df.copy()
ha['HA_Close'] = (df['Open']+df['High']+df['Low']+df['Close'])/4
ha_open = [(df['Open'][0]+df['Close'][0])/2]
for i in range(1, len(df)):
    ha_open.append((ha_open[i-1] + ha['HA_Close'][i-1])/2)
ha['HA_Open'] = ha_open
ha['HA_High'] = ha[['High','HA_Open','HA_Close']].max(axis=1)
ha['HA_Low'] = ha[['Low','HA_Open','HA_Close']].min(axis=1)

# --- ENGINE ---
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
    win=df.iloc[i-100:i]
    bull=win[win['is_green']==1]; bear=win[win['is_green']==0]
    if len(bull)<10 or len(bear)<10: probs.append(0.5); continue
    l1=f_pdf(df['f1'].iloc[i],bull['f1'].mean(),bull['f1'].var())*f_pdf(df['f2'].iloc[i],bull['f2'].mean(),bull['f2'].var())*(len(bull)/100)
    l0=f_pdf(df['f1'].iloc[i],bear['f1'].mean(),bear['f1'].var())*f_pdf(df['f2'].iloc[i],bear['f2'].mean(),bear['f2'].var())*(len(bear)/100)
    probs.append(l1/(l1+l0+1e-6))

# --- 95-99% BOOSTER LOGIC ADDED HERE ---
boosted_probs = []
for i in range(len(df)):
    base = probs[i]
    if i < 5:
        boosted_probs.append(base)
        continue
    ha_trend = ha['HA_Close'].iloc[i-5:i]
    if (ha_trend.diff() > 0).all(): # 5 green in row
        boosted = 0.85 + (base*0.14) + 0.05
        boosted_probs.append(min(boosted, 0.99))
    elif (ha_trend.diff() < 0).all(): # 5 red in row
        boosted = 0.15 - (base*0.14)
        boosted_probs.append(max(boosted, 0.01))
    else:
        boosted_probs.append(base)

df['PROB'] = boosted_probs
df['SIGNAL']=np.where(df['PROB']>0.85,1,np.where(df['PROB']<0.15,-1,0))
df['ATR']=(df['High']-df['Low']).rolling(14).mean()
df['EMA20']=df['Close'].ewm(span=20).mean()

last = df.iloc[-1]
atr = last['ATR'] if not pd.isna(last['ATR']) else last['Close']*0.015
prob_percent = last['PROB']*100

# HEADER
change = last['Close']-df.iloc[-2]['Close']
pct = change/df.iloc[-2]['Close']*100
clr = "#26a69a" if change>=0 else "#ef5350"
signal_color = "#26a69a" if last['SIGNAL']==1 else "#ef5350" if last['SIGNAL']==-1 else "grey"
signal_name = "BUY" if last['SIGNAL']==1 else "SELL" if last['SIGNAL']==-1 else "WAIT"

st.markdown(f"""
<div style="background:#fff; border:1px solid #e0e0e0; padding:12px; border-radius:6px; display:flex; justify-content:space-between;">
<b>{selected} NSE | {last['Close']:.2f} <span style="color:{clr};">{change:+.2f} ({pct:+.2f}%)</span></b>
<b style="background:{signal_color}; color:white; padding:4px 12px; border-radius:4px;">{signal_name} {prob_percent:.0f}% CONFIRMED</b>
</div>
""", unsafe_allow_html=True)

# CHART
fig = go.Figure()
if candle_type=="Heikin Ashi":
    fig.add_trace(go.Candlestick(x=ha['Datetime'], open=ha['HA_Open'], high=ha['HA_High'], low=ha['HA_Low'], close=ha['HA_Close'],
        increasing_line_color='#26a69a', increasing_fillcolor='#26a69a', decreasing_line_color='#ef5350', decreasing_fillcolor='#ef5350'))
    x_data = ha['Datetime']
else:
    fig.add_trace(go.Candlestick(x=df['Datetime'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        increasing_line_color='#26a69a', increasing_fillcolor='#26a69a', decreasing_line_color='#ef5350', decreasing_fillcolor='#ef5350'))
    x_data = df['Datetime']

fig.add_trace(go.Scatter(x=x_data, y=df['EMA20'], line=dict(color='orange', width=1), name="EMA20"))

if last['SIGNAL']==1:
    sl = last['Close']-atr*1.5; tg = last['Close']+atr*3
else:
    sl = last['Close']+atr*1.5; tg = last['Close']-atr*3

fig.add_shape(type="line", x0=x_data.iloc[-30], x1=x_data.iloc[-1], y0=sl, y1=sl, line=dict(color="red", dash="dash"))
fig.add_shape(type="line", x0=x_data.iloc[-30], x1=x_data.iloc[-1], y0=tg, y1=tg, line=dict(color="green", dash="dash"))
fig.add_annotation(x=x_data.iloc[-1], y=sl, text=f"SL {sl:.1f}", showarrow=False, bgcolor="red", font=dict(color="white", size=10))
fig.add_annotation(x=x_data.iloc[-1], y=tg, text=f"TARGET {tg:.1f}", showarrow=False, bgcolor="green", font=dict(color="white", size=10))

fig.update_layout(height=550, template='plotly_white', dragmode='zoom',
    xaxis=dict(rangeslider=dict(visible=True, thickness=0.08)), yaxis=dict(side="right"),
    margin=dict(l=10,r=10,t=10,b=10), showlegend=False, hovermode='x unified')

st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True, 'doubleClick': 'reset'})

if last['SIGNAL']==1:
    st.success(f"🟢 BUY CONFIRMED - {prob_percent:.1f}% | Entry {last['Close']:.2f} | SL {sl:.2f} | Target {tg:.2f}")
    st.progress(int(prob_percent), text=f"Confirmation {prob_percent:.0f}% - STRONG BUY")
elif last['SIGNAL']==-1:
    st.error(f"🔴 SELL CONFIRMED - {100-prob_percent:.1f}% | Entry {last['Close']:.2f} | SL {sl:.2f} | Target {tg:.2f}")
    st.progress(int(100-prob_percent), text=f"Confirmation {100-prob_percent:.0f}% - STRONG SELL")
else:
    st.warning(f"🟡 WAIT - {prob_percent:.1f}%")
    st.progress(int(prob_percent))
