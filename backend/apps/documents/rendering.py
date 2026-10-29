import io
from datetime import date
from decimal import Decimal
from importlib.metadata import version

from django.template.loader import render_to_string
from pypdf import PdfReader


TEMPLATE_VERSION = 1
RENDERER_VERSION = f"weasyprint-{version('weasyprint')}"


class PdfRenderingError(RuntimeError):
    pass


def _money(value):
    amount = Decimal(value)
    rendered = f"{amount:,.2f}"
    return rendered.replace(",", "X").replace(".", ",").replace("X", ".")


def _quantity(value):
    return f"{Decimal(value):f}".rstrip("0").rstrip(".")


def _date(value):
    return date.fromisoformat(value).strftime("%d.%m.%Y") if value else "-"


def render_invoice_html(payload):
    lines = [
        {
            **line,
            "quantity_display": _quantity(line["quantity"]),
            "unit_price_display": _money(line["unit_price_net"]),
            "discount_display": _money(line["discount_percent"]),
            "tax_rate_display": _money(line["tax_rate"]),
            "net_display": _money(line["net_amount"]),
        }
        for line in payload["lines"]
    ]
    breakdown = [
        {
            **group,
            "tax_rate_display": _money(group["tax_rate"]),
            "net_display": _money(group["net_amount"]),
            "tax_display": _money(group["tax_amount"]),
            "gross_display": _money(group["gross_amount"]),
        }
        for group in payload["totals"]["tax_breakdown"]
    ]
    context = {
        "invoice": payload,
        "lines": lines,
        "breakdown": breakdown,
        "issue_date": _date(payload["issue_date"]),
        "service_date_from": _date(payload["service_date_from"]),
        "service_date_to": _date(payload["service_date_to"]),
        "due_date": _date(payload["due_date"]),
        "net_total": _money(payload["totals"]["net_total"]),
        "tax_total": _money(payload["totals"]["tax_total"]),
        "gross_total": _money(payload["totals"]["gross_total"]),
    }
    return render_to_string("documents/invoice_standard.html", context)


def _verify_pdf(pdf_bytes, payload):
    if not pdf_bytes.startswith(b"%PDF-"):
        raise PdfRenderingError("Der Renderer hat keine gültige PDF-Signatur erzeugt.")
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as error:
        raise PdfRenderingError(f"Das erzeugte PDF konnte nicht geprüft werden: {error}") from error
    if not reader.pages:
        raise PdfRenderingError("Das erzeugte PDF besitzt keine Seite.")
    expected = (
        payload["document_number"], payload["issuer"]["name"],
        payload["recipient"]["name"],
    )
    missing = [value for value in expected if value not in text]
    if missing:
        raise PdfRenderingError(
            "Das erzeugte PDF enthält nicht alle Kerndaten: " + ", ".join(missing)
        )


def render_invoice_pdf(snapshot):
    from weasyprint import HTML

    html = render_invoice_html(snapshot.payload)
    pdf_bytes = HTML(string=html).write_pdf(
        custom_metadata=True,
        pdf_identifier=snapshot.sha256.encode("ascii"),
    )
    _verify_pdf(pdf_bytes, snapshot.payload)
    return pdf_bytes
