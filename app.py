import re
import json
from datetime import datetime
from collections import defaultdict
from PIL import Image
import streamlit as st
logo_image = Image.open("assets/images/anulakshyalog.jpg")
# Set page layout
st.set_page_config(
    page_title="Anulaksya — Third-Party Account Aggregator",
    page_icon=logo_image,
    layout="wide"
)
st.sidebar.image(logo_image, width=200)

st.title("💳 Anulaksya — Third-Party Account Aggregator")

# =========================================================
# 1. THIRD-PARTY ACCOUNT CONNECTORS
# =========================================================

class AccountConnector:
    def __init__(self, platform_name: str, auth_type: str):
        self.platform_name = platform_name
        self.auth_type = auth_type

    def fetch_subscription_metadata(self, account_id: str):
        raise NotImplementedError

class SpotifyConnector(AccountConnector):
    def __init__(self):
        super().__init__("Spotify", "OAuth2")

    def fetch_subscription_metadata(self, account_id: str):
        return {
            "account_id": account_id,
            "platform": "Spotify Premium",
            "plan_name": "Premium Family",
            "amount": 179.0,
            "currency": "INR",
            "billing_cycle": "Monthly",
            "next_billing_date": "2026-11-15",
            "last_used_date": "2026-10-30",
            "is_usage_active": True,
            "revoke_endpoint": "https://www.spotify.com/account/apps/",
            "payment_rail": "UPI AutoPay (GPay)"
        }

class OpenAIConnector(AccountConnector):
    def __init__(self):
        super().__init__("OpenAI", "API_Key")

    def fetch_subscription_metadata(self, account_id: str):
        return {
            "account_id": account_id,
            "platform": "OpenAI / ChatGPT",
            "plan_name": "ChatGPT Plus",
            "amount": 1650.0,
            "currency": "INR",
            "billing_cycle": "Monthly",
            "next_billing_date": "2026-11-08",
            "last_used_date": "2026-09-12", # Inactive for 45+ days
            "is_usage_active": False,
            "revoke_endpoint": "https://platform.openai.com/account/billing/overview",
            "payment_rail": "Credit Card Standing Instruction"
        }

class AmazonConnector(AccountConnector):
    def __init__(self):
        super().__init__("Amazon India", "OAuth2")

    def fetch_subscription_metadata(self, account_id: str):
        return {
            "account_id": account_id,
            "platform": "Amazon Prime",
            "plan_name": "Prime Annual Membership",
            "amount": 1499.0,
            "currency": "INR",
            "billing_cycle": "Annual",
            "next_billing_date": "2026-12-01",
            "last_used_date": "2026-10-28",
            "is_usage_active": True,
            "revoke_endpoint": "https://www.amazon.in/mc/manage",
            "payment_rail": "eNACH Mandate"
        }

class ThirdPartyAutopayAggregator:
    def __init__(self):
        self.connectors = {
            "spotify": SpotifyConnector(),
            "openai": OpenAIConnector(),
            "amazon": AmazonConnector()
        }

    def aggregate_linked_accounts(self, linked_credentials):
        active_subscriptions = []
        total_annual_leak = 0.0
        idle_count = 0

        for cred in linked_credentials:
            platform_key = cred["platform_key"]
            if platform_key in self.connectors:
                connector = self.connectors[platform_key]
                meta = connector.fetch_subscription_metadata(cred["account_id"])
                
                cycle = meta["billing_cycle"]
                cost = meta["amount"]
                annual_impact = cost * 12 if cycle == "Monthly" else cost
                
                total_annual_leak += annual_impact

                days_idle = (datetime.now() - datetime.strptime(meta["last_used_date"], "%Y-%m-%d")).days
                is_idle = days_idle > 30

                if is_idle:
                    idle_count += 1

                active_subscriptions.append({
                    "platform": meta["platform"],
                    "plan": meta["plan_name"],
                    "recurring_amount": cost,
                    "cycle": cycle,
                    "next_billing_date": meta["next_billing_date"],
                    "annual_impact": round(annual_impact, 2),
                    "days_idle": days_idle,
                    "is_idle": is_idle,
                    "payment_rail": meta["payment_rail"],
                    "revoke_url": meta["revoke_endpoint"]
                })

        return {
            "linked_count": len(active_subscriptions),
            "total_annual_commitment": round(total_annual_leak, 2),
            "idle_waste_count": idle_count,
            "subscriptions": active_subscriptions
        }

# =========================================================
# 2. STREAMLIT WEB INTERFACE
# =========================================================

st.title("💳 Anulaksya — Third-Party Account Aggregator")
st.caption("Direct platform governance across consumer services, AI tools, and subscriptions.")

# Sidebar Connector Controls
st.sidebar.header("🔗 Linked Accounts")
connect_spotify = st.sidebar.checkbox("Spotify Premium", value=True)
connect_openai = st.sidebar.checkbox("OpenAI / ChatGPT", value=True)
connect_amazon = st.sidebar.checkbox("Amazon Prime", value=True)

linked_creds = []
if connect_spotify:
    linked_creds.append({"platform_key": "spotify", "account_id": "usr_spot_9921"})
if connect_openai:
    linked_creds.append({"platform_key": "openai", "account_id": "usr_oai_8832"})
if connect_amazon:
    linked_creds.append({"platform_key": "amazon", "account_id": "usr_amzn_1102"})

aggregator = ThirdPartyAutopayAggregator()
report = aggregator.aggregate_linked_accounts(linked_creds)

# Top Metrics Banner
col1, col2, col3 = st.columns(3)
col1.metric("Total Annual Commitment", f"₹{report['total_annual_commitment']:,.2f}")
col2.metric("Connected Accounts", report['linked_count'])
col3.metric("Unused / Idle Subscriptions", report['idle_waste_count'], delta="Action Needed" if report['idle_waste_count'] else None, delta_color="inverse")

st.markdown("---")
st.subheader("Connected Platform Mandates & Inactivity Alerts")

if not report["subscriptions"]:
    st.info("No accounts currently connected. Use the sidebar to link services.")

for item in report["subscriptions"]:
    with st.expander(f"{item['platform']} ({item['plan']}) — ₹{item['recurring_amount']} / {item['cycle']}"):
        c1, c2 = st.columns([2, 1])
        with c1:
            st.write(f"**Billing Cycle:** {item['cycle']}")
            st.write(f"**Next Billing Date:** {item['next_billing_date']}")
            st.write(f"**Payment Rail:** {item['payment_rail']}")
            st.write(f"**Annualized Financial Impact:** ₹{item['annual_impact']:,.2f}")
            
            if item['is_idle']:
                st.error(f"⚠️ **Idle Financial Drain Alert:** No usage recorded in {item['days_idle']} days! Consider cancelling or pausing this plan.")
            else:
                st.success(f"✅ Active subscription (Used {item['days_idle']} days ago).")

        with c2:
            st.markdown("### ⚙️ Account Governance")
            st.markdown(f"[🔗 Manage / Revoke Access directly on {item['platform']}]({item['revoke_url']})")