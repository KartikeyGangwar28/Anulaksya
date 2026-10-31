# 💳 Anulaksya (अनुलक्ष्य) — Recurring Debit & Mandate Intelligence

> **Hackathon Theme:** T4 (Fintech)  
> **Problem Statement:** T4.1 — *"The Auto Debits Nobody Can Find"*  
> **Live Web App:** [anulaksya.streamlit.app](https://anulaksya234gfasfd3123412qwasdg342tgds.streamlit.app/)  

---

## 📌 Overview

**Anulaksya (अनुलक्ष्य)** (Sanskrit for *Subtle Tracking*) is an intelligence layer built on top of digital payment rails (UPI AutoPay, eNACH, Card Standing Instructions) to uncover forgotten mandates, silent price hikes, free trial traps, and irregular annual renewals hiding inside bank statements and third-party platform accounts.

### Key Capabilities
- 🔍 **Merchant String Normalization:** Uses pattern-matching rules to clean cryptic descriptors (e.g., matching `INB*AMZN PRIME*MEMBERSHIP` to `Amazon Prime`).
- 📈 **Silent Price Hike Radar:** Tracks price deltas over time to flag unannounced fee increases.
- 🕒 **Predictive Renewal Calendar:** Projects expected auto-debit dates over 30, 60, and 90-day horizons.
- 🔗 **Third-Party Account Aggregation:** Links external platforms (Spotify, OpenAI, Amazon) to flag idle subscriptions with no recent activity.
- 🛡️ **Mandate Health Index (MHI):** Scores account portfolio risk on a 0–100 scale.
- 📄 **1-Click Cancellation Pathways & Audit Export:** Generates step-by-step revocation guides and downloadable CSV audit reports for bank disputes.

---

## 🏗️ Repository & File Structure

```text
autopayTracker/
├── assets/
│   └── images/
│       └── anulakshyalog.jpg    # Official Anulaksya Project Logo
├── app.py                       # Main Streamlit Web Dashboard & Core Intelligence Engine
├
├── requirements.txt             # Python Dependencies for Streamlit Cloud Deployment
└── README.md                    # Project Documentation