"""
Law Enforcement Investigation Report and Legal Requisition Notice Generator.
Renders Jinja2 HTML templates and compiles court-ready PDF documents using WeasyPrint.
"""

import hashlib
import logging
from pathlib import Path
import time
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"


class ReportGenerator:
    """Compiles court-ready investigation reports under Section 91 CrPC / Section 94 BNSS."""

    def __init__(self) -> None:
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=True
        )

    def render_html_report(self, context: Dict[str, Any]) -> str:
        """Render the Jinja2 HTML template with forensic trace parameters."""
        template = self.env.get_template("investigation.html")

        # Fill sensible defaults for law enforcement presentation
        now_str = time.strftime("%d-%b-%Y %H:%M:%S IST", time.localtime())
        audit_raw = f"{context.get('case_number')}_{context.get('seed_address')}_{time.time()}"
        audit_hash = hashlib.sha256(audit_raw.encode()).hexdigest()[:24].upper()

        full_context = {
            "case_number": context.get("case_number", "CYBER/FIR/2026/8912"),
            "fir_number": context.get("fir_number", "8912/2026"),
            "police_station": context.get("police_station", "Special Cyber Crime Cell, New Delhi"),
            "incident_date": context.get("incident_date", time.strftime("%d-%b-%Y")),
            "io_name": context.get("io_name", "Insp. Rajesh Kumar"),
            "io_badge": context.get("io_badge", "DL-CY-8821"),
            "victim_name": context.get("victim_name", "Cyber Fraud Complainant"),
            "victim_loss_inr": context.get("victim_loss_inr", "21,87,500"),
            "victim_loss_usdt": context.get("victim_loss_usdt", "25,000.00"),
            "seed_address": context.get("seed_address", "TNaRAoLUyYEV2uF7GUrzSjRQTU8v5ZJ5VR"),
            "chain": context.get("chain", "tron"),
            "total_hops": context.get("total_hops", 3),
            "attribution_pct": context.get("attribution_pct", 98.5),
            "hop_breakdown": context.get("hop_breakdown", []),
            "terminal_vasp": context.get("terminal_vasp", "Binance"),
            "fiu_registered": context.get("fiu_registered", True),
            "terminal_deposit_address": context.get("terminal_deposit_address", "TNaRAoLUyYEV2uF7GUrzSjRQTU8v5ZJ5VR"),
            "vasp_nodal_email": context.get("vasp_nodal_email", "compliance@binance.com"),
            "timestamp_str": now_str,
            "audit_hash": audit_hash
        }

        return template.render(**full_context)

    def generate_pdf_report(self, context: Dict[str, Any]) -> bytes:
        """
        Generate PDF bytes from rendered HTML.
        Falls back to HTML bytes if WeasyPrint system C libraries are absent on host OS.
        """
        html_content = self.render_html_report(context)

        try:
            from weasyprint import HTML
            pdf_bytes = HTML(string=html_content).write_pdf()
            return pdf_bytes
        except Exception as exc:
            logger.warning(
                "WeasyPrint PDF rendering not available in current environment (%s). "
                "Returning HTML report document.", exc
            )
            return html_content.encode("utf-8")


# Global generator singleton
report_generator = ReportGenerator()


def get_report_generator() -> ReportGenerator:
    """Dependency provider for report generation."""
    return report_generator
