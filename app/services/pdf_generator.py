import io
import logging
import os
import unicodedata
from typing import Any, Dict, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

logger = logging.getLogger("bulk_certificates")

_FONT_REGISTERED = False
_REG_FONT_NAME = "Helvetica"
_REG_FONT_BOLD = "Helvetica-Bold"


def register_certificate_fonts() -> Tuple[str, str]:
    """Register Unicode TTF font for ReportLab canvas rendering with multi-platform fallbacks."""
    global _FONT_REGISTERED, _REG_FONT_NAME, _REG_FONT_BOLD
    if _FONT_REGISTERED:
        return _REG_FONT_NAME, _REG_FONT_BOLD

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assets_dir = os.path.join(base_dir, "assets")

    font_candidates = [
        (os.path.join(assets_dir, "DejaVuSans.ttf"), os.path.join(assets_dir, "DejaVuSans-Bold.ttf")),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("C:\\Windows\\Fonts\\arial.ttf", "C:\\Windows\\Fonts\\arialbd.ttf"),
        ("C:\\Windows\\Fonts\\segoeui.ttf", "C:\\Windows\\Fonts\\segoeuib.ttf"),
    ]

    for reg_path, bold_path in font_candidates:
        if os.path.exists(reg_path):
            try:
                pdfmetrics.registerFont(TTFont("CertUnicode", reg_path))
                if os.path.exists(bold_path):
                    pdfmetrics.registerFont(TTFont("CertUnicode-Bold", bold_path))
                    _REG_FONT_BOLD = "CertUnicode-Bold"
                else:
                    _REG_FONT_BOLD = "CertUnicode"
                _REG_FONT_NAME = "CertUnicode"
                _FONT_REGISTERED = True
                logger.info(f"Registered Certificate TTF Font: {_REG_FONT_NAME} from {reg_path}")
                return _REG_FONT_NAME, _REG_FONT_BOLD
            except Exception as e:
                logger.warning(f"Failed to register TTF font at {reg_path}: {e}")

    _FONT_REGISTERED = True
    return _REG_FONT_NAME, _REG_FONT_BOLD


def safe_text(text: str) -> str:
    """Ensure string is clean printable unicode and normalize text."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", str(text))
    return "".join(ch for ch in normalized if ch == " " or not unicodedata.category(ch).startswith("C"))


def generate_pdf(data: Dict[str, Any]) -> bytes:
    """
    Generate an A4 Landscape Certificate PDF from input data dictionary.

    Expected keys:
    - title: str
    - recipient_name: str
    - recipient_email: str
    - achievement: str (optional)
    - issuer_name: str
    - issue_date: str
    - signatory_name: str
    - signatory_title: str
    - verification_code: str
    - base_url: str (optional)
    """
    font_reg, font_bold = register_certificate_fonts()

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)

    c.setFillColor(colors.HexColor("#FCFDFD"))
    c.rect(0, 0, width, height, fill=True, stroke=False)

    c.setLineWidth(4)
    c.setStrokeColor(colors.HexColor("#1E293B"))
    c.rect(20, 20, width - 40, height - 40, fill=False, stroke=True)

    c.setLineWidth(1.5)
    c.setStrokeColor(colors.HexColor("#D97706"))
    c.rect(26, 26, width - 52, height - 52, fill=False, stroke=True)

    c.setLineWidth(0.5)
    c.setStrokeColor(colors.HexColor("#94A3B8"))
    c.rect(30, 30, width - 60, height - 60, fill=False, stroke=True)

    corner_size = 12
    c.setFillColor(colors.HexColor("#D97706"))
    for cx, cy in [(32, 32), (width - 32 - corner_size, 32), (32, height - 32 - corner_size), (width - 32 - corner_size, height - 32 - corner_size)]:
        c.rect(cx, cy, corner_size, corner_size, fill=True, stroke=False)

    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont(font_bold, 28)
    header_title = safe_text(data.get("title", "CERTIFICATE OF ACHIEVEMENT")).upper()
    c.drawCentredString(width / 2.0, height - 90, header_title)

    c.setLineWidth(2)
    c.setStrokeColor(colors.HexColor("#D97706"))
    c.line(width / 2.0 - 120, height - 105, width / 2.0 + 120, height - 105)

    c.setFillColor(colors.HexColor("#475569"))
    c.setFont(font_reg, 14)
    c.drawCentredString(width / 2.0, height - 145, "PROUDLY PRESENTED TO")

    recipient_name = safe_text(data.get("recipient_name", "Recipient Name"))
    max_name_width = width - 120
    base_font_size = 32
    target_font_size = base_font_size

    current_text_width = pdfmetrics.stringWidth(recipient_name, font_bold, target_font_size)
    while current_text_width > max_name_width and target_font_size > 14:
        target_font_size -= 2
        current_text_width = pdfmetrics.stringWidth(recipient_name, font_bold, target_font_size)

    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont(font_bold, target_font_size)
    c.drawCentredString(width / 2.0, height - 200, recipient_name)

    c.setLineWidth(1)
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.line(width / 2.0 - (min(current_text_width, max_name_width) / 2.0 + 10), height - 212,
           width / 2.0 + (min(current_text_width, max_name_width) / 2.0 + 10), height - 212)

    achievement_text = safe_text(data.get("achievement") or "for successful completion and outstanding performance.")
    c.setFillColor(colors.HexColor("#334155"))
    c.setFont(font_reg, 13)
    c.drawCentredString(width / 2.0, height - 250, achievement_text)

    issuer_name = safe_text(data.get("issuer_name", "Issuer Name"))
    issue_date = safe_text(data.get("issue_date", "Date"))
    info_line = f"Issued by {issuer_name} on {issue_date}"
    c.setFont(font_reg, 11)
    c.setFillColor(colors.HexColor("#64748B"))
    c.drawCentredString(width / 2.0, height - 280, info_line)

    signatory_name = safe_text(data.get("signatory_name", "Authorized Signatory"))
    signatory_title = safe_text(data.get("signatory_title", "Title"))

    sig_x = width - 220
    sig_y = 120
    c.setLineWidth(1)
    c.setStrokeColor(colors.HexColor("#475569"))
    c.line(sig_x - 80, sig_y, sig_x + 80, sig_y)

    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont(font_bold, 12)
    c.drawCentredString(sig_x, sig_y - 18, signatory_name)

    c.setFillColor(colors.HexColor("#64748B"))
    c.setFont(font_reg, 10)
    c.drawCentredString(sig_x, sig_y - 32, signatory_title)

    date_x = 220
    c.line(date_x - 60, sig_y, date_x + 60, sig_y)

    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont(font_bold, 12)
    c.drawCentredString(date_x, sig_y - 18, issue_date)

    c.setFillColor(colors.HexColor("#64748B"))
    c.setFont(font_reg, 10)
    c.drawCentredString(date_x, sig_y - 32, "Date of Issue")

    v_code = safe_text(data.get("verification_code", "N/A"))
    base_url = data.get("base_url", "http://localhost:8000").rstrip("/")
    verify_url = f"{base_url}/api/verify/{v_code}"

    c.setFont(font_bold, 9)
    c.setFillColor(colors.HexColor("#475569"))
    c.drawString(45, 50, f"Verification Code: {v_code}")

    c.setFont(font_reg, 9)
    c.setFillColor(colors.HexColor("#64748B"))
    c.drawString(45, 38, f"Verify at: {verify_url}")

    c.showPage()
    c.save()

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
