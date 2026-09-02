import io
from reportlab.lib.pagesizes import A4, A5
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from app.utils.codes import draw_qr_code, draw_barcode

TEXT_DARK = HexColor("#0F172A")
TEXT_MUTED = HexColor("#64748B")
BORDER = HexColor("#E2E8F0")
WHITE = HexColor("#FFFFFF")

STYLE_COLORS = {
    "classique": {"primary": HexColor("#1D4ED8"), "accent": HexColor("#1D4ED8")},
    "moderne": {"primary": HexColor("#0F172A"), "accent": HexColor("#1D4ED8")},
    "audacieux": {"primary": HexColor("#1D4ED8"), "accent": HexColor("#10B981")},
    "serein": {"primary": HexColor("#5F7470"), "accent": HexColor("#8FA79C")},
    "vague": {"primary": HexColor("#0E7C86"), "accent": HexColor("#14B8A6")},
}


def _page_size(taille):
    return A5 if str(taille).upper() == "A5" else A4


def _scale(taille):
    """Facteur d'échelle des marges/polices pour le format A5."""
    return 0.82 if str(taille).upper() == "A5" else 1.0


def _header(c, width, height, clinic, titre, style="classique", taille="A4"):
    s = _scale(taille)
    colors = STYLE_COLORS.get(style, STYLE_COLORS["classique"])
    band_h = 26 * mm * s

    if style == "moderne":
        c.setStrokeColor(TEXT_DARK)
        c.setLineWidth(1.4)
        c.line(15 * mm, height - band_h, width - 15 * mm, height - band_h)
        text_color = TEXT_DARK
        title_color = colors["accent"]
        y_name = height - 12 * mm
        y_sub = height - 18 * mm
        x_text = 15 * mm
        if clinic.get("logo_path"):
            try:
                img = ImageReader(clinic["logo_path"])
                c.drawImage(img, 15 * mm, height - 24 * mm, width=16 * mm, height=16 * mm,
                            preserveAspectRatio=True, mask='auto')
                x_text = 34 * mm
            except Exception:
                pass
    elif style == "serein":
        # Bandeau tinté très doux + fine ligne sauge, typographie discrète
        c.setFillColor(HexColor("#F4F6F5"))
        c.rect(0, height - band_h, width, band_h, fill=1, stroke=0)
        c.setStrokeColor(colors["accent"])
        c.setLineWidth(0.9)
        c.line(15 * mm, height - band_h, width - 15 * mm, height - band_h)
        text_color = HexColor("#3F4A47")
        title_color = colors["primary"]
        y_name = height - (band_h / 2) + 3 * mm
        y_sub = height - (band_h / 2) - 3 * mm
        x_text = 15 * mm
        if clinic.get("logo_path"):
            try:
                img = ImageReader(clinic["logo_path"])
                c.drawImage(img, 15 * mm, height - band_h + (band_h - 15 * mm * s) / 2,
                            width=15 * mm * s, height=15 * mm * s, preserveAspectRatio=True, mask='auto')
                x_text = 15 * mm + 18 * mm * s
            except Exception:
                pass
    elif style == "vague":
        c.setFillColor(colors["primary"])
        p = c.beginPath()
        p.moveTo(0, height)
        p.lineTo(0, height - band_h)
        p.curveTo(width * 0.55, height - band_h - 8 * mm, width * 0.7, height - band_h + 10 * mm, width, height - band_h + 2 * mm)
        p.lineTo(width, height)
        p.close()
        c.drawPath(p, fill=1, stroke=0)
        c.setFillColor(colors["accent"])
        c.circle(width - 22 * mm, height - 10 * mm, 1.6 * mm, fill=1, stroke=0)
        text_color = WHITE
        title_color = WHITE
        x_text = 15 * mm
        y_name = height - 12 * mm
        y_sub = height - 18 * mm
        if clinic.get("logo_path"):
            try:
                img = ImageReader(clinic["logo_path"])
                c.drawImage(img, 15 * mm, height - 22 * mm, width=14 * mm * s, height=14 * mm * s,
                            preserveAspectRatio=True, mask='auto')
                x_text = 15 * mm + 17 * mm * s
            except Exception:
                pass
    else:
        if style == "audacieux":
            c.setFillColor(colors["primary"])
            c.rect(0, height - band_h, width, band_h, fill=1, stroke=0)
            c.setFillColor(colors["accent"])
            c.rect(0, height - band_h, width, 2.2 * mm, fill=1, stroke=0)
        else:
            c.setFillColor(colors["primary"])
            c.rect(0, height - band_h, width, band_h, fill=1, stroke=0)
        text_color = WHITE
        title_color = WHITE
        x_text = 15 * mm
        y_name = height - (band_h / 2) + 3 * mm
        y_sub = height - (band_h / 2) - 3 * mm
        if clinic.get("logo_path"):
            try:
                img = ImageReader(clinic["logo_path"])
                c.drawImage(img, 15 * mm, height - band_h + (band_h - 16 * mm * s) / 2,
                            width=16 * mm * s, height=16 * mm * s, preserveAspectRatio=True, mask='auto')
                x_text = 15 * mm + 19 * mm * s
            except Exception:
                pass

    c.setFillColor(text_color)
    c.setFont("Helvetica-Bold", 15 * s if style != "audacieux" else 17 * s)
    c.drawString(x_text, y_name, clinic.get("nom_clinique") or "Cabinet Médical")
    c.setFont("Helvetica", 8.5 * s)
    sous = " • ".join(filter(None, [clinic.get("nom_medecin"), clinic.get("specialite"), clinic.get("telephone")]))
    c.drawString(x_text, y_sub, sous[:95])

    c.setFillColor(title_color)
    c.setFont("Helvetica-Bold", 11 * s)
    c.drawRightString(width - 15 * mm, y_name - 1 * mm, titre)

    c.setFillColor(TEXT_DARK)
    return height - band_h - 8 * mm * s if style not in ("moderne", "serein") else height - band_h - 6 * mm * s


