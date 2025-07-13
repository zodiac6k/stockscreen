import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objs as go
import os

st.title("📈 Stock Screener - Beginner Project")

# Load ticker list
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(script_dir, "tickers.csv")
df = pd.read_csv(csv_path)
print(df.columns)
tickers = df['Ticker'].tolist()

selected_tickers = st.multiselect("Select stocks", tickers[:50])  # Limit for speed

pe_filter = st.slider("Max P/E Ratio", 0, 100, 30)

data = []

for ticker in selected_tickers:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        if info['trailingPE'] is not None and info['trailingPE'] <= pe_filter:
            data.append({
                'Symbol': ticker,
                'Name': info.get('shortName', ''),
                'PE': info['trailingPE'],
                'Market Cap': info['marketCap'],
                'Price': info['currentPrice']
            })
    except:
        pass

if data:
    df = pd.DataFrame(data)
    st.dataframe(df)

    if st.button("Download CSV"):
        df.to_csv("screened_stocks.csv", index=False)
        st.success("Downloaded as screened_stocks.csv")

    # Chart for first selected stock
    chart_ticker = selected_tickers[0]
    hist = yf.download(chart_ticker, period="6mo")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name='Close Price'))
    st.plotly_chart(fig)
