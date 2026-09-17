import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import math

st.set_page_config(page_title="Heikin Ashi Pro", layout="wide")
st.title("🕯️ Heikin Ashi + GAINZALGO V2 - Zerodha Style")

# --- CONTROLS ---
c1,c2,c3,c4 = st.columns(4)
with c1:
    stock = st.selectbox("Stock", ["INFY.NS","TCS.NS","RELIANCE.NS","HDFCBANK.NS","SBIN.NS","TATAMOTORS.NS"])
    custom = st.text_input("Custom (e.g. WIPRO.NS)")
    if custom: stock = custom.upper()
with c2:
    timeframe = st.select_slider("Time Frame", options=["5m","15m","30m","1h","1d","1wk"], value="1h")
with c3:
    candle_type = st.selectbox("Candle Type", ["Normal Candle", "Heikin Ashi"], index=1)
with c4:
    rr_ratio = st.selectbox("Risk:Reward", ["1:2","1:3"], index=0)

period_map = {"5m":"5d","15m":"1mo","30m":"1mo","1h":"3mo","1d":"1y","1wk":"2y"}
interval_map = {"5m":"5m","15m":"15m","30m":"30m","1h":"60m","1d":"1d","1wk":"1wk"}

# --- DATA ---
data = yf.download(stock, period=period_map[timeframe], interval=interval_map[timeframe])
if isinstance(data.columns, pd.MultiIndex): data.columns=data.columns.get_level_values(0)
data = data.reset_index()
if 'Date' in data.columns: data.rename(columns={'Date':'Datetime'}, inplace=True)
if 'Datetime' not in data.columns: data.rename(columns={'index':'Datetime'}, inplace=True)

# --- HEIKIN ASHI FORMULA ---
def heikin_ashi(df):
    ha = df.copy()
    ha['HA_Close'] = (df['Open']+df['High']+df['Low']+df['Close'])/4
    ha_open = [(df['Open'][0]+df['Close'][0])/2]
    for i in range(1, len(df)):
        ha_open.append((ha_open[i-1] + ha['HA_Close'][i-1])/2)
    ha['HA_Open'] = ha_open
    ha['HA_High'] = ha[['High','HA_Open','HA_Close']].max(axis=1)
    ha['HA_Low'] = ha[['Low','HA_Open','HA_Close']].min(axis=1)
    return ha

ha_data = heikin_ashi(data)

# --- GAINZALGO ON NORMAL DATA FOR SIGNAL ---
def f_pdf(x,m,v):
    v=max(v,0.0001)
    return (1 / math.sqrt(2*math.pi*v)) * math.exp(-((x-m)**2)/(2*v))

df_sig = data.copy()
df_sig['vol_sma']=df_sig['Volume'].rolling(20).mean()
df_sig['f1']=(df_sig['Close']-df_sig['Open'])/(df_sig['High']-df_sig['Low']+0.001)
df_sig['f2']=df_sig['Volume']/(df_sig['vol_sma']+1)
df_sig['is_green']=(df_sig['Close']>df_sig['Open']).astype(int)
probs=[]
for i in range(len(df_sig)):
    if i<100: probs.append(0.5); continue
    win=df_sig.iloc[i-100:i]
    bull=win[win['is_green']==1]; bear=win[win['is_green']==0]
    if len(bull)<10 or len(bear)<10: probs.append(0.5); continue
    l1=f_pdf(df_sig['f1'].iloc[i],bull['f1'].mean(),bull['f1'].var())*f_pdf(df_sig['f2'].iloc[i],bull['f2'].mean(),bull['f2'].var())*(len(bull)/100)
    l0=f_pdf(df_sig['f1'].iloc[i],bear['f1'].mean(),bear['f1'].var())*f_pdf(df_sig['f2'].iloc[i],bear['f2'].mean(),bear['f2'].var())*(len(bear)/100)
    probs.append(l1/(l1+l0+1e-6))
df_sig['PROB']=probs
df_sig['SIGNAL']=np.where(df_sig['PROB']>0.62,1,np.where(df_sig['PROB']<0.38,-1,0))
df_sig['ATR']=(df_sig['High']-df_sig['Low']).rolling(14).mean()

# --- PLOT ---
fig = go.Figure()

