"""Contexte de conversation — mémoire courte, uniquement pendant la session.

Ne remplace jamais la base de données : ne sert qu'à retenir "de qui/quoi
on parlait" pour comprendre les phrases de suivi (ex: "annule-le").
"""
from flask import session

_KEY = "assistant_context"

_DEFAULT = {
    "last_patient_id": None,
    "last_patient_name": None,
    "last_date": None,
    "last_appointments": [],
    "pending_action": None,
    "pending_entities": {},
    "pending_confirm": None,
}


def get_context():
    ctx = session.get(_KEY)
    if not ctx:
        ctx = dict(_DEFAULT)
    return ctx


def save_context(ctx):
    session[_KEY] = ctx


def reset_context():
    session[_KEY] = dict(_DEFAULT)


def set_pending(ctx, action, entities):
    ctx["pending_action"] = action
    ctx["pending_entities"] = entities
    save_context(ctx)


def clear_pending(ctx):
    ctx["pending_action"] = None
    ctx["pending_entities"] = {}
    save_context(ctx)
