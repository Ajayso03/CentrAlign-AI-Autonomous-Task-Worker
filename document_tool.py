"""
Document Repository Search & Invoice Parser Tool.
"""

import os
import re
from typing import Dict, Any, List, Optional
from app.tools.base import BaseTool
from app.agent.state import RiskLevel

class DocumentRepositoryTool(BaseTool):
    def __init__(self, data_dir: Optional[str] = None):
        super().__init__(
            name="search_documents",
            description="Searches company document repository for invoices and documents matching a vendor query.",
            risk_level=RiskLevel.LOW
        )
        self.data_dir = data_dir or os.path.join(os.getcwd(), "app", "sandbox", "company_data")

    def execute(self, **kwargs) -> Dict[str, Any]:
        query = kwargs.get("query", "").lower()
        doc_type = kwargs.get("doc_type", "invoices")
        target_dir = os.path.join(self.data_dir, doc_type)

        if not os.path.exists(target_dir):
            return {"matches": [], "count": 0, "message": f"Directory {doc_type} not found"}

        matched_files = []
        for root, _, files in os.walk(target_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.data_dir)
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                
                if query in file.lower() or query in content.lower():
                    matched_files.append({
                        "filename": file,
                        "relative_path": rel_path,
                        "file_size_bytes": os.path.getsize(full_path)
                    })

        return {
            "query": query,
            "matches": matched_files,
            "count": len(matched_files)
        }

class DocumentReaderTool(BaseTool):
    def __init__(self, data_dir: Optional[str] = None):
        super().__init__(
            name="read_document",
            description="Reads and extracts structured invoice data from a document file.",
            risk_level=RiskLevel.LOW
        )
        self.data_dir = data_dir or os.path.join(os.getcwd(), "app", "sandbox", "company_data")

    def execute(self, **kwargs) -> Dict[str, Any]:
        file_path = kwargs.get("file_path", "")
        if not os.path.isabs(file_path):
            full_path = os.path.join(self.data_dir, file_path)
        else:
            full_path = file_path

        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Document not found at path: {file_path}")

        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        content = "".join(lines)
        invoice_number = None
        invoice_date = None
        raw_due_date = None
        amount = None
        vendor = "Unknown Vendor"

        for line in lines:
            line_str = line.strip()
            if "Invoice Number:" in line_str:
                invoice_number = line_str.split("Invoice Number:")[1].strip()
            elif "Invoice Date:" in line_str:
                invoice_date = line_str.split("Invoice Date:")[1].strip()
            elif "Due Date:" in line_str:
                raw_due_date = line_str.split("Due Date:")[1].strip()
            elif "Total Due:" in line_str or "Total:" in line_str:
                if "$" in line_str:
                    after_dollar = line_str.split("$")[1].split()[0]
                    clean_amt = after_dollar.replace(",", "").strip()
                    try:
                        amount = float(clean_amt)
                    except ValueError:
                        pass
                else:
                    amt_match = re.search(r"([0-9,]+\.[0-9]{2})", line_str)
                    if amt_match:
                        amount = float(amt_match.group(1).replace(",", ""))

        for line in lines[:6]:
            clean = line.replace("=", "").strip()
            if any(term in clean.upper() for term in ["INC", "CORP", "LLC", "SERVICES", "HARDWARE", "LOGISTICS"]):
                vendor = clean
                break

        return {
            "file_path": file_path,
            "vendor_name": vendor,
            "invoice_number": invoice_number,
            "invoice_date": invoice_date,
            "due_date_raw": raw_due_date,
            "amount": amount,
            "currency": "USD",
            "full_text_snippet": content[:300] + "..."
        }
