import time
import os
import json
import logging
from typing import Dict, Any
from arna_backend.services.notifier import send_email_notification

logger = logging.getLogger("arna_backend.billing")

BILLING_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "billing_config.json")

DEFAULT_BILLING_STATE = {
    "currency": "INR",
    "budget_threshold": 25000.0,  # Max monthly spend budget in INR
    "warning_threshold": 15000.0, # Early alert trigger at 60%
    "alert_email": "admin@arna.co.in",
    "alert_sent_warning": False,
    "alert_sent_critical": False,
    "last_reset": time.time(),
    "usage": {
        "api_requests": 1420,
        "database_reads": 4890,
        "database_writes": 612,
        "sms_dispatched": 28,
        "emails_sent": 115,
        "orders_processed": 42
    },
    "cost_breakdown": {
        "supabase_cloud": 1950.0,
        "sms_gateway": 4.20,       # ~0.15 INR per SMS
        "email_delivery": 11.50,    # ~0.10 INR per email
        "compute_bandwidth": 450.0
    }
}

class BillingService:
    def __init__(self):
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        try:
            if os.path.exists(BILLING_CONFIG_PATH):
                with open(BILLING_CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {**DEFAULT_BILLING_STATE, **data}
        except Exception as e:
            logger.warning(f"Could not load billing state: {e}")
        return DEFAULT_BILLING_STATE.copy()

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(BILLING_CONFIG_PATH), exist_ok=True)
            with open(BILLING_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save billing state: {e}")

    def record_usage(self, metric: str, count: int = 1):
        """Records infrastructure usage and checks billing alert thresholds."""
        if metric in self.state["usage"]:
            self.state["usage"][metric] += count

        # Dynamically compute approximate usage costs in INR
        sms_cost = self.state["usage"]["sms_dispatched"] * 0.15
        email_cost = self.state["usage"]["emails_sent"] * 0.10
        db_cost = 1950.0 + (self.state["usage"]["database_writes"] * 0.02)
        compute_cost = 450.0 + (self.state["usage"]["api_requests"] * 0.005)

        self.state["cost_breakdown"] = {
            "supabase_cloud": round(db_cost, 2),
            "sms_gateway": round(sms_cost, 2),
            "email_delivery": round(email_cost, 2),
            "compute_bandwidth": round(compute_cost, 2)
        }

        total_cost = self.get_total_cost()
        self._check_alerts(total_cost)
        self._save_state()

    def get_total_cost(self) -> float:
        return round(sum(self.state["cost_breakdown"].values()), 2)

    def _check_alerts(self, current_cost: float):
        budget = self.state["budget_threshold"]
        warning = self.state["warning_threshold"]

        if current_cost >= budget and not self.state.get("alert_sent_critical", False):
            self.state["alert_sent_critical"] = True
            logger.critical(f"BILLING ALERT: Current usage ({current_cost} INR) exceeded budget threshold ({budget} INR)!")
            send_email_notification(
                to_email=self.state["alert_email"],
                subject="URGENT: ARNA Atelier Monthly Cloud Budget Exceeded!",
                html_content=f"""
                <div style="font-family: sans-serif; padding: 20px; background: #fff1f2; border: 2px solid #e11d48; border-radius: 10px;">
                    <h2 style="color: #9f1239;">🚨 ARNA Atelier Cloud Budget Exceeded</h2>
                    <p>Your current infrastructure spend of <strong>₹{current_cost:,.2f}</strong> has crossed your set safety budget threshold of <strong>₹{budget:,.2f}</strong>.</p>
                    <ul>
                        <li>Database & Storage: ₹{self.state['cost_breakdown']['supabase_cloud']}</li>
                        <li>SMS Gateway Dispatches: ₹{self.state['cost_breakdown']['sms_gateway']}</li>
                        <li>Email Notifications: ₹{self.state['cost_breakdown']['email_delivery']}</li>
                        <li>API & Bandwidth: ₹{self.state['cost_breakdown']['compute_bandwidth']}</li>
                    </ul>
                    <p style="color: #4b5563; font-size: 12px;">Automated safeguard by ARNA Security & Billing Engine.</p>
                </div>
                """
            )
        elif current_cost >= warning and not self.state.get("alert_sent_warning", False):
            self.state["alert_sent_warning"] = True
            logger.warning(f"BILLING WARNING: Current usage ({current_cost} INR) reached warning threshold ({warning} INR).")
            send_email_notification(
                to_email=self.state["alert_email"],
                subject="Notice: ARNA Atelier 60% Cloud Budget Reached",
                html_content=f"""
                <div style="font-family: sans-serif; padding: 20px; background: #fffbeb; border: 1px solid #f59e0b; border-radius: 10px;">
                    <h2 style="color: #92400e;">⚠️ ARNA Atelier Cloud Budget Notice</h2>
                    <p>Current estimated infrastructure spend is <strong>₹{current_cost:,.2f}</strong> (Budget: ₹{budget:,.2f}).</p>
                    <p style="color: #4b5563; font-size: 12px;">Automated alert by ARNA Security & Billing Engine.</p>
                </div>
                """
            )

    def get_status(self) -> Dict[str, Any]:
        total_cost = self.get_total_cost()
        budget = self.state["budget_threshold"]
        pct = round((total_cost / budget) * 100, 1) if budget > 0 else 0
        
        status_label = "SAFE"
        if total_cost >= budget:
            status_label = "CRITICAL_EXCEEDED"
        elif total_cost >= self.state["warning_threshold"]:
            status_label = "WARNING_APPROACHING"

        return {
            "status": status_label,
            "currency": self.state["currency"],
            "total_estimated_cost": total_cost,
            "budget_threshold": budget,
            "warning_threshold": self.state["warning_threshold"],
            "percentage_used": pct,
            "alert_email": self.state["alert_email"],
            "usage_metrics": self.state["usage"],
            "cost_breakdown": self.state["cost_breakdown"],
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    def update_config(self, budget_threshold: float, warning_threshold: float, alert_email: str) -> Dict[str, Any]:
        if budget_threshold > 0:
            self.state["budget_threshold"] = budget_threshold
        if warning_threshold > 0:
            self.state["warning_threshold"] = warning_threshold
        if alert_email:
            self.state["alert_email"] = alert_email.strip().lower()
        self._save_state()
        return self.get_status()

billing_service = BillingService()
