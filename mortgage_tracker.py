import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
from datetime import datetime, timedelta
import math

# ---------------------------
# Page configuration
# ---------------------------
st.set_page_config(
    page_title="Mortgage Rate Tracker and Refinance Analyzer",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------
# Custom CSS
# ---------------------------
st.markdown("""
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
""", unsafe_allow_html=True)

# ---------------------------
# Utility functions
# ---------------------------
@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_treasury_data():
    """Fetch 10-year Treasury yield data from Yahoo Finance (^TNX)."""
    try:
        treasury = yf.Ticker("^TNX")
        data = treasury.history(period="1y")
        # ^TNX is usually quoted as yield * 10 (e.g., 45.67 == 4.567%)
        # Convert to % if needed.
        if not data.empty:
            last = float(data["Close"].iloc[-1])
            scale = 10.0 if last > 20 else 1.0  # crude but robust detector
            data = data.copy()
            data["Close"] = data["Close"] / scale
        return data
    except Exception as e:
        st.error(f"Error fetching Treasury data: {e}")
        return None

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_mortgage_rate_estimate(treasury_yield_pct: float) -> float:
    """Estimate mortgage rate based on 10-year Treasury yield (in %)."""
    # Typical spread range 1.5–2.5; choose a middle value
    mortgage_spread = 2.1
    return float(treasury_yield_pct) + mortgage_spread

def calculate_monthly_payment(principal: float, rate_pct: float, years: float) -> float:
    """Monthly mortgage payment for a fixed-rate loan."""
    if years <= 0:
        return 0.0
    monthly_rate = rate_pct / 12.0 / 100.0
    n = int(round(years * 12))
    if n <= 0:
        return 0.0
    if monthly_rate == 0:
        return principal / n
    return principal * (monthly_rate * (1 + monthly_rate) ** n) / ((1 + monthly_rate) ** n - 1)

def remaining_balance(principal: float, rate_pct: float, total_payments: int, payments_made: int) -> float:
    """Amortized remaining balance after payments_made of total_payments."""
    monthly_rate = rate_pct / 12.0 / 100.0
    n = int(total_payments)
    k = int(max(0, min(payments_made, n)))
    if n <= 0:
        return principal
    if monthly_rate == 0:
        # Straight-line principal paydown
        paid = principal * (k / n)
        return max(0.0, principal - paid)
    # Standard amortization remaining balance formula
    pmt = principal * (monthly_rate * (1 + monthly_rate) ** n) / ((1 + monthly_rate) ** n - 1)
    bal = principal * (1 + monthly_rate) ** k - pmt * ((1 + monthly_rate) ** k - 1) / monthly_rate
    return max(0.0, float(bal))

def calculate_refinance_savings(current_balance: float, current_rate_pct: float, new_rate_pct: float,
                                remaining_years: float, closing_costs: float = 5000.0):
    """Compute savings if refinancing current_balance into a new 30-year loan."""
    current_payment = calculate_monthly_payment(current_balance, current_rate_pct, remaining_years)
    new_payment = calculate_monthly_payment(current_balance, new_rate_pct, 30)  # new 30-year loan
    monthly_savings = current_payment - new_payment
    total_savings = monthly_savings * remaining_years * 12 - closing_costs
    break_even_months = (closing_costs / monthly_savings) if monthly_savings > 0 else float("inf")
    return {
        "current_payment": current_payment,
        "new_payment": new_payment,
        "monthly_savings": monthly_savings,
        "total_savings": total_savings,
        "break_even_months": break_even_months
    }

def get_rate_prediction_insight(current_treasury_pct: float, historical_data: pd.DataFrame):
    """Provide quick insight on trend/volatility from last 30 sessions."""
    closes = historical_data["Close"].dropna()
    if len(closes) == 0:
        return "—", "—"
    tail = closes.tail(30)
    recent_avg = tail.mean()
    trend = "📈 Rising" if current_treasury_pct > recent_avg else "📉 Falling"
    volatility = tail.std()
    if volatility > 0.30:
        stability = "High volatility"
    elif volatility > 0.15:
        stability = "Moderate volatility"
    else:
        stability = "Low volatility"
    return trend, stability

# ---------------------------
# Main App
# ---------------------------
def main():
    st.markdown('<div class="main-header">🏠 Mortgage Rate Tracker & Refinance Analyzer</div>', unsafe_allow_html=True)

    # Sidebar - User Inputs
    st.sidebar.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.sidebar.header("📊 Your Mortgage Details")

    current_rate = st.sidebar.number_input("Current Mortgage Rate (%)", value=6.125, step=0.001, format="%.3f")
    loan_amount = st.sidebar.number_input("Original Loan Amount ($)", value=400_000, step=1000)
    loan_start = st.sidebar.date_input("Loan Start Date", value=datetime(2025, 6, 1))
    remaining_payments = st.sidebar.number_input("Remaining Payments", value=349, step=1, min_value=0)
    prepaid_principal = st.sidebar.number_input("Prepaid Principal ($)", value=0, step=100, min_value=0)

    # Refinance parameters
    st.sidebar.markdown("### 🔄 Refinance Parameters")
    refinance_threshold = st.sidebar.slider("Refinance Threshold (rate difference %)", 0.1, 2.0, 0.5, 0.1)
    closing_costs = st.sidebar.number_input("Estimated Closing Costs ($)", value=5000, step=500, min_value=0)
    st.sidebar.markdown("</div>", unsafe_allow_html=True)

    # Derived values
    total_payments = 360
    payments_made = max(0, total_payments - int(remaining_payments))
    # Compute a realistic current balance from amortization (minus any prepaid principal)
    current_balance_raw = remaining_balance(loan_amount, current_rate, total_payments, payments_made)
    current_balance = max(0.0, current_balance_raw - float(prepaid_principal))
    remaining_years = max(0.0, float(remaining_payments) / 12.0)

    # Layout
    col1, col2 = st.columns([2, 1])

    with col1:
        with st.spinner("Fetching real-time Treasury data..."):
            treasury_data = get_treasury_data()

        if treasury_data is not None and not treasury_data.empty:
            current_treasury = float(treasury_data["Close"].iloc[-1])  # already in %
            estimated_mortgage_rate = get_mortgage_rate_estimate(current_treasury)

            # Charts
            st.subheader("📈 10-Year Treasury Yield & Estimated Mortgage Rates")

            fig = make_subplots(
                rows=2, cols=1,
                subplot_titles=("10-Year Treasury Yield (%)", "Estimated 30-Year Mortgage Rate (%)"),
                vertical_spacing=0.12
            )

            # Treasury yield chart
            fig.add_trace(
                go.Scatter(
                    x=treasury_data.index,
                    y=treasury_data["Close"],
                    name="10-Year Treasury",
                    line=dict(width=2)
                ),
                row=1, col=1
            )

            # Estimated mortgage rate series (Treasury + 2.1%)
            estimated_series = treasury_data["Close"] + 2.1
            fig.add_trace(
                go.Scatter(
                    x=treasury_data.index,
                    y=estimated_series,
                    name="Est. Mortgage Rate",
                    line=dict(width=2)
                ),
                row=2, col=1
            )

            # Horizontal lines in subplots via shapes (use yref 'y1'/'y2' and xref 'x1'/'x2')
            x0 = treasury_data.index.min()
            x1 = treasury_data.index.max()

            # Current rate line (subplot 2)
            fig.add_shape(
                type="line",
                x0=x0, x1=x1,
                y0=current_rate, y1=current_rate,
                xref="x2", yref="y2",
                line=dict(dash="dash")
            )
            fig.add_annotation(
                x=x1, y=current_rate, xref="x2", yref="y2",
                xanchor="right", yanchor="bottom",
                text=f"Your Current Rate: {current_rate:.3f}%",
                showarrow=False
            )

            # Refinance threshold line (subplot 2)
            refinance_rate = current_rate - float(refinance_threshold)
            fig.add_shape(
                type="line",
                x0=x0, x1=x1,
                y0=refinance_rate, y1=refinance_rate,
                xref="x2", yref="y2",
                line=dict(dash="dot")
            )
            fig.add_annotation(
                x=x1, y=refinance_rate, xref="x2", yref="y2",
                xanchor="right", yanchor="bottom",
                text=f"Refi Threshold: {refinance_rate:.3f}%",
                showarrow=False
            )

            fig.update_layout(height=600, showlegend=True, margin=dict(l=30, r=30, t=60, b=30))
            fig.update_xaxes(title_text="Date", row=1, col=1)
            fig.update_xaxes(title_text="Date", row=2, col=1)
            fig.update_yaxes(title_text="Yield (%)", row=1, col=1)
            fig.update_yaxes(title_text="Rate (%)", row=2, col=1)

            st.plotly_chart(fig, use_container_width=True)

            # Rate insights
            trend, stability = get_rate_prediction_insight(current_treasury, treasury_data)

            st.subheader("🔍 Current Market Analysis")
            insight_col1, insight_col2, insight_col3 = st.columns(3)

            with insight_col1:
                delta_val = 0.0
                if len(treasury_data) >= 2:
                    delta_val = current_treasury - float(treasury_data["Close"].iloc[-2])
                st.metric("Current 10Y Treasury", f"{current_treasury:.3f}%", delta=f"{delta_val:.3f}%")

            with insight_col2:
                st.metric("Est. Mortgage Rate", f"{estimated_mortgage_rate:.3f}%",
                          delta=f"{estimated_mortgage_rate - current_rate:.3f}%")

            with insight_col3:
                rate_diff = current_rate - estimated_mortgage_rate  # positive means your rate > est (bad); we want est < current
                if (current_rate - estimated_mortgage_rate) >= refinance_threshold:
                    refinance_status_text = "⏳ Monitor Rates"  # est still below by big margin? Clarify:
                    # Actually, if estimated < current by at least threshold => consider refi
                    refinance_status_text = "✅ Consider Refinancing"
                    css_class = "highlight-green"
                else:
                    refinance_status_text = "⏳ Monitor Rates"
                    css_class = "highlight-red"
                st.markdown(f"**Refinance Status:** <span class='{css_class}'>{refinance_status_text}</span>", unsafe_allow_html=True)

            # Detailed refinance analysis
            st.subheader("💰 Refinance Analysis")
            if estimated_mortgage_rate < current_rate:
                savings = calculate_refinance_savings(
                    current_balance=current_balance,
                    current_rate_pct=current_rate,
                    new_rate_pct=estimated_mortgage_rate,
                    remaining_years=remaining_years,
                    closing_costs=closing_costs
                )

                analysis_col1, analysis_col2 = st.columns(2)

                with analysis_col1:
                    st.markdown("#### Current vs. Potential New Payment")
                    st.write(f"**Current Monthly Payment:** ${savings['current_payment']:,.2f}")
                    st.write(f"**Potential New Payment:** ${savings['new_payment']:,.2f}")
                    if savings["monthly_savings"] > 0:
                        st.write(f"**Monthly Savings:** <span class='highlight-green'>${savings['monthly_savings']:,.2f}</span>", unsafe_allow_html=True)
                    else:
                        st.write(f"**Monthly Increase:** <span class='highlight-red'>${abs(savings['monthly_savings']):,.2f}</span>", unsafe_allow_html=True)

                with analysis_col2:
                    st.markdown("#### Break-Even Analysis")
                    if math.isfinite(savings["break_even_months"]):
                        st.write(f"**Break-Even Time:** {savings['break_even_months']:.1f} months")
                        st.write(f"**Total Savings (net of costs):** ${savings['total_savings']:,.2f}")
                    else:
                        st.write("**Break-Even:** Not applicable (no savings)")

                # Recommendation
                if (current_rate - estimated_mortgage_rate) >= refinance_threshold and savings["monthly_savings"] > 0:
                    st.success("🎯 **Recommendation:** Strong candidate for refinancing! You could save significantly.")
                elif (current_rate - estimated_mortgage_rate) >= 0.25:
                    st.info("💡 **Recommendation:** Consider refinancing. Monitor rates for better opportunities.")
                else:
                    st.warning("⚠️ **Recommendation:** Current rates do not justify refinancing yet. Keep monitoring.")
            else:
                st.info("Current estimate is not below your rate; refinancing likely not beneficial right now.")

        else:
            st.error("Unable to fetch Treasury data. Please check your internet connection and try again.")

    with col2:
        # Loan summary
        st.subheader("📋 Your Loan Summary")
        end_date = loan_start + timedelta(days=30 * 360)  # approximate 30 years
        loan_summary = f"""
        <div class="metric-container">
        <strong>Loan Details:</strong><br>
        • Original Amount: ${loan_amount:,.0f}<br>
        • Current Rate: {current_rate:.3f}%<br>
        • Start Date: {loan_start.strftime('%b %Y')}<br>
        • End Date (approx): {end_date.strftime('%b %Y')}<br>
        • Payments Made: {payments_made}<br>
        • Remaining Payments: {remaining_payments}<br>
        • Current Balance (est): ${current_balance:,.0f}<br>
        • Prepaid Principal: ${prepaid_principal:,.0f}
        </div>
        """
        st.markdown(loan_summary, unsafe_allow_html=True)

        # Rate alerts
        st.subheader("🔔 Rate Alerts")
        treasury_data = st.session_state.get("treasury_cache") if "treasury_cache" in st.session_state else None  # optional
        # Re-fetch estimated rate safely if needed
        td = get_treasury_data()
        if td is not None and not td.empty:
            ct = float(td["Close"].iloc[-1])
            est_rate = get_mortgage_rate_estimate(ct)
            alert_threshold = current_rate - float(refinance_threshold)
            if est_rate <= alert_threshold:
                st.success(f"🎉 ALERT: Rates hit your threshold! Current estimate: {est_rate:.3f}%")
            else:
                st.info(f"📊 Monitoring rates. Target: {alert_threshold:.3f}% (Current: {est_rate:.3f}%)")
        else:
            st.info("Rate alerts unavailable (no market data).")

        # Historical context
        st.subheader("📚 Historical Context")
        historical_context = """
        <div class="metric-container">
        <strong>Rate History (rough ranges):</strong><br>
        • 2020–2021: ~2.5–3.5% (Historic lows)<br>
        • 2022–2023: ~3.0–7.5% (Rising cycle)<br>
        • 2024–2025: ~6.0–7.5% (Recent range)<br><br>
        <strong>Typical Refinance Triggers:</strong><br>
        • ≥ 0.5% rate drop vs. your rate<br>
        • Break-even &lt; 24 months<br>
        • Plan to stay in home ≥ 3 years
        </div>
        """
        st.markdown(historical_context, unsafe_allow_html=True)

    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; font-size: 0.9rem;">
    📊 Data source: Yahoo Finance (10Y Treasury) • 🔄 Updates every 5 minutes<br>
    ⚠️ Estimates only. Consult a mortgage professional for personalized advice.
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()