def _footer(c, width, clinic, style="classique"):
    c.setStrokeColor(BORDER)
    c.line(15 * mm, 15 * mm, width - 15 * mm, 15 * mm)
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 7)
    contact = " • ".join(filter(None, [clinic.get("telephone"), clinic.get("email"), clinic.get("adresse")]))
    c.drawCentredString(width / 2, 10 * mm, contact[:120])
    if clinic.get("numero_fiscal"):
        c.drawCentredString(width / 2, 6 * mm, f"N° Fiscal : {clinic['numero_fiscal']}")


def _patient_block(c, width, patient, y_start, age, style, taille):
    s = _scale(taille)
    c.setFillColor(TEXT_DARK)
    c.setFont("Helvetica-Bold", 10 * s)
    c.drawString(15 * mm, y_start, f"Patient : {patient['prenom']} {patient['nom']}")
    c.setFont("Helvetica", 9 * s)
    c.setFillColor(TEXT_MUTED)
    infos = f"Âge : {age if age is not None else '—'}   •   N° Patient : {patient.get('numero_patient', '')}"
    c.drawString(15 * mm, y_start - 5 * mm * s, infos)
    c.setStrokeColor(BORDER)
    c.line(15 * mm, y_start - 8 * mm * s, width - 15 * mm, y_start - 8 * mm * s)
    return y_start - 14 * mm * s


def _signature_block(c, width, clinic, y, taille, doc_ref=None):
    s = _scale(taille)
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica-Oblique", 8 * s)
    c.drawRightString(width - 15 * mm, y, "Signature et cachet")
    x = width - 55 * mm
    if clinic.get("signature_path"):
        try:
            img = ImageReader(clinic["signature_path"])
            c.drawImage(img, x, y - 20 * mm * s, width=40 * mm * s, height=18 * mm * s,
                        preserveAspectRatio=True, mask='auto', anchor='sw')
        except Exception:
            pass
    if clinic.get("cachet_path"):
        try:
            img = ImageReader(clinic["cachet_path"])
            c.drawImage(img, x - 22 * mm * s, y - 22 * mm * s, width=20 * mm * s, height=20 * mm * s,
                        preserveAspectRatio=True, mask='auto', anchor='sw')
        except Exception:
            pass
    if not clinic.get("signature_path") and not clinic.get("cachet_path"):
        c.setStrokeColor(BORDER)
        c.rect(x, y - 20 * mm * s, 40 * mm * s, 18 * mm * s)

    if doc_ref:
        qr_size = 18 * mm * s
        draw_qr_code(c, 15 * mm, y - 20 * mm * s, doc_ref, size_mm=18 * s)
        draw_barcode(c, 15 * mm, y - 25 * mm * s, doc_ref, width_mm=42 * s, height_mm=6 * s)
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 6 * s)
        c.drawString(15 * mm, y - 27 * mm * s, doc_ref)


