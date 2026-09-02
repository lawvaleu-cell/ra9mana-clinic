import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, jsonify

from app.db import query_db, execute_db
from app.utils.security import login_required, roles_required, validate_csrf, log_action
from app.utils.background_removal import remove_background

bp = Blueprint("settings", __name__, url_prefix="/parametres")

THEMES = {
    "light": "Clair",
    "dark": "Sombre",
    "blue": "Bleu Médical",
    "emerald": "Émeraude",
}

TEMPLATE_STYLES = {
    "classique": "Classique — bandeau bleu médical",
    "moderne": "Moderne — minimaliste, lignes fines",
    "audacieux": "Audacieux — en-tête large et coloré",
    "serein": "Serein — élégant, couleurs douces et apaisées",
    "vague": "Vague Turquoise — courbe organique premium",
}

ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}


def _save_upload(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXT:
        return None
    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    file_storage.save(path)

    # Suppression automatique du fond (fonctionne pour les fonds unis / blancs)
    cleaned_filename = f"{uuid.uuid4().hex}_transparent.png"
    cleaned_path = os.path.join(current_app.config["UPLOAD_FOLDER"], cleaned_filename)
    try:
        if remove_background(path, cleaned_path):
            return cleaned_path
    except Exception:
        pass
    return path


@bp.route("/", methods=["GET", "POST"])
@login_required
@roles_required("medecin", "gestionnaire")
def clinic_profile():
    clinic_id = session["clinic_id"]

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            flash("Session expirée, veuillez réessayer.", "error")
            return redirect(url_for("settings.clinic_profile"))

        f = request.form
        updates = {
            "nom_clinique": f.get("nom_clinique"),
            "nom_medecin": f.get("nom_medecin"),
            "specialite": f.get("specialite"),
            "adresse": f.get("adresse"),
            "telephone": f.get("telephone"),
            "email": f.get("email"),
            "site_web": f.get("site_web"),
            "numero_fiscal": f.get("numero_fiscal"),
            "heures_travail": f.get("heures_travail"),
            "devise": f.get("devise") or "DZD",
            "fuseau_horaire": f.get("fuseau_horaire") or "Africa/Algiers",
            "format_papier": f.get("format_papier") or "A4",
            "seuil_stock_bas": f.get("seuil_stock_bas") or 10,
            "documents_template": f.get("documents_template") or "classique",
            "ecran_theme": f.get("ecran_theme") or "sombre",
            "carte_bio": f.get("carte_bio", ""),
            "carte_langues": f.get("carte_langues", ""),
        }
        for champ in ("nom_clinique", "nom_medecin", "specialite", "adresse", "pied_de_page", "description"):
            for langue in ("ar", "en"):
                key = f"{champ}_{langue}"
                updates[key] = f.get(key, "")

        logo_path = _save_upload(request.files.get("logo"))
        signature_path = _save_upload(request.files.get("signature"))
        cachet_path = _save_upload(request.files.get("cachet"))
        carte_photo_path = _save_upload(request.files.get("carte_photo"))

        set_clauses = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values())
        if logo_path:
            set_clauses += ", logo_path = ?"
            params.append(logo_path)
        if signature_path:
            set_clauses += ", signature_path = ?"
            params.append(signature_path)
        if cachet_path:
            set_clauses += ", cachet_path = ?"
            params.append(cachet_path)
        if carte_photo_path:
            set_clauses += ", carte_photo_path = ?"
            params.append(carte_photo_path)
        params.append(clinic_id)

        execute_db(f"UPDATE clinics SET {set_clauses} WHERE id = ?", params)
        log_action("modification_parametres", "Profil de la clinique mis à jour")
        flash("Paramètres de la clinique mis à jour avec succès.", "success")
        return redirect(url_for("settings.clinic_profile"))

    clinic = query_db("SELECT * FROM clinics WHERE id = ?", (clinic_id,), one=True)
    return render_template("settings.html", clinic=clinic, themes=THEMES, template_styles=TEMPLATE_STYLES)


@bp.route("/theme", methods=["POST"])
@login_required
def change_theme():
    theme = request.form.get("theme") or (request.get_json(silent=True) or {}).get("theme")
    if theme not in THEMES:
        return jsonify({"ok": False}), 400
    execute_db("UPDATE clinics SET theme = ? WHERE id = ?", (theme, session["clinic_id"]))
    if request.is_json:
        return jsonify({"ok": True, "theme": theme})
    flash("Thème mis à jour.", "success")
    return redirect(request.referrer or url_for("dashboard.index"))
