# Sample_Quant_Trading.py

import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objs as go
import os
import requests
import time
import io
from concurrent.futures import ThreadPoolExecutor
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import schedule
import time as pytime

st.title("📘 Multi-Source Stock Screener - Enhanced Version")

# Load tickers
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(script_dir, "tickers.csv")
df = pd.read_csv(csv_path)
tickers = df['Ticker'].tolist()

selected_tickers = st.multiselect("Select stocks", tickers[:50])  # limit to speed up

pe_filter = st.slider("Max P/E Ratio", 0, 100, 30)

# Data source options
st.sidebar.subheader("📊 Data Sources")
use_yfinance = st.sidebar.checkbox("Yahoo Finance", value=True)
use_alpha_vantage = st.sidebar.checkbox("Alpha Vantage", value=False)
use_finnhub = st.sidebar.checkbox("Finnhub", value=False)

# API Keys (use sidebar input, fallback to default if blank)
DEFAULT_ALPHA_VANTAGE_API_KEY = "3CLWRCXR800F4ASG"
DEFAULT_FINNHUB_API_KEY = "d1pmoi9r01qu436fmoigd1pmoi9r01qu436fmoj0"

ALPHA_VANTAGE_API_KEY = st.sidebar.text_input("Alpha Vantage API Key", type="password") or DEFAULT_ALPHA_VANTAGE_API_KEY
FINNHUB_API_KEY = st.sidebar.text_input("Finnhub API Key", type="password") or DEFAULT_FINNHUB_API_KEY

# Format market cap
def format_market_cap(market_cap):
    if market_cap is None:
        return "N/A"
    if market_cap >= 1e12:
        return f"${market_cap/1e12:.2f}T"
    elif market_cap >= 1e9:
        return f"${market_cap/1e9:.2f}B"
    elif market_cap >= 1e6:
        return f"${market_cap/1e6:.2f}M"
    else:
        return f"${market_cap:,.0f}"

# YFinance
def get_yfinance_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        recommendations = stock.recommendations
        buy_count = hold_count = sell_count = upgrades = downgrades = 0

        if recommendations is not None and not recommendations.empty:
            recent = recommendations.tail(10)
            if 'To Grade' in recent.columns:
                buy_count = len(recent[recent['To Grade'].str.contains('Buy|Outperform', case=False, na=False)])
                hold_count = len(recent[recent['To Grade'].str.contains('Hold|Neutral', case=False, na=False)])
                sell_count = len(recent[recent['To Grade'].str.contains('Sell|Underperform', case=False, na=False)])
                if 'From Grade' in recent.columns:
                    upgrades = len(recent[recent['To Grade'] > recent['From Grade']])
                    downgrades = len(recent[recent['To Grade'] < recent['From Grade']])

        return {
            'source': 'Yahoo Finance',
            'price': info.get('currentPrice'),
            'market_cap': info.get('marketCap'),
            'pe_ratio': info.get('trailingPE'),
            'company_name': info.get('shortName', ''),
            'buy_recs': buy_count,
            'hold_recs': hold_count,
            'sell_recs': sell_count,
            'upgrades': upgrades,
            'downgrades': downgrades,
            'volume': info.get('volume'),
            'avg_volume': info.get('averageVolume'),
            'dividend_yield': info.get('dividendYield'),
            'beta': info.get('beta'),
            'fifty_two_week_high': info.get('fiftyTwoWeekHigh'),
            'fifty_two_week_low': info.get('fiftyTwoWeekLow')
        }
    except Exception as e:
        st.warning(f"YFinance error for {ticker}: {e}")
        return None

def get_finnhub_recommendations(ticker):
    try:
        url = f"https://finnhub.io/api/v1/stock/recommendation?symbol={ticker}&token={FINNHUB_API_KEY}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data:
                r = data[0]
                return {
                    'buy': r.get('buy', 0),
                    'hold': r.get('hold', 0),
                    'sell': r.get('sell', 0),
                    'strongBuy': r.get('strongBuy', 0),
                    'strongSell': r.get('strongSell', 0)
                }
    except Exception as e:
        st.warning(f"Finnhub rec error for {ticker}: {e}")
    return {'buy': 0, 'hold': 0, 'sell': 0, 'strongBuy': 0, 'strongSell': 0}

