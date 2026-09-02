from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash

from app.db import query_db, execute_db
from app.utils.security import login_required, roles_required, validate_csrf, log_action, ROLES_LABELS

bp = Blueprint("users", __name__, url_prefix="/utilisateurs")


@bp.route("/")
@login_required
@roles_required("medecin", "gestionnaire")
def list_users():
    clinic_id = session["clinic_id"]
    utilisateurs = query_db(
        "SELECT * FROM users WHERE clinic_id = ? ORDER BY date_creation", (clinic_id,))
    return render_template("users/list.html", utilisateurs=utilisateurs, roles=ROLES_LABELS)


@bp.route("/nouveau", methods=["GET", "POST"])
@login_required
@roles_required("medecin", "gestionnaire")
def create_user():
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            flash("Session expirée, veuillez réessayer.", "error")
            return redirect(url_for("users.create_user"))

        f = request.form
        email = f.get("email", "").strip().lower()
        if query_db("SELECT id FROM users WHERE email = ?", (email,), one=True):
            flash("Un utilisateur existe déjà avec cette adresse e-mail.", "error")
            return render_template("users/form.html", utilisateur=f, roles=ROLES_LABELS, mode="create")

        if len(f.get("mot_de_passe", "")) < 8:
            flash("Le mot de passe doit contenir au moins 8 caractères.", "error")
            return render_template("users/form.html", utilisateur=f, roles=ROLES_LABELS, mode="create")

        execute_db(
            "INSERT INTO users (clinic_id, nom_complet, email, mot_de_passe_hash, role) VALUES (?,?,?,?,?)",
            (session["clinic_id"], f["nom_complet"], email, generate_password_hash(f["mot_de_passe"]), f["role"]),
        )
        log_action("creation_utilisateur", f"Utilisateur créé : {f['nom_complet']} ({f['role']})")
        flash("Utilisateur créé avec succès.", "success")
        return redirect(url_for("users.list_users"))

    return render_template("users/form.html", utilisateur={}, roles=ROLES_LABELS, mode="create")


@bp.route("/<int:user_id>/modifier", methods=["GET", "POST"])
@login_required
@roles_required("medecin", "gestionnaire")
def edit_user(user_id):
    clinic_id = session["clinic_id"]
    utilisateur = query_db("SELECT * FROM users WHERE id = ? AND clinic_id = ?", (user_id, clinic_id), one=True)
    if not utilisateur:
        flash("Utilisateur introuvable.", "error")
        return redirect(url_for("users.list_users"))

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            flash("Session expirée, veuillez réessayer.", "error")
            return redirect(url_for("users.edit_user", user_id=user_id))

        f = request.form
        if f.get("mot_de_passe"):
            execute_db("UPDATE users SET nom_complet=?, role=?, actif=?, mot_de_passe_hash=? WHERE id=? AND clinic_id=?",
                       (f["nom_complet"], f["role"], 1 if f.get("actif") == "on" else 0,
                        generate_password_hash(f["mot_de_passe"]), user_id, clinic_id))
        else:
            execute_db("UPDATE users SET nom_complet=?, role=?, actif=? WHERE id=? AND clinic_id=?",
                       (f["nom_complet"], f["role"], 1 if f.get("actif") == "on" else 0, user_id, clinic_id))
        log_action("modification_utilisateur", f"Utilisateur modifié : {f['nom_complet']}")
        flash("Utilisateur mis à jour.", "success")
        return redirect(url_for("users.list_users"))

    return render_template("users/form.html", utilisateur=utilisateur, roles=ROLES_LABELS, mode="edit")


@bp.route("/<int:user_id>/supprimer", methods=["POST"])
@login_required
@roles_required("medecin", "gestionnaire")
def delete_user(user_id):
    clinic_id = session["clinic_id"]
    if user_id == session["user_id"]:
        flash("Vous ne pouvez pas supprimer votre propre compte.", "error")
        return redirect(url_for("users.list_users"))
    if validate_csrf(request.form.get("csrf_token")):
        execute_db("DELETE FROM users WHERE id = ? AND clinic_id = ?", (user_id, clinic_id))
        log_action("suppression_utilisateur", f"Utilisateur #{user_id} supprimé")
        flash("Utilisateur supprimé.", "success")
    return redirect(url_for("users.list_users"))
