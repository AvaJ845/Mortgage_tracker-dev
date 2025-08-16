import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import yfinance as yf
from datetime import datetime, timedelta
import requests
import time

# Page configuration

st.set_page_config(
page_title=“Mortgage Rate Tracker & Refinance Analyzer”,
page_icon=“🏠”,
layout=“wide”,
initial_sidebar_state=“expanded”
)

# Custom CSS

st.markdown(”””

<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-container {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
    .highlight-green {
        color: #28a745;
        font-weight: bold;
    }
    .highlight-red {
        color: #dc3545;
        font-weight: bold;
    }
    .sidebar-section {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
</style>

“””, unsafe_allow_html=True)

# Functions

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_treasury_data():
“”“Fetch 10-year Treasury yield data”””
try:
# Fetch 10-year Treasury yield (^TNX)
treasury = yf.Ticker(”^TNX”)
data = treasury.history(period=“1y”)
return data
except Exception as e:
st.error(f”Error fetching Treasury data: {e}”)
return None

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_mortgage_rate_estimate(treasury_yield):
“”“Estimate mortgage rate based on 10-year Treasury yield”””
# Historical spread between 30-year mortgage and 10-year Treasury is typically 1.5-2.5%
# Current market conditions suggest a spread of around 2.0-2.3%
mortgage_spread = 2.1  # Average spread
estimated_mortgage_rate = treasury_yield + mortgage_spread
return estimated_mortgage_rate

def calculate_monthly_payment(principal, rate, years):
“”“Calculate monthly mortgage payment”””
monthly_rate = rate / 12 / 100
num_payments = years * 12
if monthly_rate == 0:
return principal / num_payments
return principal * (monthly_rate * (1 + monthly_rate)**num_payments) / ((1 + monthly_rate)**num_payments - 1)

def calculate_refinance_savings(current_balance, current_rate, new_rate, remaining_years, closing_costs=5000):
“”“Calculate potential refinance savings”””
current_payment = calculate_monthly_payment(current_balance, current_rate, remaining_years)
new_payment = calculate_monthly_payment(current_balance, new_rate, 30)  # New 30-year loan

```
monthly_savings = current_payment - new_payment
total_savings = monthly_savings * remaining_years * 12 - closing_costs

if monthly_savings > 0:
    break_even_months = closing_costs / monthly_savings
else:
    break_even_months = float('inf')

return {
    'current_payment': current_payment,
    'new_payment': new_payment,
    'monthly_savings': monthly_savings,
    'total_savings': total_savings,
    'break_even_months': break_even_months
}
```

def get_rate_prediction_insight(current_treasury, historical_data):
“”“Provide insights on rate trends”””
recent_avg = historical_data[‘Close’].tail(30).mean()
trend = “📈 Rising” if current_treasury > recent_avg else “📉 Falling”

```
volatility = historical_data['Close'].tail(30).std()
if volatility > 0.3:
    stability = "High volatility"
elif volatility > 0.15:
    stability = "Moderate volatility"
else:
    stability = "Low volatility"

return trend, stability
```

# Main App

def main():
st.markdown(’<div class="main-header">🏠 Mortgage Rate Tracker & Refinance Analyzer</div>’, unsafe_allow_html=True)

```
# Sidebar - User Inputs
st.sidebar.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
st.sidebar.header("📊 Your Mortgage Details")

# User's mortgage information
current_rate = st.sidebar.number_input("Current Mortgage Rate (%)", value=6.125, step=0.001, format="%.3f")
loan_amount = st.sidebar.number_input("Original Loan Amount ($)", value=400000, step=1000)
loan_start = st.sidebar.date_input("Loan Start Date", value=datetime(2025, 6, 1))
remaining_payments = st.sidebar.number_input("Remaining Payments", value=349, step=1)
prepaid_principal = st.sidebar.number_input("Prepaid Principal ($)", value=0, step=100)

# Calculate current loan balance
original_years = 30
months_elapsed = 360 - remaining_payments
current_balance = loan_amount - prepaid_principal

# Refinance parameters
st.sidebar.markdown("### 🔄 Refinance Parameters")
refinance_threshold = st.sidebar.slider("Refinance Threshold (rate difference %)", 0.1, 2.0, 0.5, 0.1)
closing_costs = st.sidebar.number_input("Estimated Closing Costs ($)", value=5000, step=500)

st.sidebar.markdown('</div>', unsafe_allow_html=True)

# Main content
col1, col2 = st.columns([2, 1])

with col1:
    # Fetch real-time data
    with st.spinner("Fetching real-time Treasury data..."):
        treasury_data = get_treasury_data()
    
    if treasury_data is not None and not treasury_data.empty:
        current_treasury = treasury_data['Close'].iloc[-1]
        estimated_mortgage_rate = get_mortgage_rate_estimate(current_treasury)
        
        # Rate tracking chart
        st.subheader("📈 10-Year Treasury Yield & Estimated Mortgage Rates")
        
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=('10-Year Treasury Yield', 'Estimated 30-Year Mortgage Rate'),
            vertical_spacing=0.12
        )
        
        # Treasury yield chart
        fig.add_trace(
            go.Scatter(
                x=treasury_data.index,
                y=treasury_data['Close'],
                name='10-Year Treasury',
                line=dict(color='blue', width=2)
            ),
            row=1, col=1
        )
        
        # Estimated mortgage rates
        estimated_rates = treasury_data['Close'] + 2.1  # Add spread
        fig.add_trace(
            go.Scatter(
                x=treasury_data.index,
                y=estimated_rates,
                name='Est. Mortgage Rate',
                line=dict(color='red', width=2)
            ),
            row=2, col=1
        )
        
        # Add current rate line
        fig.add_hline(
            y=current_rate,
            line_dash="dash",
            line_color="green",
            annotation_text=f"Your Current Rate: {current_rate}%",
            row=2, col=1
        )
        
        # Add refinance threshold line
        refinance_rate = current_rate - refinance_threshold
        fig.add_hline(
            y=refinance_rate,
            line_dash="dot",
            line_color="orange",
            annotation_text=f"Refinance Threshold: {refinance_rate:.3f}%",
            row=2, col=1
        )
        
        fig.update_layout(height=600, showlegend=True)
        fig.update_xaxes(title_text="Date")
        fig.update_yaxes(title_text="Yield (%)", row=1, col=1)
        fig.update_yaxes(title_text="Rate (%)", row=2, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Rate insights
        trend, stability = get_rate_prediction_insight(current_treasury, treasury_data)
        
        st.subheader("🔍 Current Market Analysis")
        
        insight_col1, insight_col2, insight_col3 = st.columns(3)
        
        with insight_col1:
            st.metric(
                "Current 10Y Treasury",
                f"{current_treasury:.3f}%",
                delta=f"{current_treasury - treasury_data['Close'].iloc[-2]:.3f}%"
            )
        
        with insight_col2:
            st.metric(
                "Est. Mortgage Rate",
                f"{estimated_mortgage_rate:.3f}%",
                delta=f"{estimated_mortgage_rate - current_rate:.3f}%"
            )
        
        with insight_col3:
            rate_diff = current_rate - estimated_mortgage_rate
            if rate_diff >= refinance_threshold:
                refinance_status = "✅ Consider Refinancing"
                status_color = "green"
            else:
                refinance_status = "⏳ Monitor Rates"
                status_color = "orange"
            
            st.markdown(f"**Refinance Status:** <span class='highlight-{status_color.replace('green', 'green').replace('orange', 'red')}'>{refinance_status}</span>", unsafe_allow_html=True)
        
        # Detailed refinance analysis
        st.subheader("💰 Refinance Analysis")
        
        if estimated_mortgage_rate < current_rate:
            savings = calculate_refinance_savings(
                current_balance, current_rate, estimated_mortgage_rate, 
                remaining_payments/12, closing_costs
            )
            
            analysis_col1, analysis_col2 = st.columns(2)
            
            with analysis_col1:
                st.markdown("#### Current vs. Potential New Payment")
                st.write(f"**Current Monthly Payment:** ${savings['current_payment']:,.2f}")
                st.write(f"**Potential New Payment:** ${savings['new_payment']:,.2f}")
                
                if savings['monthly_savings'] > 0:
                    st.write(f"**Monthly Savings:** <span class='highlight-green'>${savings['monthly_savings']:,.2f}</span>", unsafe_allow_html=True)
                else:
                    st.write(f"**Monthly Increase:** <span class='highlight-red'>${abs(savings['monthly_savings']):,.2f}</span>", unsafe_allow_html=True)
            
            with analysis_col2:
                st.markdown("#### Break-Even Analysis")
                if savings['break_even_months'] != float('inf'):
                    st.write(f"**Break-Even Time:** {savings['break_even_months']:.1f} months")
                    st.write(f"**Total Savings:** ${savings['total_savings']:,.2f}")
                else:
                    st.write("**Break-Even:** Not applicable (no savings)")
            
            # Recommendation
            if rate_diff >= refinance_threshold and savings['monthly_savings'] > 0:
                st.success("🎯 **Recommendation:** Strong candidate for refinancing! You could save significantly.")
            elif rate_diff >= 0.25:
                st.info("💡 **Recommendation:** Consider refinancing. Monitor rates for better opportunities.")
            else:
                st.warning("⚠️ **Recommendation:** Current rates don't justify refinancing yet. Keep monitoring.")
        
    else:
        st.error("Unable to fetch Treasury data. Please check your internet connection and try again.")

with col2:
    # Loan summary
    st.subheader("📋 Your Loan Summary")
    
    loan_summary = f"""
    <div class="metric-container">
    <strong>Loan Details:</strong><br>
    • Original Amount: ${loan_amount:,}<br>
    • Current Rate: {current_rate}%<br>
    • Start Date: {loan_start.strftime('%b %Y')}<br>
    • End Date: {(loan_start + timedelta(days=30*360)).strftime('%b %Y')}<br>
    • Remaining Payments: {remaining_payments}<br>
    • Current Balance: ${current_balance:,}<br>
    • Prepaid Principal: ${prepaid_principal:,}
    </div>
    """
    st.markdown(loan_summary, unsafe_allow_html=True)
    
    # Rate alerts
    st.subheader("🔔 Rate Alerts")
    
    if treasury_data is not None:
        current_treasury = treasury_data['Close'].iloc[-1]
        estimated_mortgage_rate = get_mortgage_rate_estimate(current_treasury)
        
        alert_threshold = current_rate - refinance_threshold
        
        if estimated_mortgage_rate <= alert_threshold:
            st.success(f"🎉 ALERT: Rates hit your threshold! Current estimate: {estimated_mortgage_rate:.3f}%")
        else:
            st.info(f"📊 Monitoring rates. Target: {alert_threshold:.3f}% (Current: {estimated_mortgage_rate:.3f}%)")
    
    # Historical context
    st.subheader("📚 Historical Context")
    
    historical_context = """
    <div class="metric-container">
    <strong>Rate History:</strong><br>
    • 2020-2021: ~2.5-3.5% (Historic lows)<br>
    • 2022-2023: 3.0-7.5% (Rising cycle)<br>
    • 2024-2025: 6.0-7.5% (Current range)<br><br>
    <strong>Typical Refinance Triggers:</strong><br>
    • 0.5%+ rate drop<br>
    • Break-even < 24 months<br>
    • Staying in home 3+ years
    </div>
    """
    st.markdown(historical_context, unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; font-size: 0.9rem;'>
📊 Data sources: Yahoo Finance (10Y Treasury) | 🔄 Updates every 5 minutes<br>
⚠️ This tool provides estimates only. Consult with a mortgage professional for personalized advice.
</div>
""", unsafe_allow_html=True)
```

if **name** == “**main**”:
main()
