"""
Browser / Web Portal Inspection Tool.
Inspects DOM and verifies visual representation in the company ERP web portal.
"""

from typing import Dict, Any, Optional
from app.tools.base import BaseTool
from app.agent.state import RiskLevel
from app.sandbox.erp_server import erp_app
from fastapi.testclient import TestClient

class BrowserPortalTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="inspect_web_portal",
            description="Renders and inspects the internal company ERP web portal to visually check invoice records.",
            risk_level=RiskLevel.LOW
        )
        self.client = TestClient(erp_app)

    def execute(self, **kwargs) -> Dict[str, Any]:
        invoice_number = kwargs.get("invoice_number", "")
        response = self.client.get("/sandbox/portal")
        
        html = response.text
        is_visible = invoice_number in html if invoice_number else False
        
        return {
            "portal_url": "/sandbox/portal",
            "status_code": response.status_code,
            "invoice_found_in_dom": is_visible,
            "target_invoice": invoice_number,
            "page_title": "CentrAlign Sandbox Enterprise ERP"
        }
