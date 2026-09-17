import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import streamlit.components.v1 as components

st.set_page_config(page_title="Zerodha Clone - Fixed", layout="wide")

# --- TOP NSE STOCKS LIST FOR DROPDOWN (Auto-show on arrow) ---
NSE_STOCKS = [
    "INFY","TCS","RELIANCE","HDFCBANK","ICICIBANK","SBIN","BHARTIARTL","ITC","LT","KOTAKBANK",
    "AXISBANK","BAJFINANCE","WIPRO","HCLTECH","SUNPHARMA","MARUTI","TITAN","ULTRACEMCO","ONGC","NTPC",
    "POWERGRID","TATAMOTORS","ADANIENT","JSWSTEEL","COALINDIA","M&M","HINDALCO","TECHM","CIPLA","DIVISLAB",
    "DRREDDY","EICHERMOT","GRASIM","BPCL","BRITANNIA","HEROMOTOCO","HINDUNILVR","APOLLOHOSP","BAJAJFINSV","SBILIFE"
]

# --- HEADER ---
col1, col2, col3 = st.columns([2,1,1])
with col1:
    selected_stock_name = st.selectbox("Search Stock (Click arrow ▼)", NSE_STOCKS, index=0)
    stock = selected_stock_name + ".NS"
with col2:
    timeframe = st.selectbox("TimeFrame", ["5m","15m","30m","1h","1d"], index=3)
with col3:
    candle_type = st.selectbox("Candle", ["Normal", "Heikin Ashi"], index=1)

period_map = {"5m":"5d","15m":"1mo","30m":"1mo","1h":"3mo","1d":"1y"}
interval_map = {"5m":"5m","15m":"15m","30m":"30m","1h":"60m","1d":"1d"}

