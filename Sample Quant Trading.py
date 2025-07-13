import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objs as go
import os
import requests
import time
from datetime import datetime, timedelta
import json

st.title("📈 Multi-Source Stock Screener - Enhanced Version")

# Load ticker list
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(script_dir, "tickers.csv")
df = pd.read_csv(csv_path)
print(df.columns)
tickers = df['Ticker'].tolist()

selected_tickers = st.multiselect("Select stocks", tickers[:50])  # Limit for speed

pe_filter = st.slider("Max P/E Ratio", 0, 100, 30)

# Data source selection
st.sidebar.subheader("🔄 Data Sources")
use_yfinance = st.sidebar.checkbox("Yahoo Finance", value=True)
use_alpha_vantage = st.sidebar.checkbox("Alpha Vantage", value=False)
use_finnhub = st.sidebar.checkbox("Finnhub", value=False)
use_quandl = st.sidebar.checkbox("Quandl", value=False)

# API Keys (you can add these to Streamlit secrets later)
ALPHA_VANTAGE_API_KEY = st.sidebar.text_input("3CLWRCXR800F4ASG", type="password")
FINNHUB_API_KEY = st.sidebar.text_input("d1pmoi9r01qu436fmoigd1pmoi9r01qu436fmoj0", type="password")

# Function to format market cap in millions
def format_market_cap(market_cap):
    if market_cap is None:
        return "N/A"
    if market_cap >= 1e12:  # Trillion
        return f"${market_cap/1e12:.2f}T"
    elif market_cap >= 1e9:  # Billion
        return f"${market_cap/1e9:.2f}B"
    elif market_cap >= 1e6:  # Million
        return f"${market_cap/1e6:.2f}M"
    else:
        return f"${market_cap:,.0f}"

# YFinance data source
def get_yfinance_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Get recommendations
        recommendations = stock.recommendations
        buy_count, hold_count, sell_count = 0, 0, 0
        upgrades, downgrades = 0, 0
        
        if recommendations is not None and not recommendations.empty:
            recent_recs = recommendations.tail(10)
            buy_count = len(recent_recs[recent_recs['To Grade'].str.contains('Buy|Strong Buy|Outperform', case=False, na=False)])
            hold_count = len(recent_recs[recent_recs['To Grade'].str.contains('Hold|Neutral|Equal-Weight', case=False, na=False)])
            sell_count = len(recent_recs[recent_recs['To Grade'].str.contains('Sell|Strong Sell|Underperform', case=False, na=False)])
            
            upgrades = len(recent_recs[recent_recs['To Grade'] > recent_recs['From Grade']])
            downgrades = len(recent_recs[recent_recs['To Grade'] < recent_recs['From Grade']])
        
        return {
            'source': 'Yahoo Finance',
            'price': info.get('currentPrice'),
            'market_cap': info.get('marketCap'),
            'pe_ratio': info.get('trailingPE'),
            'company_name': info.get('shortName', info.get('longName', '')),
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
        st.write(f"YFinance error for {ticker}: {str(e)}")
        return None

# Alpha Vantage data source
def get_alpha_vantage_data(ticker):
    if not ALPHA_VANTAGE_API_KEY:
        return None
    
    try:
        # Get company overview
        url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}"
        response = requests.get(url)
        data = response.json()
        
        if 'Error Message' in data:
            return None
            
        # Get real-time quote
        quote_url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}"
        quote_response = requests.get(quote_url)
        quote_data = quote_response.json()
        
        return {
            'source': 'Alpha Vantage',
            'price': float(quote_data.get('Global Quote', {}).get('05. price', 0)),
            'market_cap': float(data.get('MarketCapitalization', 0)),
            'pe_ratio': float(data.get('PERatio', 0)) if data.get('PERatio') != 'None' else None,
            'company_name': data.get('Name', ''),
            'buy_recs': 0,  # Alpha Vantage doesn't provide recommendations
            'hold_recs': 0,
            'sell_recs': 0,
            'upgrades': 0,
            'downgrades': 0,
            'volume': float(quote_data.get('Global Quote', {}).get('06. volume', 0)),
            'avg_volume': 0,
            'dividend_yield': float(data.get('DividendYield', 0)) if data.get('DividendYield') != 'None' else None,
            'beta': float(data.get('Beta', 0)) if data.get('Beta') != 'None' else None,
            'fifty_two_week_high': float(quote_data.get('Global Quote', {}).get('52WeekHigh', 0)),
            'fifty_two_week_low': float(quote_data.get('Global Quote', {}).get('52WeekLow', 0))
        }
    except Exception as e:
        st.write(f"Alpha Vantage error for {ticker}: {str(e)}")
        return None

