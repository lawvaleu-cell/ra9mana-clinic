import os
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file, send_from_directory, current_app, g

from app.db import query_db, execute_db
from app.utils.security import login_required, validate_csrf, log_action
from app.utils.helpers import calculate_age, format_datetime_fr, html_to_text
from app.utils.pdf_generator import generate_custom_document_pdf

bp = Blueprint("documents", __name__, url_prefix="/documents")

TYPES_DOCUMENT = {
    "rapport_medical": "Rapport médical",
    "lettre_orientation": "Lettre d'orientation",
    "certificat": "Certificat médical",
    "recommandation": "Recommandation médicale",
    "lettre_administrative": "Lettre administrative",
    "communication_medecin": "Communication avec un confrère",
    "instructions_patient": "Instructions au patient",
    "notes_libres": "Notes médicales libres",
    "autre": "Autre document",
}


def _clinic_dict():
    return dict(g.clinic) if g.clinic else {}


def _style():
    return (g.clinic["documents_template"] if g.clinic and "documents_template" in g.clinic.keys() else None) or "classique"


def _taille():
    t = request.args.get("taille", "A4").upper()
    return t if t in ("A4", "A5") else "A4"


@bp.route("/uploads/<path:filename>")
def serve_upload(filename):
    """Sert les fichiers uploadés (logo/signature/cachet) pour les documents imprimables."""
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@bp.route("/nouveau/<int:patient_id>", methods=["GET", "POST"])
@login_required
def create_document(patient_id):
    clinic_id = session["clinic_id"]
    patient = query_db("SELECT * FROM patients WHERE id = ? AND clinic_id = ?", (patient_id, clinic_id), one=True)
    if not patient:
        flash("Patient introuvable.", "error")
        return redirect(url_for("patients.list_patients"))

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            flash("Session expirée, veuillez réessayer.", "error")
            return redirect(request.path)

        f = request.form
        titre = f.get("titre", "").strip()
        contenu = f.get("contenu", "").strip()
        type_document = f.get("type_document", "autre")
        if not titre or not contenu:
            flash("Le titre et le contenu du document sont obligatoires.", "error")
            return render_template("documents/form.html", patient=patient, types=TYPES_DOCUMENT, form=f)

        doc_id = execute_db(
            "INSERT INTO documents_personnalises (clinic_id, patient_id, medecin_id, type_document, titre, contenu) "
            "VALUES (?,?,?,?,?,?)",
            (clinic_id, patient_id, session["user_id"], type_document, titre, contenu),
        )
        log_action("creation_document", f"Document « {titre} » créé pour le patient #{patient_id}")
        flash("Document créé avec succès.", "success")
        return redirect(url_for("documents.view_document", document_id=doc_id))

    return render_template("documents/form.html", patient=patient, types=TYPES_DOCUMENT, form={})


def _document_context(document_id, clinic_id):
    doc = query_db(
        "SELECT d.*, p.prenom, p.nom, p.numero_patient, p.date_naissance, p.id as patient_id FROM documents_personnalises d "
        "JOIN patients p ON p.id = d.patient_id WHERE d.id = ? AND d.clinic_id = ?",
        (document_id, clinic_id), one=True)
    if not doc:
        return None, None, None
    patient = {"prenom": doc["prenom"], "nom": doc["nom"], "numero_patient": doc["numero_patient"],
               "id": doc["patient_id"]}
    age = calculate_age(doc["date_naissance"])
    d = dict(doc)
    d["date_str"] = format_datetime_fr(doc["date_creation"])
    d["type_label"] = TYPES_DOCUMENT.get(doc["type_document"], "Document médical")
    return d, patient, age


@bp.route("/<int:document_id>")
@login_required
def view_document(document_id):
    d, patient, age = _document_context(document_id, session["clinic_id"])
    if not d:
        flash("Document introuvable.", "error")
        return redirect(url_for("patients.list_patients"))
    return render_template("documents/detail.html", document=d, patient=patient)


@bp.route("/<int:document_id>/imprimer")
@login_required
def print_document(document_id):
    d, patient, age = _document_context(document_id, session["clinic_id"])
    if not d:
        flash("Document introuvable.", "error")
        return redirect(url_for("patients.list_patients"))
    return render_template("documents/custom_print.html", clinic=_clinic_dict(), patient=patient, document=d,
                            age=age, style=_style(), taille=_taille(), date_str=d["date_str"])


@bp.route("/<int:document_id>/pdf")
@login_required
def download_document_pdf(document_id):
    d, patient, age = _document_context(document_id, session["clinic_id"])
    if not d:
        flash("Document introuvable.", "error")
        return redirect(url_for("patients.list_patients"))
    buf = generate_custom_document_pdf(_clinic_dict(), patient, {**d, "contenu": html_to_text(d.get("contenu"))},
                                        age, _style(), _taille())
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name=f"document_{document_id}.pdf")


@bp.route("/<int:document_id>/supprimer", methods=["POST"])
@login_required
def delete_document(document_id):
    clinic_id = session["clinic_id"]
    if validate_csrf(request.form.get("csrf_token")):
        doc = query_db("SELECT patient_id FROM documents_personnalises WHERE id = ? AND clinic_id = ?",
                       (document_id, clinic_id), one=True)
        if doc:
            execute_db("DELETE FROM documents_personnalises WHERE id = ? AND clinic_id = ?", (document_id, clinic_id))
            log_action("suppression_document", f"Document #{document_id} supprimé")
            flash("Document supprimé.", "success")
            return redirect(url_for("patients.view_patient", patient_id=doc["patient_id"]))
    return redirect(url_for("patients.list_patients"))
