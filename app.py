import re
import json
from datetime import datetime, timedelta
from collections import defaultdict
import streamlit as st
import pandas as pd
import plotly.express as px
from PIL import Image

# =========================================================
# 1. PAGE SETUP & FAVICON CONFIGURATION
# =========================================================

try:
    logo_image = Image.open("assets/images/anulakshyalog.jpg")
    page_icon_setting = logo_image
except Exception:
    page_icon_setting = "💳"
    logo_image = None

st.set_page_config(
    page_title="Anulaksya — Recurring Debit & Mandate Intelligence",
    page_icon=page_icon_setting,
    layout="wide"
)

# =========================================================
# 2. REFERENCE KNOWLEDGE BASE & PATTERN MATCHING
# =========================================================

MERCHANT_KNOWLEDGE_BASE = [
    {
        "pattern": r"(?i)(AMZN|AMAZON|PRIME\s*MEMBER)",
        "clean_name": "Amazon Prime",
        "category": "Entertainment & Shopping",
        "rail_type": "UPI AutoPay / Card SI",
        "cancellation_steps": [
            "Open Amazon App > Account > Prime Membership",
            "Select 'Manage Membership' > End Membership",
            "Confirm cancellation; benefits continue till end of cycle."
        ]
    },
    {
        "pattern": r"(?i)(NFLX|NETFLIX)",
        "clean_name": "Netflix India",
        "category": "OTT Streaming",
        "rail_type": "Card Standing Instruction",
        "cancellation_steps": [
            "Log into Netflix.com via browser",
            "Go to Account > Membership & Billing",
            "Click 'Cancel Membership' and confirm"
        ]
    },
    {
        "pattern": r"(?i)(SPOTIFY|SPTF)",
        "clean_name": "Spotify Premium",
        "category": "Audio Streaming",
        "rail_type": "UPI AutoPay",
        "cancellation_steps": [
            "Open UPI App (GPay/PhonePe/Paytm) > Autopay Settings",
            "Locate 'Spotify India' mandate",
            "Click 'Pause Mandate' or 'Revoke Mandate' and enter UPI PIN"
        ]
    },
    {
        "pattern": r"(?i)(AWS|AMAZON\s*WEB\s*SERVICES)",
        "clean_name": "AWS Cloud Hosting",
        "category": "Developer Infrastructure",
        "rail_type": "Credit Card SI",
        "cancellation_steps": [
            "Log into AWS Management Console > Billing Dashboard",
            "Terminate active EC2/S3 resources to halt meter",
            "Close AWS Account under Account Settings"
        ]
    },
    {
        "pattern": r"(?i)(SWIGGY|ONE\s*SUPER|SWIGGYONE)",
        "clean_name": "Swiggy One Membership",
        "category": "Food & Delivery",
        "rail_type": "UPI AutoPay",
        "cancellation_steps": [
            "Open Swiggy App > Account > Swiggy One Membership",
            "Disable Auto-Renewal under Membership Settings",
            "Or revoke UPI Mandate directly in UPI payment app"
        ]
    },
    {
        "pattern": r"(?i)(CULT\.|CULTFIT|CUREFIT)",
        "clean_name": "Cult.fit Pass",
        "category": "Fitness & Health",
        "rail_type": "eNACH / UPI Mandate",
        "cancellation_steps": [
            "Open Cult.fit App > Profile > Active Subscriptions",
            "Select Membership > Cancel Auto-Renewal",
            "If non-responsive, submit eNACH mandate cancellation at issuing bank"
        ]
    },
    {
        "pattern": r"(?i)(OPENAI|CHATGPT)",
        "clean_name": "OpenAI / ChatGPT Plus",
        "category": "AI Tools & Productivity",
        "rail_type": "Credit Card SI",
        "cancellation_steps": [
            "Log into chatgpt.com > My Account",
            "Manage My Subscription > Cancel Subscription"
        ]
    }
]

# =========================================================
# 3. RECURRING DEBIT REASONING ENGINE
# =========================================================