def generate_prescription_pdf(clinic, patient, prescription, lignes, age, style="classique", taille="A4"):
    buf = io.BytesIO()
    width, height = _page_size(taille)
    s = _scale(taille)
    c = canvas.Canvas(buf, pagesize=(width, height))
    y = _header(c, width, height, clinic, "ORDONNANCE MÉDICALE", style, taille)
    y = _patient_block(c, width, patient, y, age, style, taille)

    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 8 * s)
    c.drawString(15 * mm, y, f"Date : {prescription.get('date_str', '')}")
    y -= 10 * mm * s

    c.setFillColor(TEXT_DARK)
    for i, ligne in enumerate(lignes, start=1):
        if y < 40 * mm:
            c.showPage()
            y = _header(c, width, height, clinic, "ORDONNANCE MÉDICALE (suite)", style, taille)
        c.setFont("Helvetica-Bold", 11 * s)
        c.drawString(15 * mm, y, f"{i}. {ligne['medicament']}")
        y -= 5.5 * mm * s
        c.setFont("Helvetica", 9 * s)
        c.setFillColor(TEXT_MUTED)
        detail = "   ".join(filter(None, [ligne.get("dosage"), ligne.get("frequence"), ligne.get("duree")]))
        c.drawString(20 * mm, y, detail)
        y -= 5 * mm * s
        if ligne.get("instructions"):
            c.setFont("Helvetica-Oblique", 8 * s)
            c.drawString(20 * mm, y, ligne["instructions"][:110])
            y -= 5 * mm * s
        c.setFillColor(TEXT_DARK)
        y -= 2 * mm * s

    if prescription.get("notes"):
        y -= 4 * mm
        c.setFont("Helvetica-Bold", 9 * s)
        c.drawString(15 * mm, y, "Notes :")
        c.setFont("Helvetica", 9 * s)
        c.drawString(35 * mm, y, prescription["notes"][:90])

    _signature_block(c, width, clinic, 50 * mm, taille, doc_ref=f"RX-{prescription.get('id','')}")
    _footer(c, width, clinic, style)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


def generate_request_pdf(clinic, patient, request_data, items_text, age, titre, style="classique", taille="A4"):
    buf = io.BytesIO()
    width, height = _page_size(taille)
    s = _scale(taille)
    c = canvas.Canvas(buf, pagesize=(width, height))
    y = _header(c, width, height, clinic, titre, style, taille)
    y = _patient_block(c, width, patient, y, age, style, taille)

    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 8 * s)
    c.drawString(15 * mm, y, f"Date : {request_data.get('date_str', '')}")
    y -= 10 * mm * s

    c.setFillColor(TEXT_DARK)
    c.setFont("Helvetica-Bold", 10 * s)
    c.drawString(15 * mm, y, "Examens / analyses demandés :")
    y -= 7 * mm * s
    c.setFont("Helvetica", 10 * s)
    for line in items_text.split("\n"):
        if not line.strip():
            continue
        if y < 25 * mm:
            c.showPage()
            y = _header(c, width, height, clinic, titre + " (suite)", style, taille)
        c.drawString(20 * mm, y, f"•  {line.strip()[:100]}")
        y -= 6 * mm * s

    if request_data.get("notes"):
        y -= 4 * mm
        c.setFont("Helvetica-Bold", 9 * s)
        c.drawString(15 * mm, y, "Notes cliniques :")
        c.setFont("Helvetica", 9 * s)
        c.drawString(45 * mm, y, request_data["notes"][:90])

    _signature_block(c, width, clinic, 50 * mm, taille, doc_ref=f"REQ-{request_data.get('id','')}")
    _footer(c, width, clinic, style)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


