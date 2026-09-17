import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import math

st.set_page_config(page_title="Heikin Ashi Pro - Responsive", layout="wide")
st.title("🕯️ Heikin Ashi - Responsive Zoom Chart")

# --- CONTROLS ---
c1,c2,c3 = st.columns([2,1,1])
with c1:
    stock = st.selectbox("Stock", ["INFY.NS","TCS.NS","RELIANCE.NS","HDFCBANK.NS","SBIN.NS","TATAMOTORS.NS","ICICIBANK.NS"], index=0)
with c2:
    timeframe = st.select_slider("Time Frame", options=["5m","15m","30m","1h","1d"], value="1h")
with c3:
    show_only_last = st.checkbox("Show Only Last Trade SL/Target", True)

period_map = {"5m":"5d","15m":"1mo","30m":"1mo","1h":"3mo","1d":"1y"}
interval_map = {"5m":"5m","15m":"15m","30m":"30m","1h":"60m","1d":"1d"}

# --- DATA ---
data = yf.download(stock, period=period_map[timeframe], interval=interval_map[timeframe], auto_adjust=True)
if isinstance(data.columns, pd.MultiIndex): data.columns=data.columns.get_level_values(0)
data = data.reset_index()
if 'Date' in data.columns: data.rename(columns={'Date':'Datetime'}, inplace=True)

# Heikin Ashi
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

# GAINZ Signal
data['ATR']=(data['High']-data['Low']).rolling(14).mean()
data['PROB']=0.5
# simple prob for demo - last candle bullish = 65%
data['PROB'] = np.where(data['Close']>data['Open'], 0.65, 0.35)
data['SIGNAL'] = np.where(data['PROB']>0.60,1,np.where(data['PROB']<0.40,-1,0))

# --- PRO CHART WITH INDEX BAR (Range Slider) ---
fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=ha_data['Datetime'], open=ha_data['HA_Open'], high=ha_data['HA_High'], low=ha_data['HA_Low'], close=ha_data['HA_Close'],
    increasing_line_color='#00b386', increasing_fillcolor='#00b386',
    decreasing_line_color='#ff3c3c', decreasing_fillcolor='#ff3c3c',
    name="Heikin Ashi"
))

fig.add_trace(go.Scatter(x=data['Datetime'], y=data['Close'].ewm(span=20).mean(), name="EMA20", line=dict(color='yellow', width=1.2)))

# ONLY LAST SIGNAL SL/TARGET - FIX FOR SCREEN
signals = data[data['SIGNAL']!=0]
if not signals.empty:
    if show_only_last:
        signals_to_plot = signals.tail(1)
    else:
        signals_to_plot = signals.tail(3) # max 3 to avoid clutter

    for i,row in signals_to_plot.iterrows():
        entry=row['Close']; atr=row['ATR'] if not pd.isna(row['ATR']) else entry*0.015
        rr=2
        sl = entry-atr*1.5 if row['SIGNAL']==1 else entry+atr*1.5
        tg = entry+(entry-sl)*rr if row['SIGNAL']==1 else entry-(sl-entry)*rr

        # SL Line
        fig.add_trace(go.Scatter(x=[row['Datetime'], data['Datetime'].iloc[-1]], y=[sl, sl],
                                 line=dict(color='red', width=2, dash='dash'), name=f"SL {sl:.1f}"))
        # Target Line
        fig.add_trace(go.Scatter(x=[row['Datetime'], data['Datetime'].iloc[-1]], y=[tg, tg],
                                 line=dict(color='#00ff00', width=2, dash='dash'), name=f"TARGET {tg:.1f}"))

        # BUY/SELL Label
        if row['SIGNAL']==1:
            fig.add_annotation(x=row['Datetime'], y=row['Low']*0.99, text=f"BUY {row['PROB']*100:.0f}%<br>SL {sl:.1f} | TG {tg:.1f}",
                               showarrow=True, arrowhead=2, bgcolor="#00b386", font=dict(color="white", size=12))
        else:
            fig.add_annotation(x=row['Datetime'], y=row['High']*1.01, text=f"SELL<br>SL {sl:.1f} | TG {tg:.1f}",
                               showarrow=True, arrowhead=2, bgcolor="#ff3c3c", font=dict(color="white", size=12))

# --- THIS IS THE MAIN FIX FOR VERTICAL/HORIZONTAL + INDEX BAR ---
fig.update_layout(
    title=f"{stock} - Heikin Ashi {timeframe} - Responsive",
    height=650, # Fixed height for screen
    template='plotly_dark',
    dragmode='zoom',
    hovermode='x unified',
    # HORIZONTAL INDEX BAR - Like Zerodha bottom slider
    xaxis=dict(
        rangeslider=dict(visible=True, thickness=0.08), # <-- INDEX BAR
        rangeselector=dict(
            buttons=list([
                dict(count=1, label="1D", step="day", stepmode="backward"),
                dict(count=5, label="5D", step="day", stepmode="backward"),
                dict(count=1, label="1M", step="month", stepmode="backward"),
                dict(step="all", label="All")
            ])
        ),
        fixedrange=False,
        showspikes=True
    ),
    yaxis=dict(fixedrange=False, showspikes=True, autorange=True),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=10, r=10, t=60, b=10)
)

st.plotly_chart(fig, use_container_width=True, config={
    'scrollZoom': True,
    'doubleClick': 'reset',
    'displayModeBar': True,
    'displaylogo': False
})

st.info("👇 **HOW TO USE:**\n- **Bottom Grey Bar = Horizontal Zoom Index Bar** - Drag edges to zoom time\n- **Mouse Wheel = Vertical + Horizontal Zoom**\n- **Right side Drag = Only Vertical Zoom**\n- **Drag on Chart = Box Zoom**\n- **Double Click = Reset to Full Screen Fit")

# Trade Table
st.subheader("Last Trade")
if not signals.empty:
    last = signals.iloc[-1]
    entry=last['Close']; atr=last['ATR'] if not pd.isna(last['ATR']) else entry*0.015
    sl = entry-atr*1.5 if last['SIGNAL']==1 else entry+atr*1.5
    tg = entry+(entry-sl)*2 if last['SIGNAL']==1 else entry-(sl-entry)*2
    st.success(f"{'BUY' if last['SIGNAL']==1 else 'SELL'} @ {entry:.2f} | SL: {sl:.2f} | TARGET: {tg:.2f} | Chart fits screen now")
