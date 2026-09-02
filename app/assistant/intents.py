"""Détection d'intention par score de mots-clés pondérés.

Pipeline : message -> tokens normalisés (racines approximatives FR/EN/AR)
-> comparaison avec le vocabulaire de chaque intention (exacte ou floue)
-> somme des poids -> intention gagnante si le score dépasse un seuil.

Toujours déterministe, toujours local — aucun LLM. Les clés contenant un
espace sont comparées comme expression exacte dans le message brut (utile
pour lever l'ambiguïté entre deux intentions qui partagent une même racine,
ex: "remind me" pour créer un rappel vs "my reminders" pour les consulter).
"""
from app.assistant.nlp_utils import tokenize, normalize_token, fuzzy_match

# intent -> { mot_clé_ou_expression: poids }
INTENT_KEYWORDS = {
    "cancel_appointment": {
        "annule": 2.2, "annuler": 2.2, "cancel": 2.2, "supprim": 1.6, "delete": 1.4,
        "الغاء": 2.2, "إلغاء": 2.2, "الغ": 2.0,
        "rendez-vous": 0.6, "rdv": 0.6, "appointment": 0.6, "موعد": 0.6, "مواعيد": 0.4,
    },
    "reschedule_appointment": {
        "déplace": 2.2, "deplace": 2.2, "reprogramm": 2.2, "reschedul": 2.2, "move": 1.8,
        "غير": 1.4, "حرك": 1.8,
        "rendez-vous": 0.6, "rdv": 0.6, "appointment": 0.6, "موعد": 0.6,
    },
    "create_appointment": {
        "planifi": 2.0, "programm": 2.0, "schedul": 2.2, "book": 2.0, "prend": 1.2,
        "احجز": 2.2, "حدد": 1.8,
        "rendez-vous": 0.7, "rdv": 0.7, "appointment": 0.7, "موعد": 0.7,
    },
    "get_appointments": {
        "rendez-vous": 1.3, "rdv": 1.3, "appointment": 1.3, "مواعيد": 1.6, "موعد": 0.9,
    },
    "complete_reminder": {
        "termin": 1.8, "complet": 1.6, "done": 1.8, "fini": 1.6,
        "rappel": 0.3, "remind": 0.3, "تذكير": 0.3,
    },
    "delete_reminder": {
        "supprim": 1.8, "efface": 1.8, "delete": 1.8, "remove": 1.6,
        "rappel": 0.3, "remind": 0.3, "تذكير": 0.3,
    },
    "get_reminders": {
        "my reminders": 2.4, "show my reminders": 2.6, "show reminders": 2.2,
        "mes rappels": 2.4, "mes rappel": 2.2,
        "تذكيراتي": 2.6, "عرض تذكير": 2.0, "رأيت تذكير": 1.8,
    },
    "create_reminder": {
        "remind me": 2.6, "rappelle-moi": 2.6, "rappelle moi": 2.6,
        "create a reminder": 2.4, "crée un rappel": 2.4, "set a reminder": 2.2,
        "ذكرني": 2.6,
        "rappell": 1.2, "remind": 1.2, "ذكر": 1.4,
    },
    "get_profit": {
        "bénéfice": 2.0, "benefice": 2.0, "profit": 2.0, "ربح": 2.0, "أرباح": 2.0,
    },
    "get_revenue": {
        "revenu": 2.0, "recette": 1.8, "revenue": 2.0, "income": 1.8, "إيراد": 2.0, "ايرادات": 2.0,
        "chiffre": 1.4,
    },
    "get_expenses": {
        "dépense": 2.0, "depense": 2.0, "expense": 2.0, "مصروف": 2.0, "مصاريف": 2.0,
    },
    "add_inventory": {
        "ajout": 1.6, "add": 1.6, "أضف": 1.8,
        "stock": 0.7, "inventaire": 0.7, "inventory": 0.7, "مخزون": 0.7,
    },
    "update_inventory": {
        "modifi": 1.8, "update": 1.8, "met à jour": 1.8, "عدل": 1.8, "حدث": 1.8,
        "stock": 0.7, "inventaire": 0.7, "inventory": 0.7, "مخزون": 0.7,
    },
    "search_inventory": {
        "stock": 1.5, "inventaire": 1.5, "inventory": 1.5, "مخزون": 1.6, "combien": 1.0, "how many": 1.2,
    },
    "open_patient": {
        "ouvre": 1.6, "ouvrir": 1.6, "open": 1.6, "افتح": 1.8,
        "dossier": 1.0, "fichier": 0.8, "file": 1.0, "ملف": 1.0,
    },
    "add_patient": {
        "ajout": 1.4, "créer": 1.4, "create": 1.4, "add": 1.4, "new": 1.0, "أضف": 1.6,
        "patient": 0.9, "مريض": 0.9,
    },
    "search_patient": {
        "cherch": 1.6, "recherch": 1.6, "trouv": 1.6, "find": 1.6, "search": 1.6, "montre": 1.0,
        "ابحث": 1.8, "دور": 1.2,
    },
    "greeting": {
        "bonjour": 2.0, "salut": 1.8, "hello": 2.0, "hi": 1.6, "مرحبا": 2.0, "السلام": 1.8,
    },
    "help": {
        "aide": 1.8, "help": 1.8, "مساعدة": 1.8,
    },
}

_THRESHOLD = 1.1


def _score_intent(tokens, raw_lower, keywords):
    score = 0.0
    matched = 0
    for phrase, weight in keywords.items():
        if " " in phrase or "-" in phrase:
            if phrase in raw_lower:
                score += weight
                matched += 1
            continue
        phrase_norm = normalize_token(phrase)
        for tok in tokens:
            if not tok:
                continue
            if tok == phrase_norm:
                score += weight
                matched += 1
                break
            shorter, longer = (tok, phrase_norm) if len(tok) <= len(phrase_norm) else (phrase_norm, tok)
            if longer.startswith(shorter) and len(shorter) / len(longer) >= 0.75:
                score += weight
                matched += 1
                break
            ratio = fuzzy_match(tok, phrase_norm)
            if ratio:
                score += weight * 0.7
                matched += 1
                break
    return score, matched


def detect_intent(message):
    """Retourne le nom de l'intention détectée, ou 'unknown'."""
    if not message or not message.strip():
        return "unknown"
    tokens = tokenize(message)
    raw_lower = message.lower()
    if not tokens:
        return "unknown"

    best_intent, best_score, best_matched = "unknown", 0.0, 0
    for intent, keywords in INTENT_KEYWORDS.items():
        score, matched = _score_intent(tokens, raw_lower, keywords)
        if score > best_score or (score == best_score and matched > best_matched):
            best_intent, best_score, best_matched = intent, score, matched

    if best_score < _THRESHOLD:
        return "unknown"
    return best_intent