def generate_custom_document_pdf(clinic, patient, document, age, style="classique", taille="A4"):
    buf = io.BytesIO()
    width, height = _page_size(taille)
    s = _scale(taille)
    c = canvas.Canvas(buf, pagesize=(width, height))
    titre = (document.get("type_label") or "DOCUMENT MÉDICAL").upper()
    y = _header(c, width, height, clinic, titre, style, taille)
    y = _patient_block(c, width, patient, y, age, style, taille)

    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 8 * s)
    c.drawString(15 * mm, y, f"Date : {document.get('date_str', '')}")
    y -= 10 * mm * s

    c.setFillColor(TEXT_DARK)
    c.setFont("Helvetica-Bold", 12 * s)
    c.drawString(15 * mm, y, document.get("titre", ""))
    y -= 9 * mm * s

    c.setFont("Helvetica", 10 * s)
    import textwrap
    contenu = (document.get("contenu") or "").replace("\r\n", "\n")
    for paragraph in contenu.split("\n"):
        if not paragraph.strip():
            y -= 4 * mm * s
            continue
        wrapped = textwrap.wrap(paragraph, width=int(95 / s))
        for line in wrapped:
            if y < 30 * mm:
                c.showPage()
                y = _header(c, width, height, clinic, titre + " (suite)", style, taille)
                c.setFont("Helvetica", 10 * s)
            c.drawString(15 * mm, y, line)
            y -= 5.2 * mm * s

    _signature_block(c, width, clinic, 50 * mm, taille, doc_ref=f"DOC-{document.get('id','')}")
    _footer(c, width, clinic, style)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


def generate_invoice_pdf(clinic, patient, facture, lignes, style="classique", taille="A4"):
    buf = io.BytesIO()
    width, height = _page_size(taille)
    s = _scale(taille)
    c = canvas.Canvas(buf, pagesize=(width, height))
    y = _header(c, width, height, clinic, f"FACTURE N° {facture.get('numero_facture', '')}", style, taille)

    c.setFillColor(TEXT_DARK)
    c.setFont("Helvetica-Bold", 10 * s)
    c.drawString(15 * mm, y, f"Patient : {patient['prenom']} {patient['nom']}")
    c.setFont("Helvetica", 9 * s)
    c.setFillColor(TEXT_MUTED)
    c.drawString(15 * mm, y - 5 * mm * s, f"Date : {facture.get('date_str', '')}")
    y -= 16 * mm * s

    colors = STYLE_COLORS.get(style, STYLE_COLORS["classique"])
    c.setFillColor(colors["primary"])
    c.rect(15 * mm, y, width - 30 * mm, 8 * mm, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 9 * s)
    c.drawString(18 * mm, y + 2.5 * mm, "Désignation")
    c.drawCentredString(width - 65 * mm, y + 2.5 * mm, "Qté")
    c.drawCentredString(width - 45 * mm, y + 2.5 * mm, "P.U.")
    c.drawRightString(width - 18 * mm, y + 2.5 * mm, "Total")
    y -= 8 * mm

    c.setFillColor(TEXT_DARK)
    c.setFont("Helvetica", 9 * s)
    total = 0
    for ligne in lignes:
        sous_total = ligne["quantite"] * ligne["prix_unitaire"]
        total += sous_total
        c.drawString(18 * mm, y + 2 * mm, str(ligne["designation"])[:55])
        c.drawCentredString(width - 65 * mm, y + 2 * mm, str(ligne["quantite"]))
        c.drawCentredString(width - 45 * mm, y + 2 * mm, f"{ligne['prix_unitaire']:.2f}")
        c.drawRightString(width - 18 * mm, y + 2 * mm, f"{sous_total:.2f}")
        c.setStrokeColor(BORDER)
        c.line(15 * mm, y, width - 15 * mm, y)
        y -= 7 * mm * s

    y -= 3 * mm
    c.setFont("Helvetica-Bold", 11 * s)
    c.drawRightString(width - 18 * mm, y, f"Total : {facture.get('montant_total', total):.2f} {clinic.get('devise','DZD')}")
    y -= 6 * mm * s
    c.setFont("Helvetica", 9 * s)
    c.setFillColor(TEXT_MUTED)
    c.drawRightString(width - 18 * mm, y, f"Payé : {facture.get('montant_paye', 0):.2f} {clinic.get('devise','DZD')}")

    _signature_block(c, width, clinic, 50 * mm, taille, doc_ref=f"FAC-{facture.get('numero_facture', facture.get('id',''))}")
    _footer(c, width, clinic, style)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


