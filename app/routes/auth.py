import secrets
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

from app.db import query_db, execute_db
from app.utils.security import validate_csrf, log_action, generate_csrf_token

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/inscription", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            flash("Session expirée, veuillez réessayer.", "error")
            return redirect(url_for("auth.register"))

        nom_clinique = request.form.get("nom_clinique", "").strip()
        nom_medecin = request.form.get("nom_medecin", "").strip()
        specialite = request.form.get("specialite", "").strip()
        email = request.form.get("email", "").strip().lower()
        mot_de_passe = request.form.get("mot_de_passe", "")
        confirmation = request.form.get("confirmation", "")

        errors = []
        if not nom_clinique or not nom_medecin:
            errors.append("Le nom de la clinique et du médecin sont obligatoires.")
        if "@" not in email or "." not in email:
            errors.append("Adresse e-mail invalide.")
        if len(mot_de_passe) < 8:
            errors.append("Le mot de passe doit contenir au moins 8 caractères.")
        if mot_de_passe != confirmation:
            errors.append("Les mots de passe ne correspondent pas.")
        if query_db("SELECT id FROM users WHERE email = ?", (email,), one=True):
            errors.append("Un compte existe déjà avec cette adresse e-mail.")

        if errors:
            for err in errors:
                flash(err, "error")
            return render_template("auth/register.html", form=request.form)

        clinic_id = execute_db(
            "INSERT INTO clinics (nom_clinique, nom_medecin, specialite, email, statut, plan, date_expiration_abonnement) "
            "VALUES (?, ?, ?, ?, 'essai', 'essai_gratuit', ?)",
            (nom_clinique, nom_medecin, specialite, email, (datetime.utcnow() + timedelta(days=14)).date()),
        )
        user_id = execute_db(
            "INSERT INTO users (clinic_id, nom_complet, email, mot_de_passe_hash, role) "
            "VALUES (?, ?, ?, ?, 'medecin')",
            (clinic_id, nom_medecin, email, generate_password_hash(mot_de_passe)),
        )
        execute_db(
            "INSERT INTO notifications (clinic_id, user_id, titre, message, type) VALUES (?, ?, ?, ?, ?)",
            (clinic_id, user_id, "Bienvenue sur RA9MANA Clinic !",
             "Votre période d'essai gratuite de 14 jours a commencé. Complétez le profil de votre clinique dans les paramètres.",
             "info"),
        )
        session.clear()
        session["user_id"] = user_id
        session["clinic_id"] = clinic_id
        session["role"] = "medecin"
        log_action("inscription", f"Nouvelle clinique créée : {nom_clinique}")
        flash("Compte créé avec succès ! Bienvenue sur RA9MANA Clinic.", "success")
        return redirect(url_for("dashboard.index"))

    return render_template("auth/register.html", form={})


@bp.route("/connexion", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            flash("Session expirée, veuillez réessayer.", "error")
            return redirect(url_for("auth.login"))

        email = request.form.get("email", "").strip().lower()
        mot_de_passe = request.form.get("mot_de_passe", "")
        se_souvenir = request.form.get("se_souvenir") == "on"

        user = query_db("SELECT * FROM users WHERE email = ?", (email,), one=True)
        succes = bool(user and user["actif"] and check_password_hash(user["mot_de_passe_hash"], mot_de_passe))

        execute_db(
            "INSERT INTO tentatives_connexion (email, succes, adresse_ip) VALUES (?, ?, ?)",
            (email, 1 if succes else 0, request.remote_addr),
        )

        if not succes:
            flash("E-mail ou mot de passe incorrect.", "error")
            return render_template("auth/login.html", email=email)

        clinic = query_db("SELECT * FROM clinics WHERE id = ?", (user["clinic_id"],), one=True)
        if clinic and clinic["statut"] == "suspendu":
            flash("Ce compte a été suspendu. Contactez le support pour plus d'informations.", "error")
            return render_template("auth/login.html", email=email)

        session.clear()
        session["user_id"] = user["id"]
        session["clinic_id"] = user["clinic_id"]
        session["role"] = user["role"]
        session.permanent = se_souvenir

        execute_db("UPDATE users SET derniere_connexion = ? WHERE id = ?", (datetime.utcnow(), user["id"]))
        log_action("connexion", "Connexion réussie")

        next_url = request.args.get("next")
        return redirect(next_url or url_for("dashboard.index"))

    return render_template("auth/login.html", email="")


@bp.route("/deconnexion")
def logout():
    log_action("deconnexion", "Déconnexion")
    session.clear()
    flash("Vous avez été déconnecté avec succès.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/mot-de-passe-oublie", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            flash("Session expirée, veuillez réessayer.", "error")
            return redirect(url_for("auth.forgot_password"))

        email = request.form.get("email", "").strip().lower()
        user = query_db("SELECT * FROM users WHERE email = ?", (email,), one=True)
        if user:
            token = secrets.token_urlsafe(32)
            execute_db(
                "INSERT INTO password_resets (user_id, token, expire_at) VALUES (?, ?, ?)",
                (user["id"], token, datetime.utcnow() + timedelta(hours=1)),
            )
            reset_link = url_for("auth.reset_password", token=token, _external=True)
            # Aucun serveur e-mail configuré dans cet environnement : le lien est affiché
            # directement (mode démo/local). En production, il serait envoyé par e-mail.
            flash(f"Lien de réinitialisation généré (valable 1h) : {reset_link}", "info")
        else:
            flash("Si cette adresse existe, un lien de réinitialisation a été généré.", "info")
        return redirect(url_for("auth.forgot_password"))

    return render_template("auth/forgot_password.html")


@bp.route("/reinitialiser-mot-de-passe/<token>", methods=["GET", "POST"])
def reset_password(token):
    reset = query_db("SELECT * FROM password_resets WHERE token = ? AND utilise = 0", (token,), one=True)
    valide = bool(reset) and datetime.fromisoformat(str(reset["expire_at"])) > datetime.utcnow()

    if not valide:
        flash("Ce lien de réinitialisation est invalide ou a expiré.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            flash("Session expirée, veuillez réessayer.", "error")
            return redirect(request.path)

        mot_de_passe = request.form.get("mot_de_passe", "")
        confirmation = request.form.get("confirmation", "")
        if len(mot_de_passe) < 8:
            flash("Le mot de passe doit contenir au moins 8 caractères.", "error")
            return render_template("auth/reset_password.html", token=token)
        if mot_de_passe != confirmation:
            flash("Les mots de passe ne correspondent pas.", "error")
            return render_template("auth/reset_password.html", token=token)

        execute_db("UPDATE users SET mot_de_passe_hash = ? WHERE id = ?",
                   (generate_password_hash(mot_de_passe), reset["user_id"]))
        execute_db("UPDATE password_resets SET utilise = 1 WHERE id = ?", (reset["id"],))
        flash("Mot de passe réinitialisé avec succès. Vous pouvez vous connecter.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", token=token)