class RecurringPaymentAnalyzer:
    def __init__(self, knowledge_base):
        self.kb = knowledge_base

    def normalize_merchant(self, raw_descriptor):
        for entry in self.kb:
            match = re.search(entry["pattern"], raw_descriptor)
            if match:
                return {
                    "clean_name": entry["clean_name"],
                    "category": entry["category"],
                    "rail_type": entry["rail_type"],
                    "cancellation_steps": entry["cancellation_steps"]
                }
        return {
            "clean_name": raw_descriptor.strip(),
            "category": "Uncategorized Subscription",
            "rail_type": "Unknown Mandate Rail",
            "cancellation_steps": [
                "Log into NetBanking > eMandate / Autopay Section",
                "Issue explicit mandate revocation request to bank grievance cell"
            ]
        }

    def analyze_transactions(self, raw_transactions):
        grouped = defaultdict(list)
        for tx in raw_transactions:
            norm = self.normalize_merchant(tx["descriptor"])
            tx_data = {**tx, **norm}
            tx_data["date_obj"] = datetime.strptime(tx["date"], "%Y-%m-%d")
            grouped[norm["clean_name"]].append(tx_data)

        commitments = []
        predictions = []
        total_annual_leak = 0.0

        for merchant, txs in grouped.items():
            if len(txs) < 2:
                # Flag potential trial conversion single debit
                if len(txs) == 1 and txs[0]["amount"] > 0:
                    latest = txs[0]
                    commitments.append({
                        "merchant": merchant,
                        "category": latest["category"],
                        "rail_type": latest["rail_type"],
                        "last_debit_date": latest["date"],
                        "latest_amount": latest["amount"],
                        "annualized_impact": round(latest["amount"] * 12, 2),
                        "frequency": "Single / New Commitment",
                        "has_price_hike": False,
                        "price_hike_details": [],
                        "is_trial_conversion": True,
                        "cancellation_steps": latest["cancellation_steps"],
                        "next_estimated_date": (latest["date_obj"] + timedelta(days=30)).strftime("%Y-%m-%d")
                    })
                    total_annual_leak += latest["amount"] * 12
                continue

            txs.sort(key=lambda x: x["date_obj"])

            intervals = []
            price_changes = []
            for i in range(1, len(txs)):
                delta_days = (txs[i]["date_obj"] - txs[i-1]["date_obj"]).days
                intervals.append(delta_days)
                price_diff = txs[i]["amount"] - txs[i-1]["amount"]
                if price_diff > 0:
                    price_changes.append({
                        "date": txs[i]["date"],
                        "old_amount": txs[i-1]["amount"],
                        "new_amount": txs[i]["amount"],
                        "increase_pct": round((price_diff / max(txs[i-1]["amount"], 1)) * 100, 1)
                    })

            avg_interval = sum(intervals) / len(intervals) if intervals else 30
            latest_tx = txs[-1]
            earliest_tx = txs[0]

            # Classification
            if 25 <= avg_interval <= 35:
                commitment_type = "Monthly Recurring"
                annualized_cost = latest_tx["amount"] * 12
                next_date = latest_tx["date_obj"] + timedelta(days=30)
            elif 340 <= avg_interval <= 390:
                commitment_type = "Annual Auto-Renewal"
                annualized_cost = latest_tx["amount"]
                next_date = latest_tx["date_obj"] + timedelta(days=365)
            elif 80 <= avg_interval <= 100:
                commitment_type = "Quarterly Recurring"
                annualized_cost = latest_tx["amount"] * 4
                next_date = latest_tx["date_obj"] + timedelta(days=90)
            else:
                commitment_type = "Irregular / Variable Cycle"
                annualized_cost = latest_tx["amount"] * (365 / max(avg_interval, 1))
                next_date = latest_tx["date_obj"] + timedelta(days=int(avg_interval))

            is_trial = (earliest_tx["amount"] <= 10 and latest_tx["amount"] > 100)
            total_annual_leak += annualized_cost

            next_date_str = next_date.strftime("%Y-%m-%d")

            commitments.append({
                "merchant": merchant,
                "category": latest_tx["category"],
                "rail_type": latest_tx["rail_type"],
                "last_debit_date": latest_tx["date"],
                "latest_amount": latest_tx["amount"],
                "annualized_impact": round(annualized_cost, 2),
                "frequency": commitment_type,
                "has_price_hike": len(price_changes) > 0,
                "price_hike_details": price_changes,
                "is_trial_conversion": is_trial,
                "cancellation_steps": latest_tx["cancellation_steps"],
                "next_estimated_date": next_date_str
            })

            predictions.append({
                "Merchant": merchant,
                "Category": latest_tx["category"],
                "Expected Date": next_date_str,
                "Estimated Charge": f"₹{latest_tx['amount']:,.2f}",
                "Rail": latest_tx["rail_type"]
            })

        return {
            "total_annual_leak": round(total_annual_leak, 2),
            "total_commitments_found": len(commitments),
            "commitments": commitments,
            "predictions": predictions
        }

