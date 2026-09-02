"""Détection de commandes de navigation en langage naturel
("ouvre-moi une ordonnance pour lui", "affiche la page des rapports"...).

Chaque cible correspond à une route Flask existante — l'assistant ne crée
aucune page, il ouvre simplement celles qui existent déjà.
"""
import re

_NAV_VERBS = [
    "ouvre", "ouvrir", "affiche", "montre-moi", "montre moi", "va à", "va sur", "aller à",
    "show me", "open", "go to", "take me to", "create", "crée", "créer",
    "افتح", "اذهب", "اعرض", "أنشئ", "انشاء", "انشئ",
]

# cible -> mots déclencheurs (le mot suffit, pas besoin du verbe pour les cibles
# qui n'ont pas d'intention concurrente déjà existante)
_STRONG_TARGETS = {
    "prescription": ["ordonnance", "prescription", "وصفة"],
    "lab_request": ["analyse", "analyses", "laboratoire", "lab test", "تحليل", "تحاليل"],
    "radio_request": ["radio", "imagerie", "أشعة", "راديو"],
    "invoice": ["facture", "factures", "invoice", "فاتورة", "فواتير"],
    "patient_file": ["dossier", "fichier patient", "ملف المريض", "ملفه", "ملفها"],
    "reports_page": ["rapport", "rapports", "report", "reports", "تقرير", "تقارير"],
}

# cibles qui partagent leur vocabulaire avec une intention "lecture" existante :
# on n'active la navigation que si un verbe de navigation + le mot "page" apparaissent.
_WEAK_TARGETS = {
    "inventory_page": ["stock", "inventaire", "inventory", "مخزون"],
    "appointments_page": ["calendrier", "agenda", "مواعيد", "rendez-vous", "rdv"],
    "expenses_page": ["dépense", "depense", "expenses", "مصاريف"],
    "settings_page": ["paramètres", "parametres", "réglages", "settings", "إعدادات"],
    "patients_page": ["liste des patients", "patients list", "قائمة المرضى"],
}

_PAGE_WORD = ["page", "صفحة", "onglet"]

_PRONOUN_REF = [
    "lui", "le patient", "her", "him", "the patient", "for him", "for her", "pour lui", "pour elle",
    "له", "لها", "لهذا المريض",
]


def detect_navigation(message):
    """Retourne une clé de cible de navigation, ou None."""
    if not message:
        return None
    low = message.lower()
    has_verb = any(v in low for v in _NAV_VERBS)

    for target, words in _STRONG_TARGETS.items():
        if any(w in low for w in words):
            return target

    if not has_verb:
        return None
    has_page_word = any(p in low for p in _PAGE_WORD)
    if not has_page_word:
        return None
    for target, words in _WEAK_TARGETS.items():
        if any(w in low for w in words):
            return target
    return None


def references_last_patient(message):
    low = message.lower()
    return any(p in low for p in _PRONOUN_REF)