if candle_type == "Heikin Ashi":
    # HEIKIN ASHI - DARK GREEN / RED
    fig.add_trace(go.Candlestick(
        x=ha_data['Datetime'], open=ha_data['HA_Open'], high=ha_data['HA_High'], low=ha_data['HA_Low'], close=ha_data['HA_Close'],
        increasing_line_color='#00b386', increasing_fillcolor='#00b386',
        decreasing_line_color='#ff3c3c', decreasing_fillcolor='#ff3c3c',
        name="Heikin Ashi"
    ))
    plot_close = ha_data['HA_Close']
else:
    fig.add_trace(go.Candlestick(
        x=data['Datetime'], open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'],
        increasing_line_color='#00b386', increasing_fillcolor='#00b386',
        decreasing_line_color='#ff3c3c', decreasing_fillcolor='#ff3c3c',
        name="Normal"
    ))
    plot_close = data['Close']

# EMA
fig.add_trace(go.Scatter(x=data['Datetime'], y=data['Close'].ewm(span=20).mean(), name="EMA20", line=dict(color='yellow', width=1)))

# BUY/SELL + SL/TARGET
rr = float(rr_ratio.split(":")[1])
last_signals = df_sig[df_sig['SIGNAL']!=0].tail(10)
for i, row in last_signals.iterrows():
    entry = row['Close']
    atr = row['ATR'] if not np.isnan(row['ATR']) else entry*0.015
    idx_time = row['Datetime']
    if row['SIGNAL']==1:
        sl = entry - atr*1.5
        tg = entry + (entry-sl)*rr
        fig.add_trace(go.Scatter(x=[idx_time, data['Datetime'].iloc[-1]], y=[sl, sl], line=dict(color='red', dash='dash'), name=f"SL {sl:.2f}"))
        fig.add_trace(go.Scatter(x=[idx_time, data['Datetime'].iloc[-1]], y=[tg, tg], line=dict(color='#00ff00', dash='dash'), name=f"TARGET {tg:.2f}"))
        fig.add_annotation(x=idx_time, y=sl, text=f"BUY {row['PROB']*100:.0f}%", showarrow=True, bgcolor="green")
    else:
        sl = entry + atr*1.5
        tg = entry - (sl-entry)*rr
        fig.add_trace(go.Scatter(x=[idx_time, data['Datetime'].iloc[-1]], y=[sl, sl], line=dict(color='red', dash='dash'), name=f"SL {sl:.2f}"))
        fig.add_trace(go.Scatter(x=[idx_time, data['Datetime'].iloc[-1]], y=[tg, tg], line=dict(color='#00ff00', dash='dash'), name=f"TARGET {tg:.2f}"))
        fig.add_annotation(x=idx_time, y=sl, text=f"SELL", showarrow=True, bgcolor="red")

fig.update_layout(
    title=f"{stock} - {candle_type} - {timeframe} | Dark Green/Red",
    xaxis_rangeslider_visible=False, height=750, dragmode='zoom',
    template='plotly_dark', xaxis=dict(fixedrange=False), yaxis=dict(fixedrange=False)
)

st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True, 'doubleClick': 'reset'})

# TRADE TABLE
st.subheader("✅ Trade Confirmation (Heikin Ashi + GAINZ)")
trades=[]
for i,row in last_signals.tail(5).iterrows():
    entry=row['Close']; atr=row['ATR'] if not np.isnan(row['ATR']) else entry*0.015
    sl = entry-atr*1.5 if row['SIGNAL']==1 else entry+atr*1.5
    tg = entry+(entry-sl)*rr if row['SIGNAL']==1 else entry-(sl-entry)*rr
    trades.append([ "BUY" if row['SIGNAL']==1 else "SELL", row['Datetime'].strftime("%d-%m %H:%M"), f"{entry:.2f}", f"{sl:.2f}", f"{tg:.2f}", f"{row['PROB']*100:.0f}%" ])

if trades:
    st.table(pd.DataFrame(trades, columns=["Signal","Time","Entry","Stop Loss","Target","Prob"])[::-1])

st.caption("Heikin Ashi = Trend clear hota hai. Green = Buy trend, Red = Sell trend. GAINZ signal SL/Target ke saath.")