# =========================================================
# 4. SYNTHETIC BANK STATEMENT DATASET
# =========================================================

DEFAULT_STATEMENT = [
    {"date": "2025-10-15", "descriptor": "UPI/NFLX*NETFLIX/983724/P2M", "amount": 649.0},
    {"date": "2025-11-15", "descriptor": "UPI/NFLX*NETFLIX/983724/P2M", "amount": 649.0},
    {"date": "2025-12-15", "descriptor": "UPI/NFLX*NETFLIX/983724/P2M", "amount": 649.0},
    {"date": "2026-01-15", "descriptor": "UPI/NFLX*NETFLIX/983724/P2M", "amount": 649.0},
    {"date": "2026-02-15", "descriptor": "UPI/NFLX*NETFLIX/983724/P2M", "amount": 799.0}, # Silent Hike
    
    {"date": "2025-11-01", "descriptor": "INB*AMZN PRIME*MEMBERSHIP", "amount": 1499.0},
    {"date": "2026-10-30", "descriptor": "INB*AMZN PRIME*MEMBERSHIP", "amount": 1499.0}, # Annual
    
    {"date": "2025-08-10", "descriptor": "POS/RAZORPAY*CULTFIT/BANGALORE", "amount": 1500.0},
    {"date": "2025-11-12", "descriptor": "POS/RAZORPAY*CULTFIT/BANGALORE", "amount": 1500.0},
    {"date": "2026-02-14", "descriptor": "POS/RAZORPAY*CULTFIT/BANGALORE", "amount": 1500.0}, # Irregular
    
    {"date": "2026-01-05", "descriptor": "AWS*CLOUD SERVICES SEATTLE", "amount": 420.0},
    {"date": "2026-02-05", "descriptor": "AWS*CLOUD SERVICES SEATTLE", "amount": 1280.0},
    
    {"date": "2026-02-01", "descriptor": "OPENAI*CHATGPT SUBSCRIPTION", "amount": 1.0},
    {"date": "2026-03-01", "descriptor": "OPENAI*CHATGPT SUBSCRIPTION", "amount": 1650.0} # Trial converted
]

# =========================================================
# 5. STREAMLIT APPLICATION INTERFACE
# =========================================================

# Session state initialization for revocation simulation
if "revoked_mandates" not in st.session_state:
    st.session_state.revoked_mandates = set()

# Header Layout
head_col1, head_col2 = st.columns([1, 5])
with head_col1:
    if logo_image:
        st.image(logo_image, width=110)
    else:
        st.title("💳")
with head_col2:
    st.title("Anulaksya — Recurring Debit & Mandate Intelligence")
    st.caption("Intelligence layer above payment rails: Uncovering hidden mandates, silent price hikes, and automatic forecast clocks.")

# Sidebar Configuration
st.sidebar.header("⚙️ Data Source & Controls")
data_source = st.sidebar.radio("Select Input Mode", ["Synthetic Demo History", "Upload Statement (JSON)"])

if data_source == "Upload Statement (JSON)":
    uploaded_file = st.sidebar.file_uploader("Upload Bank Statement JSON", type=["json"])
    if uploaded_file:
        try:
            transactions = json.load(uploaded_file)
            st.sidebar.success("Statement Loaded Successfully!")
        except Exception as e:
            st.sidebar.error(f"Error parsing JSON: {e}")
            transactions = DEFAULT_STATEMENT
    else:
        transactions = DEFAULT_STATEMENT
else:
    transactions = DEFAULT_STATEMENT

# Run Engine
analyzer = RecurringPaymentAnalyzer(MERCHANT_KNOWLEDGE_BASE)
report = analyzer.analyze_transactions(transactions)

# Filter out revoked mandates
active_commitments = [
    c for c in report["commitments"] if c["merchant"] not in st.session_state.revoked_mandates
]
recalculated_annual_leak = sum(c["annualized_impact"] for c in active_commitments)

# --- TOP METRICS BANNER ---
st.markdown("---")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Annual Financial Leak", f"₹{recalculated_annual_leak:,.2f}")
m2.metric("Active Mandates", len(active_commitments))

hikes_count = sum(1 for c in active_commitments if c["has_price_hike"])
m3.metric("Silent Price Hikes Detected", hikes_count, delta=f"{hikes_count} Alert(s)" if hikes_count else None, delta_color="inverse")