# Aggregator
def get_aggregated_data(ticker):
    sources = []
    yf_data = get_yfinance_data(ticker) if use_yfinance else None
    if yf_data:
        sources.append(yf_data)
    # Finnhub fallback for recommendations
    finnhub_recs = get_finnhub_recommendations(ticker) if use_finnhub and FINNHUB_API_KEY else None
    d = sources[0] if sources else {}
    total_buy = d.get('buy', 0) + (finnhub_recs['buy'] if finnhub_recs else 0)
    total_hold = d.get('hold', 0) + (finnhub_recs['hold'] if finnhub_recs else 0)
    total_sell = d.get('sell', 0) + (finnhub_recs['sell'] if finnhub_recs else 0)

    return {
        'Ticker': ticker,
        'Name': d.get('company_name'),
        'Full Name': d.get('long_name', d.get('company_name', '')),
        'PE': round(d.get('pe_ratio', 0), 2) if d.get('pe_ratio') else None,
        'Market Cap': format_market_cap(d.get('market_cap')),
        'Price': f"${d.get('price', 0):.2f}" if d.get('price') else "N/A",
        'Buy': total_buy,
        'Hold': total_hold,
        'Sell': total_sell,
        'Upgrades': d.get('upgrades', 0),
        'Downgrades': d.get('downgrades', 0),
        'Volume': f"{d.get('volume', 0):,}" if d.get('volume') else "N/A",
        'Dividend Yield': f"{d.get('dividend_yield')*100:.2f}%" if d.get('dividend_yield') else "N/A",
        'Beta': f"{d.get('beta'):.2f}" if d.get('beta') else "N/A",
        '52W High': f"${d.get('fifty_two_week_high'):.2f}" if d.get('fifty_two_week_high') else "N/A",
        '52W Low': f"${d.get('fifty_two_week_low'):.2f}" if d.get('fifty_two_week_low') else "N/A",
        'Data Sources': len(sources)
    }

# Email config
EMAIL_ADDRESS = st.secrets.get("email", {}).get("address", "your_email@gmail.com")
EMAIL_PASSWORD = st.secrets.get("email", {}).get("password", "your_app_password")
EMAIL_TO = st.secrets.get("email", {}).get("to", "recipient_email@gmail.com")

def send_email_alert(subject, body):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = EMAIL_TO
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, EMAIL_TO, msg.as_string())
    except Exception as e:
        st.warning(f"Email send failed: {e}")

def load_last_recommendations():
    if os.path.exists("last_recommendations.json"):
        with open("last_recommendations.json", "r") as f:
            return json.load(f)
    return {}

def save_last_recommendations(data):
    with open("last_recommendations.json", "w") as f:
        json.dump(data, f)

# Main fetch
data = []
with st.spinner("Fetching stock data..."):
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(get_aggregated_data, selected_tickers))
    data = [r for r in results if r]

# Show results
if data:
    df = pd.DataFrame(data)
    st.subheader("📊 Screening Results")
    # Set index to start from 1
    df.index = df.index + 1
    # Display the dataframe with a height that fits most screens and use_container_width for full width
    st.dataframe(df, use_container_width=True, height=900)

    # Download button (works on Streamlit Cloud)
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Download CSV",
        data=csv,
        file_name="results.csv",
        mime="text/csv"
    )

    col1, col2 = st.columns(2)
    with col2:
        if st.button("📊 Summary"):
            st.metric("Total Stocks", len(df))
            st.metric("Avg P/E", round(df['PE'].mean(), 2))

    # Price Chart
    if selected_tickers:
        st.subheader(f"📈 Price Chart: {selected_tickers[0]}")
        try:
            chart_ticker = selected_tickers[0]
            hist = yf.download(chart_ticker, period="6mo", auto_adjust=True)
            if not hist.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name="Close"))
                fig.update_layout(title=f"{chart_ticker} - 6M Price", xaxis_title="Date", yaxis_title="Price ($)")
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Chart error for {chart_ticker}: {e}")

    last_recs = load_last_recommendations()
    changes = []
    current_recs = {}

    for row in data:
        ticker = row['Ticker']
        recs = {'Buy': row['Buy'], 'Hold': row['Hold'], 'Sell': row['Sell']}
        current_recs[ticker] = recs
        last = last_recs.get(ticker)
        if last and recs != last:
            changes.append(f"{ticker}: {last} → {recs}")

    if changes:
        subject = "Stock Screener Alert: Recommendation Change"
        body = "The following stocks have updated recommendations:\n\n" + "\n".join(changes)
        send_email_alert(subject, body)

    save_last_recommendations(current_recs)

else:
    st.info("No data found. Try different tickers or relax P/E filter.")

st.markdown("""
**Note:** Most free APIs do not provide analyst recommendations (Buy/Hold/Sell) for all stocks. 
For more complete data, a paid data provider is required.
""")
