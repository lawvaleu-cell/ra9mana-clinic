"""Analyse de dates et heures en langage naturel (FR / EN / AR).

Aucune IA ici : uniquement des mots-clés et des expressions régulières.
Toute date ambiguë renvoie None plutôt que d'être devinée.
"""
import re
from datetime import date, timedelta

_WEEKDAY_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
_WEEKDAY_EN = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _next_weekday(today, target_index):
    days_ahead = (target_index - today.weekday()) % 7
    days_ahead = days_ahead or 7
    return today + timedelta(days=days_ahead)


def parse_date(text, today=None):
    """Retourne un objet date() ou None si aucune date claire n'est trouvée."""
    if not text:
        return None
    today = today or date.today()
    t = text.lower().strip()

    # Formats explicites
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", t)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", t)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None

    # Aujourd'hui / demain / hier — FR, EN, AR
    if any(k in t for k in ["aujourd'hui", "aujourdhui", "today", "اليوم"]):
        return today
    if any(k in t for k in ["demain", "tomorrow", "غدا", "غداً", "غدًا"]):
        return today + timedelta(days=1)
    if any(k in t for k in ["hier", "yesterday", "أمس", "امس"]):
        return today - timedelta(days=1)
    if any(k in t for k in ["après-demain", "apres-demain", "day after tomorrow", "بعد غد"]):
        return today + timedelta(days=2)

    # Jours de la semaine
    for i, name in enumerate(_WEEKDAY_FR):
        if name in t:
            return _next_weekday(today, i)
    for i, name in enumerate(_WEEKDAY_EN):
        if name in t:
            return _next_weekday(today, i)

    return None


def parse_period(text):
    """Retourne (debut, fin, libellé) pour une période nommée, ou None."""
    if not text:
        return None
    t = text.lower().strip()
    today = date.today()

    if any(k in t for k in ["cette semaine", "this week", "هذا الأسبوع", "هذا الاسبوع"]):
        debut = today - timedelta(days=today.weekday())
        return debut, debut + timedelta(days=6), "cette semaine"
    if any(k in t for k in ["semaine prochaine", "semaine dernière" "next week", "الأسبوع القادم", "الاسبوع القادم"]):
        debut = today - timedelta(days=today.weekday()) + timedelta(days=7)
        return debut, debut + timedelta(days=6), "la semaine prochaine"
    if any(k in t for k in ["ce mois", "this month", "هذا الشهر"]):
        debut = today.replace(day=1)
        fin = (debut.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        return debut, fin, "ce mois-ci"
    if any(k in t for k in ["mois prochain", "next month", "الشهر القادم"]):
        first_this = today.replace(day=1)
        debut = (first_this.replace(day=28) + timedelta(days=4)).replace(day=1)
        fin = (debut.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        return debut, fin, "le mois prochain"
    return None


def parse_time(text):
    """Retourne une heure normalisée 'HH:MM' ou None."""
    if not text:
        return None
    t = text.lower().strip()
    m = re.search(r"\b(\d{1,2})[:h.](\d{2})\b", t)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mn <= 59:
            return f"{h:02d}:{mn:02d}"
    m = re.search(r"\b(\d{1,2})\s*h\b", t)
    if m:
        h = int(m.group(1))
        if 0 <= h <= 23:
            return f"{h:02d}:00"
    return None
