import os
import uuid
from flask import (Blueprint, render_template, request, redirect, url_for, session, flash,
                    send_from_directory, current_app, jsonify)

from app.db import query_db, execute_db
from app.utils.security import login_required, validate_csrf, log_action

bp = Blueprint("files", __name__, url_prefix="/fichiers")

CATEGORIES = {
    "laboratoire": "Résultats de laboratoire",
    "radiologie": "Imagerie / radiologie",
    "rapport_externe": "Rapport externe",
    "image": "Photo / image médicale",
    "administratif": "Document administratif",
    "autre": "Autre",
}

ALLOWED_EXT = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".txt",
}
PREVIEWABLE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf"}


def _patient_files_dir():
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], "patient_files")
    os.makedirs(path, exist_ok=True)
    return path


@bp.route("/patient/<int:patient_id>")
@login_required
def list_files(patient_id):
    clinic_id = session["clinic_id"]
    patient = query_db("SELECT * FROM patients WHERE id = ? AND clinic_id = ?", (patient_id, clinic_id), one=True)
    if not patient:
        flash("Patient introuvable.", "error")
        return redirect(url_for("patients.list_patients"))

    q = request.args.get("q", "").strip()
    categorie = request.args.get("categorie", "")
    where = "WHERE patient_id = ? AND clinic_id = ?"
    params = [patient_id, clinic_id]
    if q:
        where += " AND (titre LIKE ? OR description LIKE ? OR tags LIKE ? OR nom_fichier LIKE ?)"
        like = f"%{q}%"
        params += [like, like, like, like]
    if categorie:
        where += " AND categorie = ?"
        params.append(categorie)

    fichiers = query_db(f"SELECT * FROM pieces_jointes {where} ORDER BY date_ajout DESC", params)
    return render_template("files/list.html", patient=patient, fichiers=fichiers, categories=CATEGORIES,
                            previewable=PREVIEWABLE_EXT, q=q, categorie=categorie)


@bp.route("/patient/<int:patient_id>/televerser", methods=["POST"])
@login_required
def upload_files(patient_id):
    clinic_id = session["clinic_id"]
    patient = query_db("SELECT id FROM patients WHERE id = ? AND clinic_id = ?", (patient_id, clinic_id), one=True)
    if not patient:
        flash("Patient introuvable.", "error")
        return redirect(url_for("patients.list_patients"))
    if not validate_csrf(request.form.get("csrf_token")):
        flash("Session expirée, veuillez réessayer.", "error")
        return redirect(url_for("files.list_files", patient_id=patient_id))

    titre = request.form.get("titre", "").strip()
    description = request.form.get("description", "").strip()
    categorie = request.form.get("categorie", "autre")
    tags = request.form.get("tags", "").strip()

    uploaded = request.files.getlist("fichiers")
    if not uploaded or all(not f.filename for f in uploaded):
        flash("Veuillez sélectionner au moins un fichier.", "error")
        return redirect(url_for("files.list_files", patient_id=patient_id))

    count = 0
    for f in uploaded:
        if not f or not f.filename:
            continue
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in ALLOWED_EXT:
            continue
        stored_name = f"{uuid.uuid4().hex}{ext}"
        dest = os.path.join(_patient_files_dir(), stored_name)
        f.save(dest)
        taille = os.path.getsize(dest)
        execute_db(
            "INSERT INTO pieces_jointes (clinic_id, patient_id, nom_fichier, chemin_fichier, type_fichier, "
            "titre, description, categorie, tags, uploaded_by, taille_fichier) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (clinic_id, patient_id, f.filename, stored_name, ext.lstrip("."),
             titre or f.filename, description, categorie, tags, session["user_id"], taille),
        )
        count += 1

    if count:
        log_action("televersement_fichier", f"{count} fichier(s) ajouté(s) au patient #{patient_id}")
        flash(f"{count} fichier(s) ajouté(s) avec succès.", "success")
    else:
        flash("Aucun fichier valide n'a été téléversé (formats acceptés : images, PDF, Word, Excel, ZIP).", "error")

    return redirect(url_for("files.list_files", patient_id=patient_id))


@bp.route("/<int:file_id>/telecharger")
@login_required
def download_file(file_id):
    clinic_id = session["clinic_id"]
    fichier = query_db("SELECT * FROM pieces_jointes WHERE id = ? AND clinic_id = ?", (file_id, clinic_id), one=True)
    if not fichier:
        flash("Fichier introuvable.", "error")
        return redirect(url_for("patients.list_patients"))
    return send_from_directory(_patient_files_dir(), fichier["chemin_fichier"],
                                as_attachment=True, download_name=fichier["nom_fichier"])


@bp.route("/<int:file_id>/apercu")
@login_required
def preview_file(file_id):
    clinic_id = session["clinic_id"]
    fichier = query_db("SELECT * FROM pieces_jointes WHERE id = ? AND clinic_id = ?", (file_id, clinic_id), one=True)
    if not fichier:
        flash("Fichier introuvable.", "error")
        return redirect(url_for("patients.list_patients"))
    return send_from_directory(_patient_files_dir(), fichier["chemin_fichier"])


@bp.route("/<int:file_id>/renommer", methods=["POST"])
@login_required
def rename_file(file_id):
    clinic_id = session["clinic_id"]
    fichier = query_db("SELECT * FROM pieces_jointes WHERE id = ? AND clinic_id = ?", (file_id, clinic_id), one=True)
    if not fichier:
        return jsonify({"ok": False}), 404
    nouveau_titre = (request.get_json(silent=True) or request.form).get("titre", "").strip()
    if nouveau_titre:
        execute_db("UPDATE pieces_jointes SET titre = ? WHERE id = ?", (nouveau_titre, file_id))
        log_action("renommage_fichier", f"Fichier #{file_id} renommé")
        return jsonify({"ok": True, "titre": nouveau_titre})
    return jsonify({"ok": False}), 400


@bp.route("/<int:file_id>/supprimer", methods=["POST"])
@login_required
def delete_file(file_id):
    clinic_id = session["clinic_id"]
    fichier = query_db("SELECT * FROM pieces_jointes WHERE id = ? AND clinic_id = ?", (file_id, clinic_id), one=True)
    if fichier and validate_csrf(request.form.get("csrf_token")):
        try:
            os.remove(os.path.join(_patient_files_dir(), fichier["chemin_fichier"]))
        except OSError:
            pass
        execute_db("DELETE FROM pieces_jointes WHERE id = ?", (file_id,))
        log_action("suppression_fichier", f"Fichier #{file_id} supprimé")
        flash("Fichier supprimé.", "success")
        return redirect(url_for("files.list_files", patient_id=fichier["patient_id"]))
    flash("Fichier introuvable.", "error")
    return redirect(url_for("patients.list_patients"))