# --- DATA ---
@st.cache_data(ttl=60)
def get_data(stock, period, interval):
    df = yf.download(stock, period=period, interval=interval, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df = df.reset_index()
    return df

df = get_data(stock, period_map[timeframe], interval_map[timeframe])
if df.empty:
    st.error(f"No data for {stock}")
    st.stop()

# Heikin Ashi Calc
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

ha = heikin_ashi(df)
df['EMA20'] = df['Close'].ewm(span=20).mean()
df['ATR'] = (df['High']-df['Low']).rolling(14).mean()

# Last price header like Zerodha
last = df.iloc[-1]
prev = df.iloc[-2]
change = last['Close']-prev['Close']
pct = change/prev['Close']*100
clr = "#26a69a" if change>=0 else "#ef5350"
st.markdown(f"""
<div style="background:white; padding:12px; border:1px solid #e3e3e3; border-radius:6px; display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
<div><b style="font-size:16px;">{selected_stock_name} <span style="color:grey; font-weight:400;">NSE</span></b> <span style="margin-left:15px; font-size:16px;">{last['Close']:.2f}</span> <span style="color:{clr};">{change:+.2f} ({pct:+.2f}%)</span></div>
<div style="color:grey; font-size:13px;">O {last['Open']:.2f} H {last['High']:.2f} L {last['Low']:.2f} C {last['Close']:.2f} Vol {last['Volume']:,}</div>
</div>
""", unsafe_allow_html=True)

# --- 1. MAIN CHART (Plotly but Zerodha White Theme) - 100% WILL SHOW ---
fig = go.Figure()

if candle_type == "Heikin Ashi":
    fig.add_trace(go.Candlestick(x=ha['Datetime'], open=ha['HA_Open'], high=ha['HA_High'], low=ha['HA_Low'], close=ha['HA_Close'],
                                 increasing_line_color='#26a69a', increasing_fillcolor='#26a69a',
                                 decreasing_line_color='#ef5350', decreasing_fillcolor='#ef5350', name="Heikin Ashi"))
else:
    fig.add_trace(go.Candlestick(x=df['Datetime'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                                 increasing_line_color='#26a69a', increasing_fillcolor='#26a69a',
                                 decreasing_line_color='#ef5350', decreasing_fillcolor='#ef5350', name="Candle"))

fig.add_trace(go.Scatter(x=df['Datetime'], y=df['EMA20'], line=dict(color='#ff9800', width=1.2), name="EMA20"))

# Only LAST SL/Target to keep chart clean & friendly
last_atr = df['ATR'].iloc[-1] if not pd.isna(df['ATR'].iloc[-1]) else last['Close']*0.015
sl_buy = last['Close'] - last_atr*1.5
tg_buy = last['Close'] + last_atr*3
sl_sell = last['Close'] + last_atr*1.5
tg_sell = last['Close'] - last_atr*3

# Example - if last candle bullish show BUY levels
if last['Close'] > last['Open']:
    fig.add_trace(go.Scatter(x=[df['Datetime'].iloc[-20], df['Datetime'].iloc[-1]], y=[sl_buy, sl_buy], line=dict(color='red', dash='dash'), name=f"SL {sl_buy:.1f}"))
    fig.add_trace(go.Scatter(x=[df['Datetime'].iloc[-20], df['Datetime'].iloc[-1]], y=[tg_buy, tg_buy], line=dict(color='green', dash='dash'), name=f"TARGET {tg_buy:.1f}"))
    fig.add_annotation(x=df['Datetime'].iloc[-1], y=last['Low'], text="BUY", bgcolor="#26a69a", font=dict(color="white"))
else:
    fig.add_trace(go.Scatter(x=[df['Datetime'].iloc[-20], df['Datetime'].iloc[-1]], y=[sl_sell, sl_sell], line=dict(color='red', dash='dash'), name=f"SL {sl_sell:.1f}"))
    fig.add_trace(go.Scatter(x=[df['Datetime'].iloc[-20], df['Datetime'].iloc[-1]], y=[tg_sell, tg_sell], line=dict(color='green', dash='dash'), name=f"TARGET {tg_sell:.1f}"))
    fig.add_annotation(x=df['Datetime'].iloc[-1], y=last['High'], text="SELL", bgcolor="#ef5350", font=dict(color="white"))

fig.update_layout(
    height=550,
    template='plotly_white', # Zerodha white theme
    dragmode='zoom',
    xaxis=dict(rangeslider=dict(visible=True, thickness=0.06), # INDEX BAR - Bottom
               rangeselector=dict(buttons=list([
                   dict(count=1, label="1D", step="day", stepmode="backward"),
                   dict(count=5, label="5D", step="day", stepmode="backward"),
                   dict(step="all", label="All")
               ])),
               type="date", fixedrange=False),
    yaxis=dict(fixedrange=False, side="right"),
    margin=dict(l=5,r=5,t=10,b=5),
    legend=dict(orientation="h", y=1.02, x=0),
    hovermode='x unified'
)

st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True, 'doubleClick': 'reset', 'displaylogo': False})

st.caption("✅ Friendly Controls: Bottom Grey Bar = Horizontal Index Bar | Scroll Mouse = Vertical Zoom | Drag = Zoom Box | Double Click = Reset")

# --- 2. TRADINGVIEW CHART BELOW (Extra - For Pro Tools) ---
st.markdown("---")
st.write("**Pro TradingView Tools (Optional):**")
tv_widget = f"""
<div class="tradingview-widget-container">
  <div id="tradingview_123" style="height:500px;"></div>
  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
  <script type="text/javascript">
  new TradingView.widget({{
    "autosize": true,
    "symbol": "NSE:{selected_stock_name}",
    "interval": "60",
    "timezone": "Asia/Kolkata",
    "theme": "light",
    "style": "1",
    "locale": "in",
    "toolbar_bg": "#f1f3f6",
    "enable_publishing": false,
    "withdateranges": true,
    "hide_side_toolbar": false,
    "allow_symbol_change": false,
    "container_id": "tradingview_123"
  }});
  </script>
</div>
"""
components.html(tv_widget, height=520)

# Signal Table
st.table(pd.DataFrame([["BUY" if last['Close']>last['Open'] else "SELL", f"{last['Close']:.2f}", f"{sl_buy if last['Close']>last['Open'] else sl_sell:.2f}", f"{tg_buy if last['Close']>last['Open'] else tg_sell:.2f}"]], columns=["Signal","Entry","Stop Loss","Target"]))
