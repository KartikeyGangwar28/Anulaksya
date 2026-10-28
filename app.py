import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import defaultdict

# ==========================================
# 1. REFERENCE DATA & KNOWLEDGE BASE
# ==========================================

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
        "pattern": r"(?i)( культ|CULT\.|CULTFIT|CUREFIT)",
        "clean_name": "Cult.fit Pass",
        "category": "Fitness & Health",
        "logo_icon": "fa-solid fa-dumbbell",
        "rail_type": "eNACH / UPI Mandate",
        "cancellation_steps": [
            "Open Cult.fit App > Profile > Active Subscriptions",
            "Select Membership > Cancel Auto-Renewal",
            "If non-responsive, submit eNACH mandate cancellation at issuing bank"
        ]
    },
    {
        "pattern": r"(?i)(RAZORPAY\*|RZP\*)(?P<submerchant>[A-Z0-9_]+)",
        "clean_name": "Razorpay Sub-Merchant",
        "category": "SaaS / Digital Service",
        "logo_icon": "fa-solid fa-credit-card",
        "rail_type": "Razorpay Sub-Mandate",
        "cancellation_steps": [
            "Visit razorpay.com/support or check email receipt for mandate link",
            "Access Razorpay Subscriptions Dashboard",
            "Cancel recurring authorization via OTP"
        ]
    }
]

# ==========================================
# 2. PATTERN REASONING & DISCOVERY ENGINE
# ==========================================

class RecurringPaymentAnalyzer:
    def __init__(self, knowledge_base: List[Dict]):
        self.kb = knowledge_base

    def normalize_merchant(self, raw_descriptor: str) -> Dict[str, str]:
        """Maps compressed bank string to recognizable merchant identity."""
        for entry in self.kb:
            match = re.search(entry["pattern"], raw_descriptor)
            if match:
                clean_name = entry["clean_name"]
                if "submerchant" in match.groupdict() and match.group("submerchant"):
                    clean_name += f" ({match.group('submerchant')})"
                return {
                    "clean_name": clean_name,
                    "category": entry["category"],
                    "logo_icon": entry["logo_icon"],
                    "rail_type": entry["rail_type"],
                    "cancellation_steps": entry["cancellation_steps"]
                }
        return {
            "clean_name": raw_descriptor.strip(),
            "category": "Uncategorized Subscription",
            "logo_icon": "fa-solid fa-receipt",
            "rail_type": "Unknown Mandate Rail",
            "cancellation_steps": [
                "Identify execution bank from statement",
                "Log into NetBanking > eMandate / Autopay Section",
                "Issue explicit mandate revocation request to bank grievance cell"
            ]
        }

    def analyze_transactions(self, raw_transactions: List[Dict]) -> Dict[str, Any]:
        """
        Processes transaction history to find fixed, irregular, variable,
        and price-increased recurring debits.
        """
        # Group by normalized merchant
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
                # Check for single high-value annual or trial charge flagged
                continue

            # Sort chronologically
            txs.sort(key=lambda x: x["date_obj"])

            # Compute intervals and price dynamics
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
            earliest_tx = txs[0]

            # Determine Commitment Type
            commitment_type = "Fixed Monthly"
            confidence = "High"
            is_irregular = False

            if 25 <= avg_interval <= 35:
                commitment_type = "Monthly Recurring"
                annualized_cost = latest_tx["amount"] * 12
            elif 350 <= avg_interval <= 380:
                commitment_type = "Annual Auto-Renewal"
                annualized_cost = latest_tx["amount"]
                is_irregular = True
            elif 80 <= avg_interval <= 100:
                commitment_type = "Quarterly Recurring"
                annualized_cost = latest_tx["amount"] * 4
                is_irregular = True
            else:
                commitment_type = "Irregular / Variable Interval"
                annualized_cost = latest_tx["amount"] * (365 / max(avg_interval, 1))
                is_irregular = True

            # Price Hike / Trial conversion check
            has_price_hike = len(price_changes) > 0
            is_trial_converted = (earliest_tx["amount"] == 0 or earliest_tx["amount"] < 10) and latest_tx["amount"] > 100

            total_annual_leak += annualized_cost

            commitments.append({
                "merchant": merchant,
                "category": latest_tx["category"],
                "rail_type": latest_tx["rail_type"],
                "logo_icon": latest_tx["logo_icon"],
                "last_debit_date": latest_tx["date"],
                "latest_amount": latest_tx["amount"],
                "annualized_impact": round(annualized_cost, 2),
                "frequency": commitment_type,
                "is_irregular": is_irregular,
                "has_price_hike": has_price_hike,
                "price_hike_details": price_changes if has_price_hike else None,
                "is_trial_converted": is_trial_converted,
                "cancellation_steps": latest_tx["cancellation_steps"],
                "history_count": len(txs)
            })

        return {
            "total_annual_leak": round(total_annual_leak, 2),
            "total_commitments_found": len(commitments),
            "commitments": commitments
        }

# ==========================================
# 3. DEMONSTRATION & SYNTHETIC DATASETS
# ==========================================

SYNTHETIC_BANK_STATEMENT = [
    {"date": "2025-10-15", "descriptor": "UPI/NFLX*NETFLIX/983724/P2M", "amount": 649.0},
    {"date": "2025-11-15", "descriptor": "UPI/NFLX*NETFLIX/983724/P2M", "amount": 649.0},
    {"date": "2025-12-15", "descriptor": "UPI/NFLX*NETFLIX/983724/P2M", "amount": 649.0},
    {"date": "2026-01-15", "descriptor": "UPI/NFLX*NETFLIX/983724/P2M", "amount": 649.0},
    {"date": "2026-02-15", "descriptor": "UPI/NFLX*NETFLIX/983724/P2M", "amount": 799.0}, # Price Hike!
    
    {"date": "2025-11-01", "descriptor": "INB*AMZN PRIME*MEMBERSHIP", "amount": 1499.0},
    {"date": "2026-10-30", "descriptor": "INB*AMZN PRIME*MEMBERSHIP", "amount": 1499.0}, # Annual Auto-Debit
    
    {"date": "2025-08-10", "descriptor": "POS/RAZORPAY*CULTFIT/BANGALORE", "amount": 1500.0},
    {"date": "2025-11-12", "descriptor": "POS/RAZORPAY*CULTFIT/BANGALORE", "amount": 1500.0},
    {"date": "2026-02-14", "descriptor": "POS/RAZORPAY*CULTFIT/BANGALORE", "amount": 1500.0}, # Quarterly / Irregular
    
    {"date": "2026-01-05", "descriptor": "AWS*CLOUD SERVICES SEATTLE", "amount": 420.0},
    {"date": "2026-02-05", "descriptor": "AWS*CLOUD SERVICES SEATTLE", "amount": 1280.0} # Variable Usage
]

if __name__ == "__main__":
    analyzer = RecurringPaymentAnalyzer(MERCHANT_KNOWLEDGE_BASE)
    report = analyzer.analyze_transactions(SYNTHETIC_BANK_STATEMENT)
    print("=== THE AUTO-DEBIT INTELLIGENCE ENGINE ===")
    print(f"Total Annual Financial Leak: ₹{report['total_annual_leak']:,.2f}")
    print(f"Total Commitments Identified: {report['total_commitments_found']}")
    print("\nDetailed Commitment Breakdown:")
    print(json.dumps(report["commitments"], indent=2))