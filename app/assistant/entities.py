"""Extraction d'entités à partir du message du médecin.

Le nom du patient est mis en correspondance avec la base de données réelle
de la clinique (fuzzy matching), jamais deviné ou inventé.
"""
import re
import difflib

from app.db import query_db
from app.assistant import dates as date_utils

# Mots à ignorer lors de l'extraction du nom du patient (déclencheurs de commande)
_STOPWORDS = {
    "montre", "montre-moi", "affiche", "cherche", "recherche", "trouve", "find", "search",
    "for", "the", "show", "me", "ouvre", "ouvrir", "open", "le", "la", "les", "de", "du",
    "dossier", "fichier", "file", "planifie", "programme", "schedule", "book", "prends",
    "un", "rendez-vous", "rendez", "vous", "rdv", "appointment", "annule", "annuler",
    "cancel", "supprime", "deplace", "déplace", "reschedule", "move", "à", "a", "demain",
    "aujourd'hui", "aujourdhui", "today", "tomorrow", "hier", "yesterday", "à", "at",
    "patient", "patient's", "medical", "médical", "mes", "my", "et", "and", "avec", "with",
    "ملف", "افتح", "ابحث", "عن", "موعد", "احجز", "حدد", "غدا", "غداً", "اليوم", "مريض",
    "s", "'s",
}


def _clean_tokens(text):
    text = re.sub(r"[.,!?؟،]", " ", text)
    tokens = text.split()
    kept = []
    for tok in tokens:
        base = tok.strip("'’").lower()
        if base in _STOPWORDS:
            continue
        if date_utils.parse_date(tok) or date_utils.parse_time(tok):
            continue
        if re.fullmatch(r"\d{1,2}[:h.]\d{2}", tok) or re.fullmatch(r"\d{1,2}h", tok):
            continue
        kept.append(tok.strip("'’,.:;"))
    return kept


def extract_patient(message, clinic_id):
    """Retrouve le patient le plus probable dans la base de la clinique.

    Retourne (patient_row, confiance) ou (None, 0) si rien de probant.
    """
    candidates_tokens = _clean_tokens(message)
    if not candidates_tokens:
        return None, 0.0

    patients = query_db(
        "SELECT id, prenom, nom, telephone, sexe, date_naissance FROM patients WHERE clinic_id = ?",
        (clinic_id,),
    )
    if not patients:
        return None, 0.0

    best_row, best_score = None, 0.0
    guess = " ".join(candidates_tokens).lower()

    for p in patients:
        full_name = f"{p['prenom']} {p['nom']}".lower()
        first_only = p["prenom"].lower()
        last_only = p["nom"].lower()

        scores = [
            difflib.SequenceMatcher(None, guess, full_name).ratio(),
        ]
        # Comparaison mot-à-mot : un prénom ou nom isolé bien orthographié doit suffire
        for tok in candidates_tokens:
            tok_l = tok.lower()
            scores.append(difflib.SequenceMatcher(None, tok_l, first_only).ratio())
            scores.append(difflib.SequenceMatcher(None, tok_l, last_only).ratio())
        score = max(scores)
        if score > best_score:
            best_score, best_row = score, p

    threshold = 0.6
    if best_row and best_score >= threshold:
        return best_row, best_score
    return None, best_score


def extract_amount(message):
    m = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(dzd|da|€|eur)?\b", message, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            return None
    return None


def extract_quantity(message):
    m = re.search(r"\b(\d+)\b", message)
    return int(m.group(1)) if m else None


def extract_inventory_item(message, clinic_id):
    """Cherche un article de stock mentionné dans le message (fuzzy)."""
    items = query_db("SELECT id, nom, quantite FROM medicaments WHERE clinic_id = ?", (clinic_id,))
    if not items:
        return None, 0.0
    message_l = message.lower()
    best_row, best_score = None, 0.0
    for it in items:
        name_l = it["nom"].lower()
        if name_l in message_l:
            return it, 1.0
        score = difflib.SequenceMatcher(None, message_l, name_l).ratio()
        if score > best_score:
            best_score, best_row = score, it
    if best_row and best_score >= 0.5:
        return best_row, best_score
    return None, best_score
