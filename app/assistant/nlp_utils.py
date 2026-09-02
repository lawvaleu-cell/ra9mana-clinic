"""Utilitaires NLP de base : tokenisation, normalisation légère et
comparaison approximative. Tout est déterministe — aucun modèle, aucun
appel externe. C'est un classifieur par mots-clés pondérés avec tolérance
aux fautes de frappe et aux variations grammaticales simples (pluriels,
suffixes possessifs arabes, etc.).
"""
import re
import difflib

_ARABIC_PREFIXES = ["وال", "بال", "كال", "فال", "ال", "و", "ف", "ب", "ل"]
_ARABIC_SUFFIXES = ["هما", "كما", "هم", "هن", "كم", "كن", "ها", "ني", "نا", "ي", "ك", "ه"]

_FR_EN_SUFFIXES = ["ations", "ation", "ements", "ement", "eries", "erie", "ing", "es", "s"]


def _strip_arabic_affixes(tok):
    if not re.search(r"[\u0600-\u06FF]", tok):
        return tok
    changed = True
    while changed and len(tok) > 3:
        changed = False
        for suf in _ARABIC_SUFFIXES:
            if tok.endswith(suf) and len(tok) - len(suf) >= 3:
                tok = tok[: -len(suf)]
                changed = True
                break
    for pre in _ARABIC_PREFIXES:
        if tok.startswith(pre) and len(tok) - len(pre) >= 3:
            tok = tok[len(pre):]
            break
    return tok


def _strip_latin_suffix(tok):
    if re.search(r"[\u0600-\u06FF]", tok) or "-" in tok or len(tok) <= 4:
        return tok
    for suf in _FR_EN_SUFFIXES:
        if tok.endswith(suf) and len(tok) - len(suf) >= 3:
            return tok[: -len(suf)]
    return tok


def normalize_token(tok):
    """Ramène un mot à une forme approximative de sa racine (léger stemming)."""
    tok = tok.strip("'’.,!?؟،:;()[]").lower()
    if not tok:
        return tok
    tok = _strip_arabic_affixes(tok)
    tok = _strip_latin_suffix(tok)
    return tok


def tokenize(text):
    """Découpe un message en tokens normalisés (mots pleins seulement)."""
    if not text:
        return []
    raw = re.findall(r"[\w'\u0600-\u06FF-]+", text.lower(), flags=re.UNICODE)
    return [normalize_token(t) for t in raw if t]


def fuzzy_match(token, vocab_word, cutoff=0.82):
    """Compare deux mots avec tolérance aux fautes de frappe légères."""
    if token == vocab_word:
        return 1.0
    if len(token) < 3 or len(vocab_word) < 3:
        return 0.0
    ratio = difflib.SequenceMatcher(None, token, vocab_word).ratio()
    return ratio if ratio >= cutoff else 0.0
