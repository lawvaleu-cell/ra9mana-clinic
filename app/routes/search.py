from flask import Blueprint, render_template, request, session, jsonify

from app.db import query_db
from app.utils.security import login_required

bp = Blueprint("search", __name__, url_prefix="/recherche")


@bp.route("/")
@login_required
def search_page():
    q = request.args.get("q", "").strip()
    results = _run_search(q) if q else {}
    return render_template("search_results.html", q=q, results=results)


@bp.route("/api")
@login_required
def search_api():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"results": {}})
    return jsonify({"results": _run_search(q, limit=5)})


def _run_search(q, limit=20):
    clinic_id = session["clinic_id"]
    like = f"%{q}%"

    patients = query_db(
        "SELECT id, prenom, nom, telephone, numero_patient FROM patients "
        "WHERE clinic_id = ? AND (prenom LIKE ? OR nom LIKE ? OR telephone LIKE ? OR numero_patient LIKE ?) "
        f"LIMIT {limit}", (clinic_id, like, like, like, like))

    medicaments = query_db(
        f"SELECT id, nom, quantite FROM medicaments WHERE clinic_id = ? AND nom LIKE ? LIMIT {limit}",
        (clinic_id, like))

    factures = query_db(
        "SELECT f.id, f.numero_facture, f.montant_total, p.prenom, p.nom FROM factures f "
        "JOIN patients p ON p.id = f.patient_id "
        f"WHERE f.clinic_id = ? AND f.numero_facture LIKE ? LIMIT {limit}", (clinic_id, like))

    rdvs = query_db(
        "SELECT r.id, r.date_rdv, r.heure_rdv, p.prenom, p.nom FROM rendez_vous r "
        "JOIN patients p ON p.id = r.patient_id "
        f"WHERE r.clinic_id = ? AND (p.prenom LIKE ? OR p.nom LIKE ?) LIMIT {limit}",
        (clinic_id, like, like))

    prescriptions = query_db(
        "SELECT pr.id, pr.date_prescription, p.prenom, p.nom FROM prescriptions pr "
        "JOIN patients p ON p.id = pr.patient_id "
        f"WHERE pr.clinic_id = ? AND (p.prenom LIKE ? OR p.nom LIKE ?) LIMIT {limit}",
        (clinic_id, like, like))

    return {
        "patients": [dict(r) for r in patients],
        "medicaments": [dict(r) for r in medicaments],
        "factures": [dict(r) for r in factures],
        "rendez_vous": [dict(r) for r in rdvs],
        "prescriptions": [dict(r) for r in prescriptions],
    }
