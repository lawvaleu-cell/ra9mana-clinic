import secrets
from functools import wraps
from datetime import datetime

from flask import session, redirect, url_for, request, abort, flash, g

from app.db import get_db, execute_db

ROLES_LABELS = {
    "medecin": "Médecin",
    "receptionniste": "Réceptionniste",
    "assistant": "Assistant",
    "infirmier": "Infirmier(ère)",
    "comptable": "Comptable",
    "gestionnaire": "Gestionnaire",
}

# Rôles ayant accès complet (médecin = propriétaire du compte clinique)
ROLES_ADMIN = {"medecin", "gestionnaire"}


def generate_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def validate_csrf(token):
    return token and session.get("csrf_token") and secrets.compare_digest(token, session["csrf_token"])


def current_user():
    return getattr(g, "user", None)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("auth.login"))
            if session.get("role") not in roles and session.get("role") not in ROLES_ADMIN:
                flash("Vous n'avez pas la permission d'accéder à cette page.", "error")
                return redirect(url_for("dashboard.index"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def super_admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("super_admin_id"):
            return redirect(url_for("super_admin.login"))
        return view(*args, **kwargs)
    return wrapped


def log_action(action, details=""):
    """Enregistre une action dans le journal d'audit."""
    try:
        execute_db(
            "INSERT INTO audit_log (clinic_id, user_id, action, details, adresse_ip, date_creation) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                session.get("clinic_id"),
                session.get("user_id"),
                action,
                details,
                request.remote_addr,
                datetime.utcnow(),
            ),
        )
    except Exception:
        pass  # l'audit ne doit jamais casser une requête utilisateur


def create_notification(clinic_id, user_id, titre, message="", type_="info", priorite="normale", categorie="general"):
    execute_db(
        "INSERT INTO notifications (clinic_id, user_id, titre, message, type, priorite, categorie) VALUES (?,?,?,?,?,?,?)",
        (clinic_id, user_id, titre, message, type_, priorite, categorie),
    )


def notify_clinic(clinic_id, titre, message="", type_="info", priorite="normale", categorie="general"):
    """Envoie une notification à tous les utilisateurs actifs de la clinique."""
    try:
        users = query_db("SELECT id FROM users WHERE clinic_id = ? AND actif = 1", (clinic_id,))
        for u in users:
            create_notification(clinic_id, u["id"], titre, message, type_, priorite, categorie)
    except Exception:
        pass
