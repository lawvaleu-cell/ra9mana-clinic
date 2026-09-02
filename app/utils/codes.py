from reportlab.graphics.barcode import qr, code128
from reportlab.graphics.shapes import Drawing
from reportlab.lib.units import mm


def draw_qr_code(c, x, y, data, size_mm=20):
    """Dessine un QR code vectoriel directement sur le canevas PDF (aucune dépendance externe)."""
    try:
        widget = qr.QrCodeWidget(data)
        b = widget.getBounds()
        w = b[2] - b[0]
        h = b[3] - b[1]
        size_pt = size_mm * mm
        d = Drawing(size_pt, size_pt, transform=[size_pt / w, 0, 0, size_pt / h, 0, 0])
        d.add(widget)
        d.drawOn(c, x, y)
    except Exception:
        pass


def draw_barcode(c, x, y, data, width_mm=45, height_mm=10):
    """Dessine un code-barres Code128 directement sur le canevas PDF."""
    try:
        bar_width = (width_mm * mm) / (len(data) * 11 + 35)
        barcode = code128.Code128(data, barHeight=height_mm * mm, barWidth=max(bar_width, 0.35))
        barcode.drawOn(c, x, y)
    except Exception:
        pass
