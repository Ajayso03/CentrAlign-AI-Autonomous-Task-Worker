"""
Enterprise Finance ERP Tool.
Directly communicates with the Sandbox ERP API or in-memory service.
"""

import httpx
from typing import Dict, Any, Optional
from app.tools.base import BaseTool
from app.agent.state import RiskLevel
from app.sandbox.erp_server import erp_app
from fastapi.testclient import TestClient

class FinanceERPTool(BaseTool):
    def __init__(self, base_url: Optional[str] = None):
        super().__init__(
            name="create_invoice_record",
            description="Enters a new verified invoice record into the enterprise finance ERP system.",
            risk_level=RiskLevel.MEDIUM
        )
        self.base_url = base_url
        self.client = TestClient(erp_app)

    def execute(self, **kwargs) -> Dict[str, Any]:
        payload = {
            "invoice_number": kwargs.get("invoice_number"),
            "vendor_name": kwargs.get("vendor_name"),
            "amount": float(kwargs.get("amount") if kwargs.get("amount") is not None else 0.0),
            "currency": kwargs.get("currency", "USD"),
            "due_date": kwargs.get("due_date"),
            "source_document": kwargs.get("source_document")
        }

        # Make HTTP call to ERP endpoint
        response = self.client.post("/api/v1/invoices", json=payload)
        
        if response.status_code == 201:
            return response.json()
        elif response.status_code == 422:
            detail = response.json().get("detail", "Validation Failed")
            raise ValueError(f"HTTP 422 {detail}")
        elif response.status_code == 503:
            detail = response.json().get("detail", "Service Unavailable")
            raise ConnectionError(f"HTTP 503 {detail}")
        elif response.status_code == 409:
            detail = response.json().get("detail", "Duplicate Record")
            raise ValueError(f"HTTP 409 {detail}")
        else:
            raise RuntimeError(f"ERP Error HTTP {response.status_code}: {response.text}")