# Finnhub data source
def get_finnhub_data(ticker):
    if not FINNHUB_API_KEY:
        return None
    
    try:
        # Get quote
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_API_KEY}"
        response = requests.get(url)
        quote_data = response.json()
        
        # Get company profile
        profile_url = f"https://finnhub.io/api/v1/stock/profile2?symbol={ticker}&token={FINNHUB_API_KEY}"
        profile_response = requests.get(profile_url)
        profile_data = profile_response.json()
        
        # Get analyst recommendations
        rec_url = f"https://finnhub.io/api/v1/stock/recommendation?symbol={ticker}&token={FINNHUB_API_KEY}"
        rec_response = requests.get(rec_url)
        rec_data = rec_response.json()
        
        buy_count = sum(rec_data.get('buy', 0) for rec_data in rec_data)
        hold_count = sum(rec_data.get('hold', 0) for rec_data in rec_data)
        sell_count = sum(rec_data.get('sell', 0) for rec_data in rec_data)
        
        return {
            'source': 'Finnhub',
            'price': quote_data.get('c'),
            'market_cap': profile_data.get('marketCapitalization'),
            'pe_ratio': profile_data.get('peRatio'),
            'company_name': profile_data.get('name', ''),
            'buy_recs': buy_count,
            'hold_recs': hold_count,
            'sell_recs': sell_count,
            'upgrades': 0,
            'downgrades': 0,
            'volume': quote_data.get('v'),
            'avg_volume': quote_data.get('av'),
            'dividend_yield': None,
            'beta': None,
            'fifty_two_week_high': quote_data.get('h'),
            'fifty_two_week_low': quote_data.get('l')
        }
    except Exception as e:
        st.write(f"Finnhub error for {ticker}: {str(e)}")
        return None

# Quandl data source (now part of Nasdaq Data Link)
def get_quandl_data(ticker):
    try:
        # Quandl has limited free data, but we can get some basic info
        # This is a simplified version - you'd need API key for full access
        return {
            'source': 'Quandl',
            'price': None,
            'market_cap': None,
            'pe_ratio': None,
            'company_name': '',
            'buy_recs': 0,
            'hold_recs': 0,
            'sell_recs': 0,
            'upgrades': 0,
            'downgrades': 0,
            'volume': None,
            'avg_volume': None,
            'dividend_yield': None,
            'beta': None,
            'fifty_two_week_high': None,
            'fifty_two_week_low': None
        }
    except Exception as e:
        st.write(f"Quandl error for {ticker}: {str(e)}")
        return None

# Alternative free data source - Yahoo Finance API (different method)
def get_yahoo_finance_alt(ticker):
    try:
        # Using a different approach to get Yahoo Finance data
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if 'chart' in data and 'result' in data['chart'] and data['chart']['result']:
            result = data['chart']['result'][0]
            meta = result.get('meta', {})
            
            return {
                'source': 'Yahoo Finance API',
                'price': meta.get('regularMarketPrice'),
                'market_cap': meta.get('marketCap'),
                'pe_ratio': None,  # Not available in this endpoint
                'company_name': meta.get('shortName', ''),
                'buy_recs': 0,
                'hold_recs': 0,
                'sell_recs': 0,
                'upgrades': 0,
                'downgrades': 0,
                'volume': meta.get('volume'),
                'avg_volume': meta.get('averageVolume'),
                'dividend_yield': None,
                'beta': None,
                'fifty_two_week_high': meta.get('fiftyTwoWeekHigh'),
                'fifty_two_week_low': meta.get('fiftyTwoWeekLow')
            }
    except Exception as e:
        st.write(f"Yahoo Finance API error for {ticker}: {str(e)}")
        return None

