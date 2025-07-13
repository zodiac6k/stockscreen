import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objs as go
import os

st.title("📈 Stock Screener - Enhanced Version")

# Load ticker list
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(script_dir, "tickers.csv")
df = pd.read_csv(csv_path)
print(df.columns)
tickers = df['Ticker'].tolist()

selected_tickers = st.multiselect("Select stocks", tickers[:50])  # Limit for speed

pe_filter = st.slider("Max P/E Ratio", 0, 100, 30)

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

# Function to get brokerage recommendations
def get_recommendations(stock):
    try:
        # Get analyst recommendations
        recommendations = stock.recommendations
        if recommendations is not None and not recommendations.empty:
            # Get the most recent recommendations
            recent_recs = recommendations.tail(10)
            
            # Count buy, hold, sell recommendations
            buy_count = len(recent_recs[recent_recs['To Grade'].str.contains('Buy|Strong Buy|Outperform', case=False, na=False)])
            hold_count = len(recent_recs[recent_recs['To Grade'].str.contains('Hold|Neutral|Equal-Weight', case=False, na=False)])
            sell_count = len(recent_recs[recent_recs['To Grade'].str.contains('Sell|Strong Sell|Underperform', case=False, na=False)])
            
            # Get upgrade/downgrade info
            upgrades = len(recent_recs[recent_recs['To Grade'] > recent_recs['From Grade']])
            downgrades = len(recent_recs[recent_recs['To Grade'] < recent_recs['From Grade']])
            
            return buy_count, hold_count, sell_count, upgrades, downgrades
        else:
            return 0, 0, 0, 0, 0
    except:
        return 0, 0, 0, 0, 0

data = []

with st.spinner("Fetching stock data and recommendations..."):
    for ticker in selected_tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            if info['trailingPE'] is not None and info['trailingPE'] <= pe_filter:
                # Get recommendations
                buy_count, hold_count, sell_count, upgrades, downgrades = get_recommendations(stock)
                
                data.append({
                    'Symbol': ticker,
                    'Name': info.get('shortName', ''),
                    'PE': round(info['trailingPE'], 2) if info['trailingPE'] else None,
                    'Market Cap': format_market_cap(info.get('marketCap')),
                    'Price': f"${info.get('currentPrice', 0):.2f}" if info.get('currentPrice') else "N/A",
                    'Buy': buy_count,
                    'Hold': hold_count,
                    'Sell': sell_count,
                    'Upgrades': upgrades,
                    'Downgrades': downgrades
                })
        except Exception as e:
            st.warning(f"Error fetching data for {ticker}: {str(e)}")
            pass

if data:
    df = pd.DataFrame(data)
    
    # Display the dataframe with better formatting
    st.subheader("📊 Screened Stocks Results")
    
    # Create a styled dataframe
    st.dataframe(
        df,
        column_config={
            "Symbol": st.column_config.TextColumn("Symbol", width="medium"),
            "Name": st.column_config.TextColumn("Company Name", width="large"),
            "PE": st.column_config.NumberColumn("P/E Ratio", format="%.2f"),
            "Market Cap": st.column_config.TextColumn("Market Cap", width="medium"),
            "Price": st.column_config.TextColumn("Current Price", width="medium"),
            "Buy": st.column_config.NumberColumn("Buy Recs", width="small"),
            "Hold": st.column_config.NumberColumn("Hold Recs", width="small"),
            "Sell": st.column_config.NumberColumn("Sell Recs", width="small"),
            "Upgrades": st.column_config.NumberColumn("Upgrades", width="small"),
            "Downgrades": st.column_config.NumberColumn("Downgrades", width="small")
        },
        hide_index=True
    )

    # Download button
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 Download CSV"):
            df.to_csv("screened_stocks.csv", index=False)
            st.success("Downloaded as screened_stocks.csv")
    
    with col2:
        if st.button("📊 Show Summary"):
            st.subheader(" Summary Statistics")
            st.write(f"**Total Stocks Found:** {len(df)}")
            st.write(f"**Average P/E Ratio:** {df['PE'].mean():.2f}")
            st.write(f"**Total Buy Recommendations:** {df['Buy'].sum()}")
            st.write(f"**Total Hold Recommendations:** {df['Hold'].sum()}")
            st.write(f"**Total Sell Recommendations:** {df['Sell'].sum()}")

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
