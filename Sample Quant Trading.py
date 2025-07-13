import streamlit as st
import pandas as pd
import yfinance as yf
import requests

# Safely get the API key from Streamlit secrets
FINNHUB_API_KEY = st.secrets["finnhub"]["api_key"]

TARIFF_SENSITIVE_SECTORS = [
    "Steel", "Semiconductors", "Textiles", "Automotive", "Agriculture", "Solar"
]

def fetch_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        eps = info.get("trailingEps", 0)
        bvps = info.get("bookValue", 0)
        price = info.get("currentPrice", 0)
        sector = info.get("sector", "Unknown")

        intrinsic = (22.5 * eps * bvps) ** 0.5 if eps > 0 and bvps > 0 else None
        undervalued = intrinsic > price if intrinsic else False
        trade_sensitive = sector in TARIFF_SENSITIVE_SECTORS
        mispricing = "Yes" if undervalued and trade_sensitive else "No"

        return {
            "Ticker": ticker,
            "Price": price,
            "EPS": eps,
            "BVPS": bvps,
            "Intrinsic Value": round(intrinsic, 2) if intrinsic else None,
            "Undervalued?": "Yes" if undervalued else "No",
            "Sector": sector,
            "Tariff Sensitive?": "Yes" if trade_sensitive else "No",
            "Mispriced (Trade War)?": mispricing
        }
    except Exception as e:
        return {"Ticker": ticker, "Error": str(e)}

def fetch_broker_recommendation(ticker):
    try:
        url = f"https://finnhub.io/api/v1/stock/recommendation?symbol={ticker}&token={FINNHUB_API_KEY}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data:
                r = data[0]
                return {
                    "Strong Buy": r.get("strongBuy"),
                    "Buy": r.get("buy"),
                    "Hold": r.get("hold"),
                    "Sell": r.get("sell"),
                    "Strong Sell": r.get("strongSell")
                }
    except Exception as e:
        st.warning(f"Broker data failed for {ticker}: {e}")
    return {}

# --- Streamlit UI ---
st.title("📘 Ben Graham Stock Screener with Broker Ratings & Trade Mispricing")

tickers_input = st.text_input("Enter tickers (comma separated)", "TSLA,MSFT,RELIANCE.NS")
tickers = [t.strip().upper() for t in tickers_input.split(',')]

results = []
for ticker in tickers:
    base_data = fetch_stock_data(ticker)
    broker_data = fetch_broker_recommendation(ticker)
    results.append({**base_data, **broker_data})

df = pd.DataFrame(results)

if not df.empty:
    st.dataframe(df)
else:
    st.warning("⚠️ No data to display. Please check ticker symbols or API access.")

st.markdown("""
**Legend**  
✅ *Undervalued?* → Based on Ben Graham Formula  
🟡 *Mispriced (Trade War)?* → Tariff-sensitive + undervalued  
📈 *Broker Ratings* → From analysts via Finnhub
""")
