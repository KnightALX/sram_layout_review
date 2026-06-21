"""Legacy report generation — thin shim over report/ submodules."""
import os
from datetime import datetime
from typing import Tuple

from report.legacy_theme import REPORTLAB_AVAILABLE
from report.pdf_legacy import PDFReportGenerator
from report.pptx_legacy import PPTXReportGenerator
from review_engine import ProfessionalLayoutReviewEngine


def generate_reports(engine: ProfessionalLayoutReviewEngine,
                     output_dir: str,
                     base_name: str = "layout_review_report") -> Tuple[str, str]:
    """Generate PPTX and PDF reports. Returns (pptx_path, pdf_path)."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    pptx_path = os.path.join(output_dir, f"{base_name}_{timestamp}.pptx")
    pptx_gen = PPTXReportGenerator()
    pptx_gen.create_report(engine)
    pptx_gen.save(pptx_path)

    pdf_path = os.path.join(output_dir, f"{base_name}_{timestamp}.pdf")
    if REPORTLAB_AVAILABLE:
        pdf_gen = PDFReportGenerator()
        story = pdf_gen.create_report(engine)
        pdf_gen.save(story, pdf_path)
    else:
        print("Warning: PDF generation requires reportlab")
        pdf_path = None

    return pptx_path, pdf_path


def generate_routing_report(state, app_state, output_dir="./output", base_name="routing_report"):
    """Thin wrapper for the routing PPTX report (compatibility shim)."""
    from report.routing_pptx import generate_routing_pptx
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{base_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx")
    return generate_routing_pptx(state, app_state, path)
