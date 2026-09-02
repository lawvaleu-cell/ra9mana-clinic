import json
import io
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file

from app.db import query_db, execute_db, get_db
from app.utils.security import login_required, roles_required, validate_csrf, log_action

bp = Blueprint("backup", __name__, url_prefix="/sauvegarde")

TABLES_CLINIQUE = [
    "patients", "consultations", "rendez_vous", "prescriptions", "prescription_lignes",
    "medicaments_favoris", "demandes_laboratoire", "demandes_radiologie", "medicaments",
    "factures", "facture_lignes", "depenses",
]


@bp.route("/")
@login_required
@roles_required("medecin", "gestionnaire")
def backup_page():
    clinic_id = session["clinic_id"]
    counts = {t: query_db(f"SELECT COUNT(*) c FROM {t} WHERE clinic_id = ?", (clinic_id,), one=True)["c"]
              for t in TABLES_CLINIQUE if t not in ("prescription_lignes", "facture_lignes")}
    return render_template("backup.html", counts=counts)


@bp.route("/exporter")
@login_required
@roles_required("medecin", "gestionnaire")
def export_backup():
    clinic_id = session["clinic_id"]
    data = {"exporte_le": datetime.utcnow().isoformat(), "clinic_id": clinic_id, "tables": {}}

    for table in TABLES_CLINIQUE:
        if table in ("prescription_lignes", "facture_lignes"):
            continue
        rows = query_db(f"SELECT * FROM {table} WHERE clinic_id = ?", (clinic_id,))
        data["tables"][table] = [dict(r) for r in rows]

    # Sous-tables liées via clé étrangère (sans clinic_id direct)
    presc_ids = [p["id"] for p in data["tables"].get("prescriptions", [])]
    if presc_ids:
        placeholders = ",".join("?" * len(presc_ids))
        lignes = query_db(f"SELECT * FROM prescription_lignes WHERE prescription_id IN ({placeholders})", presc_ids)
        data["tables"]["prescription_lignes"] = [dict(r) for r in lignes]

    fact_ids = [f["id"] for f in data["tables"].get("factures", [])]
    if fact_ids:
        placeholders = ",".join("?" * len(fact_ids))
        lignes = query_db(f"SELECT * FROM facture_lignes WHERE facture_id IN ({placeholders})", fact_ids)
        data["tables"]["facture_lignes"] = [dict(r) for r in lignes]

    buf = io.BytesIO(json.dumps(data, ensure_ascii=False, indent=2, default=str).encode("utf-8"))
    log_action("export_sauvegarde", "Sauvegarde des données exportée")
    return send_file(buf, mimetype="application/json", as_attachment=True,
                      download_name=f"sauvegarde_cliniq_{datetime.now().strftime('%Y%m%d_%H%M')}.json")


@bp.route("/restaurer", methods=["POST"])
@login_required
@roles_required("medecin", "gestionnaire")
def restore_backup():
    if not validate_csrf(request.form.get("csrf_token")):
        flash("Session expirée, veuillez réessayer.", "error")
        return redirect(url_for("backup.backup_page"))

    fichier = request.files.get("fichier_sauvegarde")
    if not fichier or not fichier.filename.endswith(".json"):
        flash("Veuillez sélectionner un fichier de sauvegarde valide (.json).", "error")
        return redirect(url_for("backup.backup_page"))

    try:
        data = json.loads(fichier.read().decode("utf-8"))
    except Exception:
        flash("Fichier de sauvegarde invalide ou corrompu.", "error")
        return redirect(url_for("backup.backup_page"))

    clinic_id = session["clinic_id"]
    db = get_db()
    try:
        # Supprime les données actuelles de la clinique (cascade sur les sous-tables)
        for table in ["prescriptions", "factures", "patients", "medicaments", "depenses",
                      "demandes_laboratoire", "demandes_radiologie", "rendez_vous", "consultations"]:
            db.execute(f"DELETE FROM {table} WHERE clinic_id = ?", (clinic_id,))

        tables = data.get("tables", {})
        for row in tables.get("patients", []):
            row["clinic_id"] = clinic_id
            cols = ", ".join(row.keys())
            qs = ", ".join("?" * len(row))
            db.execute(f"INSERT INTO patients ({cols}) VALUES ({qs})", list(row.values()))

        for table in ["medicaments", "depenses"]:
            for row in tables.get(table, []):
                row["clinic_id"] = clinic_id
                cols = ", ".join(row.keys())
                qs = ", ".join("?" * len(row))
                db.execute(f"INSERT INTO {table} ({cols}) VALUES ({qs})", list(row.values()))

        db.commit()
        log_action("restauration_sauvegarde", "Données restaurées depuis une sauvegarde (patients, inventaire, dépenses)")
        flash("Restauration effectuée avec succès (patients, inventaire et dépenses).", "success")
    except Exception as e:
        db.rollback()
        flash(f"Erreur lors de la restauration : {e}", "error")

    return redirect(url_for("backup.backup_page"))