trial_count = sum(1 for c in active_commitments if c["is_trial_conversion"])
m4.metric("Trial Conversions", trial_count, delta=f"{trial_count} Converted" if trial_count else None, delta_color="inverse")

# --- TAB NAVIGATION ---
tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 Active Mandates & Revocation", 
    "📅 Renewal Forecast Calendar", 
    "📊 Financial Category Analytics", 
    "📄 Dispute & Audit Export"
])

# --- TAB 1: ACTIVE MANDATES & REVOCATION ---
with tab1:
    st.subheader("Detected Recurring Commitments")
    st.caption("Review each detected mandate, inspect silent price hikes, and execute 1-Click revocation.")

    if not active_commitments:
        st.success("🎉 All mandates have been successfully revoked or managed!")

    for item in active_commitments:
        merchant_name = item["merchant"]
        with st.expander(f"{merchant_name} — ₹{item['latest_amount']} ({item['frequency']})"):
            col_a, col_b = st.columns([2, 1])
            with col_a:
                st.write(f"**Category:** {item['category']}")
                st.write(f"**Execution Payment Rail:** `{item['rail_type']}`")
                st.write(f"**Last Debited Date:** {item['last_debit_date']}")
                st.write(f"**Next Estimated Debit:** `{item['next_estimated_date']}`")
                st.write(f"**Annualized Financial Impact:** ₹{item['annualized_impact']:,.2f}")

                if item["has_price_hike"]:
                    st.warning("⚠️ **Silent Price Hike Detected!**")
                    for hike in item["price_hike_details"]:
                        st.write(f"- Amount increased from **₹{hike['old_amount']}** to **₹{hike['new_amount']}** (+{hike['increase_pct']}%) on {hike['date']}")

                if item["is_trial_conversion"]:
                    st.error("🚨 **Trial Conversion Detected!** This subscription converted from a free/low-cost trial to a full paid plan.")

            with col_b:
                st.markdown("### 🛑 Cancellation Pathway")
                for step in item["cancellation_steps"]:
                    st.write(f"- {step}")

                st.markdown("---")
                if st.button(f"Revoke Mandate: {merchant_name}", key=f"btn_{merchant_name}"):
                    st.session_state.revoked_mandates.add(merchant_name)
                    st.success(f"Revocation request dispatched for {merchant_name}!")
                    st.rerun()

# --- TAB 2: RENEWAL FORECAST CALENDAR ---
with tab2:
    st.subheader("📅 30/60/90 Day Renewal Forecast")
    st.caption("Predictive clock estimating when payments will be auto-debited across payment rails.")
    
    if report["predictions"]:
        df_pred = pd.DataFrame(report["predictions"])
        # Filter revoked items
        df_pred = df_pred[~df_pred["Merchant"].isin(st.session_state.revoked_mandates)]
        st.dataframe(df_pred, use_container_width=True)
    else:
        st.info("No future renewal predictions available.")

# --- TAB 3: CATEGORY ANALYTICS ---
with tab3:
    st.subheader("📊 Spend Breakdown by Category & Payment Rail")
    if active_commitments:
        df_commitments = pd.DataFrame(active_commitments)
        
        c_left, c_right = st.columns(2)
        with c_left:
            fig_cat = px.pie(
                df_commitments, 
                names="category", 
                values="annualized_impact", 
                title="Annualized Leakage by Category",
                hole=0.4
            )
            st.plotly_chart(fig_cat, use_container_width=True)

        with c_right:
            fig_rail = px.bar(
                df_commitments, 
                x="rail_type", 
                y="annualized_impact", 
                color="category",
                title="Financial Leakage by Execution Rail",
                labels={"annualized_impact": "Annual Impact (₹)", "rail_type": "Payment Rail"}
            )
            st.plotly_chart(fig_rail, use_container_width=True)

# --- TAB 4: DISPUTE & AUDIT EXPORT ---
with tab4:
    st.subheader("📄 Export Financial Leakage Audit Report")
    st.caption("Download structured CSV records to dispute unauthorized debits or file mandate cancellations with your bank.")

    if active_commitments:
        export_df = pd.DataFrame(active_commitments)[[
            "merchant", "category", "rail_type", "latest_amount", "annualized_impact", "frequency", "next_estimated_date"
        ]]
        csv_data = export_df.to_csv(index=False).encode('utf-8')

        st.download_button(
            label="📥 Download Audit Report (CSV)",
            data=csv_data,
            file_name=f"anulaksya_mandate_report_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
        st.dataframe(export_df, use_container_width=True)