# Function to aggregate data from multiple sources
def get_aggregated_data(ticker):
    data_sources = []
    
    if use_yfinance:
        yf_data = get_yfinance_data(ticker)
        if yf_data:
            data_sources.append(yf_data)
    
    if use_alpha_vantage and ALPHA_VANTAGE_API_KEY:
        av_data = get_alpha_vantage_data(ticker)
        if av_data:
            data_sources.append(av_data)
    
    if use_finnhub and FINNHUB_API_KEY:
        fh_data = get_finnhub_data(ticker)
        if fh_data:
            data_sources.append(fh_data)
    
    if use_quandl:
        q_data = get_quandl_data(ticker)
        if q_data:
            data_sources.append(q_data)
    
    # If no other sources, try alternative Yahoo Finance method
    if not data_sources and use_yfinance:
        yf_alt_data = get_yahoo_finance_alt(ticker)
        if yf_alt_data:
            data_sources.append(yf_alt_data)
    
    if not data_sources:
        return None
    
    # Aggregate data (take the first available source for now)
    # In a more sophisticated version, you could average or weight the data
    primary_data = data_sources[0]
    
    # Combine recommendations from all sources
    total_buy = sum(d.get('buy_recs', 0) for d in data_sources)
    total_hold = sum(d.get('hold_recs', 0) for d in data_sources)
    total_sell = sum(d.get('sell_recs', 0) for d in data_sources)
    total_upgrades = sum(d.get('upgrades', 0) for d in data_sources)
    total_downgrades = sum(d.get('downgrades', 0) for d in data_sources)
    
    return {
        'Symbol': ticker,
        'Name': primary_data.get('company_name', ''),
        'PE': round(primary_data.get('pe_ratio', 0), 2) if primary_data.get('pe_ratio') else None,
        'Market Cap': format_market_cap(primary_data.get('market_cap')),
        'Price': f"${primary_data.get('price', 0):.2f}" if primary_data.get('price') else "N/A",
        'Buy': total_buy,
        'Hold': total_hold,
        'Sell': total_sell,
        'Upgrades': total_upgrades,
        'Downgrades': total_downgrades,
        'Volume': f"{primary_data.get('volume', 0):,}" if primary_data.get('volume') else "N/A",
        'Dividend Yield': f"{primary_data.get('dividend_yield', 0)*100:.2f}%" if primary_data.get('dividend_yield') else "N/A",
        'Beta': f"{primary_data.get('beta', 0):.2f}" if primary_data.get('beta') else "N/A",
        '52W High': f"${primary_data.get('fifty_two_week_high', 0):.2f}" if primary_data.get('fifty_two_week_high') else "N/A",
        '52W Low': f"${primary_data.get('fifty_two_week_low', 0):.2f}" if primary_data.get('fifty_two_week_low') else "N/A",
        'Data Sources': len(data_sources)
    }

# Main data collection
data = []

with st.spinner("Fetching stock data from multiple sources..."):
    for ticker in selected_tickers:
        try:
            stock_data = get_aggregated_data(ticker)
            if stock_data and stock_data['PE'] is not None and stock_data['PE'] <= pe_filter:
                data.append(stock_data)
            time.sleep(0.5)  # Rate limiting
        except Exception as e:
            st.warning(f"Error fetching data for {ticker}: {str(e)}")
            pass

