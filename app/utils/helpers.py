from datetime import datetime, date

MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"]
JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

STATUT_RDV_LABELS = {
    "planifie": "Planifié",
    "confirme": "Confirmé",
    "en_attente": "En attente",
    "en_consultation": "En consultation",
    "termine": "Terminé",
    "annule": "Annulé",
    "absent": "Absent",
}

STATUT_RDV_COULEURS = {
    "planifie": "#64748B",
    "confirme": "#2563EB",
    "en_attente": "#F59E0B",
    "en_consultation": "#8B5CF6",
    "termine": "#10B981",
    "annule": "#EF4444",
    "absent": "#DC2626",
}


def format_date_fr(value, with_weekday=False):
    if value is None:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    jour = f"{JOURS_FR[value.weekday()].capitalize()} " if with_weekday else ""
    return f"{jour}{value.day} {MOIS_FR[value.month - 1]} {value.year}"


def format_datetime_fr(value):
    if value is None:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    return f"{format_date_fr(value)} à {value.strftime('%H:%M')}"


def calculate_age(birth_date):
    if not birth_date:
        return None
    if isinstance(birth_date, str):
        try:
            birth_date = datetime.fromisoformat(birth_date).date()
        except ValueError:
            return None
    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def format_money(value, devise="DZD"):
    try:
        value = float(value or 0)
    except (TypeError, ValueError):
        value = 0
    return f"{value:,.2f} {devise}".replace(",", " ").replace(".", ",")


def generate_patient_number(clinic_id, last_id):
    return f"PAT-{clinic_id:03d}-{(last_id or 0) + 1:05d}"


def html_to_text(html):
    """Convertit un contenu HTML simple (issu de l'éditeur riche) en texte brut pour le PDF."""
    import re
    if not html:
        return ""
    text = html
    text = re.sub(r'(?i)<br\s*/?>', '\n', text)
    text = re.sub(r'(?i)</p>', '\n\n', text)
    text = re.sub(r'(?i)</li>', '\n', text)
    text = re.sub(r'(?i)<li[^>]*>', '• ', text)
    text = re.sub(r'(?i)</h[1-6]>', '\n\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
    lines = [line.strip() for line in text.split('\n')]
    return '\n'.join(lines).strip()


def generate_invoice_number(clinic_id, last_id):
    return f"FAC-{clinic_id:03d}-{datetime.now().year}-{(last_id or 0) + 1:05d}"
