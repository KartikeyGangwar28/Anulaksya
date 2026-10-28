import re
import json
from datetime import datetime
from collections import defaultdict
import streamlit as st

# Set page configuration
st.set_page_config(
    page_title="Anulaksya - AutoPay Tracker",
    page_icon="💳",
    layout="wide"
)

# Reference dataset for merchant string interpretation
MERCHANT_KNOWLEDGE_BASE = [
    {
        "pattern": r"(?i)(AMZN|AMAZON|PRIME\s*MEMBER)",
        "clean_name": "Amazon Prime",
        "category": "Entertainment & Shopping",
        "logo_icon": "fa-brands fa-amazon",
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
        "logo_icon": "fa-solid fa-tv",
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
        "logo_icon": "fa-brands fa-spotify",
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
        "logo_icon": "fa-solid fa-cloud",
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
        "logo_icon": "fa-solid fa-utensils",
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
        "logo_icon": "fa-solid fa-dumbbell",
        "rail_type": "eNACH / UPI Mandate",
        "cancellation_steps": [
            "Open Cult.fit App > Profile > Active Subscriptions",
            "Select Membership > Cancel Auto-Renewal",
            "If non-responsive, submit eNACH mandate cancellation at issuing bank"
        ]
    }
]

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
                "Issue explicit mandate revocation request"
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
        total_annual_leak = 0.0

        for merchant, txs in grouped.items():
            if len(txs) < 2:
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
                        "increase_pct": round((price_diff / txs[i-1]["amount"]) * 100, 1)
                    })

            avg_interval = sum(intervals) / len(intervals) if intervals else 0
            latest_tx = txs[-1]

            if 25 <= avg_interval <= 35:
                commitment_type = "Monthly Recurring"
                annualized_cost = latest_tx["amount"] * 12
            elif 350 <= avg_interval <= 380:
                commitment_type = "Annual Auto-Renewal"
                annualized_cost = latest_tx["amount"]
            else:
                commitment_type = "Irregular Interval"
                annualized_cost = latest_tx["amount"] * (365 / max(avg_interval, 1))

            total_annual_leak += annualized_cost

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
                "cancellation_steps": latest_tx["cancellation_steps"]
            })

        return {
            "total_annual_leak": round(total_annual_leak, 2),
            "total_commitments_found": len(commitments),
            "commitments": commitments
        }

SYNTHETIC_BANK_STATEMENT = [
    {"date": "2025-10-15", "descriptor": "UPI/NFLX*NETFLIX/983724/P2M", "amount": 649.0},
    {"date": "2025-11-15", "descriptor": "UPI/NFLX*NETFLIX/983724/P2M", "amount": 649.0},
    {"date": "2025-12-15", "descriptor": "UPI/NFLX*NETFLIX/983724/P2M", "amount": 649.0},
    {"date": "2026-01-15", "descriptor": "UPI/NFLX*NETFLIX/983724/P2M", "amount": 649.0},
    {"date": "2026-02-15", "descriptor": "UPI/NFLX*NETFLIX/983724/P2M", "amount": 799.0},
    
    {"date": "2025-11-01", "descriptor": "INB*AMZN PRIME*MEMBERSHIP", "amount": 1499.0},
    {"date": "2026-10-30", "descriptor": "INB*AMZN PRIME*MEMBERSHIP", "amount": 1499.0},
    
    {"date": "2025-08-10", "descriptor": "POS/RAZORPAY*CULTFIT/BANGALORE", "amount": 1500.0},
    {"date": "2025-11-12", "descriptor": "POS/RAZORPAY*CULTFIT/BANGALORE", "amount": 1500.0},
    {"date": "2026-02-14", "descriptor": "POS/RAZORPAY*CULTFIT/BANGALORE", "amount": 1500.0},
    
    {"date": "2026-01-05", "descriptor": "AWS*CLOUD SERVICES SEATTLE", "amount": 420.0},
    {"date": "2026-02-05", "descriptor": "AWS*CLOUD SERVICES SEATTLE", "amount": 1280.0}
]

# --- STREAMLIT UI RENDER ---
st.title("💳 Anulaksya — Recurring Debit Intelligence")
st.caption("Unveiling forgotten auto-debits, silent price hikes, and cancellation pathways.")

analyzer = RecurringPaymentAnalyzer(MERCHANT_KNOWLEDGE_BASE)
report = analyzer.analyze_transactions(SYNTHETIC_BANK_STATEMENT)

# Metrics Banner
col1, col2, col3 = st.columns(3)
col1.metric("Total Annual Financial Leak", f"₹{report['total_annual_leak']:,.2f}")
col2.metric("Detected Subscriptions", report['total_commitments_found'])
hikes_count = sum(1 for c in report['commitments'] if c['has_price_hike'])
col3.metric("Price Hikes Detected", hikes_count, delta=f"{hikes_count} Alert" if hikes_count else None, delta_color="inverse")

st.markdown("---")
st.subheader("Active Mandates & Cancellation Guidance")

for item in report["commitments"]:
    with st.expander(f"{item['merchant']} — ₹{item['latest_amount']} ({item['frequency']})"):
        c1, c2 = st.columns([2, 1])
        with c1:
            st.write(f"**Category:** {item['category']}")
            st.write(f"**Payment Rail:** {item['rail_type']}")
            st.write(f"**Last Debited:** {item['last_debit_date']}")
            st.write(f"**Annualized Cost:** ₹{item['annualized_impact']:,.2f}")
            if item['has_price_hike']:
                st.warning("⚠️ **Silent Price Hike Detected!**")
                for hike in item['price_hike_details']:
                    st.write(f"- Increased from ₹{hike['old_amount']} to ₹{hike['new_amount']} (+{hike['increase_pct']}%) on {hike['date']}")
        with c2:
            st.markdown("### 🛑 Cancellation Steps")
            for step in item['cancellation_steps']:
                st.write(f"- {step}")