if data:
    df = pd.DataFrame(data)
    
    # Display the dataframe with better formatting
    st.subheader("📊 Multi-Source Stock Screening Results")
    
    # Create a styled dataframe with larger columns
    st.dataframe(
        df,
        column_config={
            "Symbol": st.column_config.TextColumn("Symbol", width="large"),
            "Name": st.column_config.TextColumn("Company Name", width="xlarge"),
            "PE": st.column_config.NumberColumn("P/E Ratio", format="%.2f", width="medium"),
            "Market Cap": st.column_config.TextColumn("Market Cap", width="large"),
            "Price": st.column_config.TextColumn("Current Price", width="large"),
            "Buy": st.column_config.NumberColumn("Buy Recs", width="medium"),
            "Hold": st.column_config.NumberColumn("Hold Recs", width="medium"),
            "Sell": st.column_config.NumberColumn("Sell Recs", width="medium"),
            "Upgrades": st.column_config.NumberColumn("Upgrades", width="medium"),
            "Downgrades": st.column_config.NumberColumn("Downgrades", width="medium"),
            "Volume": st.column_config.TextColumn("Volume", width="large"),
            "Dividend Yield": st.column_config.TextColumn("Div Yield", width="medium"),
            "Beta": st.column_config.TextColumn("Beta", width="medium"),
            "52W High": st.column_config.TextColumn("52W High", width="medium"),
            "52W Low": st.column_config.TextColumn("52W Low", width="medium"),
            "Data Sources": st.column_config.NumberColumn("Sources", width="small")
        },
        hide_index=True,
        use_container_width=True
    )

    # Download button
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 Download CSV"):
            df.to_csv("multi_source_screened_stocks.csv", index=False)
            st.success("Downloaded as multi_source_screened_stocks.csv")
    
    with col2:
        if st.button("📊 Show Summary"):
            st.subheader("📊 Summary Statistics")
            st.write(f"**Total Stocks Found:** {len(df)}")
            st.write(f"**Average P/E Ratio:** {df['PE'].mean():.2f}")
            st.write(f"**Total Buy Recommendations:** {df['Buy'].sum()}")
            st.write(f"**Total Hold Recommendations:** {df['Hold'].sum()}")
            st.write(f"**Total Sell Recommendations:** {df['Sell'].sum()}")
            st.write(f"**Average Data Sources per Stock:** {df['Data Sources'].mean():.1f}")

    # Chart for first selected stock
    if selected_tickers:
        st.subheader(f"📈 Price Chart: {selected_tickers[0]}")
        try:
            chart_ticker = selected_tickers[0]
            hist = yf.download(chart_ticker, period="6mo", auto_adjust=True)
            
            if not hist.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=hist.index, 
                    y=hist['Close'], 
                    name='Close Price',
                    line=dict(color='#FF6B6B', width=2)
                ))
                
                fig.update_layout(
                    title=f"{chart_ticker} - 6 Month Price Chart",
                    xaxis_title="Date",
                    yaxis_title="Price ($)",
                    hovermode='x unified',
                    template='plotly_white'
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning(f"No price data available for {chart_ticker}")
        except Exception as e:
            st.error(f"Error creating chart for {chart_ticker}: {str(e)}")

else:
    st.info("No stocks found matching your criteria. Try adjusting the P/E filter or selecting different stocks.")

# Data source information
st.sidebar.subheader("ℹ️ Data Source Info")
st.sidebar.markdown("""
**Free APIs:**
- **Yahoo Finance**: No API key needed
- **Alpha Vantage**: Free tier available
- **Finnhub**: Free tier available

**Get API Keys:**
- Alpha Vantage: alphavantage.co
- Finnhub: finnhub.io
""")

# Debug section
if st.checkbox("🔍 Show Debug Info"):
    st.subheader("Debug Information")
    st.write("**Available data sources:**")
    st.write(f"- Yahoo Finance: {use_yfinance}")
    st.write(f"- Alpha Vantage: {use_alpha_vantage and bool(ALPHA_VANTAGE_API_KEY)}")
    st.write(f"- Finnhub: {use_finnhub and bool(FINNHUB_API_KEY)}")
    st.write(f"- Quandl: {use_quandl}")