def generate_evolution_report_pdf(clinic, patient, consultations, periode, style="classique"):
    buf = io.BytesIO()
    width, height = A4
    c = canvas.Canvas(buf, pagesize=A4)
    periode_labels = {"semaine": "7 derniers jours", "mois": "30 derniers jours", "annee": "12 derniers mois"}
    y = _header(c, width, height, clinic, "RAPPORT D'ÉVOLUTION MÉDICALE", style, "A4")

    c.setFillColor(TEXT_DARK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(15 * mm, y, f"{patient.get('prenom','')} {patient.get('nom','')}")
    c.setFont("Helvetica", 9)
    c.setFillColor(TEXT_MUTED)
    c.drawString(15 * mm, y - 5.5 * mm, f"N° {patient.get('numero_patient','')} — Période : {periode_labels.get(periode, periode)}")
    y -= 16 * mm

    if not consultations:
        c.setFont("Helvetica", 10)
        c.setFillColor(TEXT_DARK)
        c.drawString(15 * mm, y, "Aucune mesure enregistrée sur cette période.")
    else:
        def _values(key):
            return [c[key] for c in consultations if c.get(key) is not None]

        resume = [
            ("Poids (kg)", _values("poids")),
            ("Température (°C)", _values("temperature")),
            ("Fréquence cardiaque (bpm)", _values("frequence_cardiaque")),
            ("Saturation O₂ (%)", _values("saturation_oxygene")),
            ("Glycémie (g/l)", _values("glycemie")),
        ]
        c.setFont("Helvetica-Bold", 10)
        c.drawString(15 * mm, y, "Synthèse de la période")
        y -= 7 * mm
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(15 * mm, y, "Mesure")
        c.drawString(85 * mm, y, "Min")
        c.drawString(115 * mm, y, "Max")
        c.drawString(145 * mm, y, "Moyenne")
        y -= 2 * mm
        c.setStrokeColor(BORDER)
        c.line(15 * mm, y, width - 15 * mm, y)
        y -= 5 * mm
        c.setFont("Helvetica", 9)
        for label, values in resume:
            if not values:
                continue
            c.setFillColor(TEXT_DARK)
            c.drawString(15 * mm, y, label)
            c.setFillColor(TEXT_MUTED)
            c.drawString(85 * mm, y, f"{min(values):.1f}")
            c.drawString(115 * mm, y, f"{max(values):.1f}")
            c.drawString(145 * mm, y, f"{sum(values)/len(values):.1f}")
            y -= 6.5 * mm

        y -= 8 * mm
        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(15 * mm, y, "Détail chronologique des mesures")
        y -= 7 * mm
        c.setFont("Helvetica-Bold", 8)
        headers = ["Date", "Poids", "Tension", "Temp.", "FC", "SpO2", "Glyc."]
        xs = [15, 55, 80, 105, 125, 145, 165]
        for h_txt, x in zip(headers, xs):
            c.drawString(x * mm, y, h_txt)
        y -= 2 * mm
        c.line(15 * mm, y, width - 15 * mm, y)
        y -= 5.5 * mm
        c.setFont("Helvetica", 8)
        for cons in consultations:
            if y < 25 * mm:
                c.showPage()
                y = _header(c, width, height, clinic, "RAPPORT D'ÉVOLUTION MÉDICALE (suite)", style, "A4")
                c.setFont("Helvetica", 8)
            date_str = str(cons.get("date_consultation", ""))[:10]
            row = [date_str, cons.get("poids") or "—", cons.get("tension") or "—", cons.get("temperature") or "—",
                   cons.get("frequence_cardiaque") or "—", cons.get("saturation_oxygene") or "—", cons.get("glycemie") or "—"]
            for val, x in zip(row, xs):
                c.drawString(x * mm, y, str(val))
            y -= 6 * mm

    _footer(c, width, clinic, style)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf
