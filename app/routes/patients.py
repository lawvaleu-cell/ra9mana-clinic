from datetime import date, timedelta, datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from app.db import query_db, execute_db
from app.utils.security import login_required, validate_csrf, log_action
from app.utils.helpers import generate_patient_number, format_date_fr

bp = Blueprint("patients", __name__, url_prefix="/patients")

PAGE_SIZE = 15


@bp.route("/")
@login_required
def list_patients():
    clinic_id = session["clinic_id"]
    q = request.args.get("q", "").strip()
    page = max(1, request.args.get("page", 1, type=int))

    where = "WHERE clinic_id = ?"
    params = [clinic_id]
    if q:
        where += " AND (prenom LIKE ? OR nom LIKE ? OR telephone LIKE ? OR numero_patient LIKE ? OR maladies_chroniques LIKE ?)"
        like = f"%{q}%"
        params += [like, like, like, like, like]

    total = query_db(f"SELECT COUNT(*) c FROM patients {where}", params, one=True)["c"]
    offset = (page - 1) * PAGE_SIZE
    patients = query_db(
        f"SELECT * FROM patients {where} ORDER BY date_inscription DESC LIMIT ? OFFSET ?",
        params + [PAGE_SIZE, offset]
    )
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    return render_template("patients/list.html", patients=patients, q=q, page=page,
                            total_pages=total_pages, total=total)


@bp.route("/nouveau", methods=["GET", "POST"])
@login_required
def create_patient():
    clinic_id = session["clinic_id"]
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            flash("Session expirée, veuillez réessayer.", "error")
            return redirect(url_for("patients.create_patient"))

        f = request.form
        if not f.get("prenom") or not f.get("nom"):
            flash("Le prénom et le nom sont obligatoires.", "error")
            return render_template("patients/form.html", patient=f, mode="create")

        last = query_db("SELECT COUNT(*) c FROM patients WHERE clinic_id = ?", (clinic_id,), one=True)["c"]
        numero = generate_patient_number(clinic_id, last)

        patient_id = execute_db(
            "INSERT INTO patients (clinic_id, numero_patient, prenom, nom, sexe, date_naissance, groupe_sanguin, "
            "telephone, email, adresse, contact_urgence, allergies, maladies_chroniques, notes_medicales, assurance) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (clinic_id, numero, f["prenom"], f["nom"], f.get("sexe"), f.get("date_naissance") or None,
             f.get("groupe_sanguin"), f.get("telephone"), f.get("email"), f.get("adresse"),
             f.get("contact_urgence"), f.get("allergies"), f.get("maladies_chroniques"),
             f.get("notes_medicales"), f.get("assurance")),
        )
        log_action("creation_patient", f"Patient créé : {f['prenom']} {f['nom']} ({numero})")
        flash("Patient enregistré avec succès.", "success")
        return redirect(url_for("patients.view_patient", patient_id=patient_id))

    return render_template("patients/form.html", patient={}, mode="create")


@bp.route("/<int:patient_id>")
@login_required
def view_patient(patient_id):
    clinic_id = session["clinic_id"]
    patient = query_db("SELECT * FROM patients WHERE id = ? AND clinic_id = ?", (patient_id, clinic_id), one=True)
    if not patient:
        flash("Patient introuvable.", "error")
        return redirect(url_for("patients.list_patients"))

    consultations = query_db(
        "SELECT c.*, u.nom_complet AS medecin_nom FROM consultations c LEFT JOIN users u ON u.id = c.medecin_id "
        "WHERE c.patient_id = ? ORDER BY c.date_consultation DESC", (patient_id,))
    prescriptions = query_db(
        "SELECT * FROM prescriptions WHERE patient_id = ? ORDER BY date_prescription DESC", (patient_id,))
    rdvs = query_db(
        "SELECT * FROM rendez_vous WHERE patient_id = ? ORDER BY date_rdv DESC, heure_rdv DESC LIMIT 10", (patient_id,))
    factures = query_db(
        "SELECT * FROM factures WHERE patient_id = ? ORDER BY date_facture DESC", (patient_id,))
    labo = query_db("SELECT * FROM demandes_laboratoire WHERE patient_id = ? ORDER BY date_creation DESC", (patient_id,))
    radio = query_db("SELECT * FROM demandes_radiologie WHERE patient_id = ? ORDER BY date_creation DESC", (patient_id,))
    documents = query_db("SELECT * FROM documents_personnalises WHERE patient_id = ? ORDER BY date_creation DESC", (patient_id,))
    pieces = query_db("SELECT * FROM pieces_jointes WHERE patient_id = ? ORDER BY date_ajout DESC", (patient_id,))

    derniere_consultation = consultations[0] if consultations else None
    derniere_prescription = None
    derniere_prescription_lignes = []
    if prescriptions:
        derniere_prescription = prescriptions[0]
        derniere_prescription_lignes = query_db(
            "SELECT medicament FROM prescription_lignes WHERE prescription_id = ?", (derniere_prescription["id"],))
    resume_patient = {
        "derniere_consultation": derniere_consultation,
        "derniere_prescription_lignes": [l["medicament"] for l in derniere_prescription_lignes],
        "nb_consultations": len(consultations),
        "nb_documents": len(prescriptions) + len(labo) + len(radio) + len(documents),
    }

    # Fusion en timeline chronologique
    timeline = []
    for c in consultations:
        timeline.append({"type": "consultation", "date": c["date_consultation"], "data": c})
    for p in prescriptions:
        timeline.append({"type": "prescription", "date": p["date_prescription"], "data": p})
    for f in factures:
        timeline.append({"type": "facture", "date": f["date_facture"], "data": f})
    for l in labo:
        timeline.append({"type": "labo", "date": l["date_creation"], "data": l})
    for r in radio:
        timeline.append({"type": "radio", "date": r["date_creation"], "data": r})
    for doc in documents:
        timeline.append({"type": "document", "date": doc["date_creation"], "data": doc})
    timeline.sort(key=lambda x: str(x["date"]), reverse=True)

    return render_template("patients/detail.html", patient=patient, timeline=timeline, resume_patient=resume_patient,
                            rdvs=rdvs, pieces=pieces)


@bp.route("/<int:patient_id>/modifier", methods=["GET", "POST"])
@login_required
def edit_patient(patient_id):
    clinic_id = session["clinic_id"]
    patient = query_db("SELECT * FROM patients WHERE id = ? AND clinic_id = ?", (patient_id, clinic_id), one=True)
    if not patient:
        flash("Patient introuvable.", "error")
        return redirect(url_for("patients.list_patients"))

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            flash("Session expirée, veuillez réessayer.", "error")
            return redirect(url_for("patients.edit_patient", patient_id=patient_id))

        f = request.form
        execute_db(
            "UPDATE patients SET prenom=?, nom=?, sexe=?, date_naissance=?, groupe_sanguin=?, telephone=?, "
            "email=?, adresse=?, contact_urgence=?, allergies=?, maladies_chroniques=?, notes_medicales=?, "
            "assurance=? WHERE id = ? AND clinic_id = ?",
            (f["prenom"], f["nom"], f.get("sexe"), f.get("date_naissance") or None, f.get("groupe_sanguin"),
             f.get("telephone"), f.get("email"), f.get("adresse"), f.get("contact_urgence"),
             f.get("allergies"), f.get("maladies_chroniques"), f.get("notes_medicales"),
             f.get("assurance"), patient_id, clinic_id),
        )
        log_action("modification_patient", f"Patient modifié : {f['prenom']} {f['nom']}")
        flash("Fiche patient mise à jour.", "success")
        return redirect(url_for("patients.view_patient", patient_id=patient_id))

    return render_template("patients/form.html", patient=patient, mode="edit")


@bp.route("/<int:patient_id>/supprimer", methods=["POST"])
@login_required
def delete_patient(patient_id):
    clinic_id = session["clinic_id"]
    if not validate_csrf(request.form.get("csrf_token")):
        flash("Session expirée, veuillez réessayer.", "error")
        return redirect(url_for("patients.list_patients"))
    patient = query_db("SELECT * FROM patients WHERE id = ? AND clinic_id = ?", (patient_id, clinic_id), one=True)
    if patient:
        execute_db("DELETE FROM patients WHERE id = ? AND clinic_id = ?", (patient_id, clinic_id))
        log_action("suppression_patient", f"Patient supprimé : {patient['prenom']} {patient['nom']}")
        flash("Patient supprimé.", "success")
    return redirect(url_for("patients.list_patients"))


@bp.route("/<int:patient_id>/consultation", methods=["POST"])
@login_required
def add_consultation(patient_id):
    clinic_id = session["clinic_id"]
    if not validate_csrf(request.form.get("csrf_token")):
        flash("Session expirée, veuillez réessayer.", "error")
        return redirect(url_for("patients.view_patient", patient_id=patient_id))

    f = request.form
    execute_db(
        "INSERT INTO consultations (clinic_id, patient_id, medecin_id, motif, diagnostic, notes, poids, taille, "
        "tension, temperature, frequence_cardiaque, saturation_oxygene, glycemie, symptomes) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (clinic_id, patient_id, session["user_id"], f.get("motif"), f.get("diagnostic"), f.get("notes"),
         f.get("poids") or None, f.get("taille") or None, f.get("tension"), f.get("temperature") or None,
         f.get("frequence_cardiaque") or None, f.get("saturation_oxygene") or None,
         f.get("glycemie") or None, f.get("symptomes")),
    )
    log_action("ajout_consultation", f"Consultation ajoutée pour le patient #{patient_id}")
    flash("Consultation ajoutée au dossier médical.", "success")
    return redirect(url_for("patients.view_patient", patient_id=patient_id))


@bp.route("/<int:patient_id>/consultations")
@login_required
def consultation_history(patient_id):
    clinic_id = session["clinic_id"]
    patient = query_db("SELECT * FROM patients WHERE id = ? AND clinic_id = ?", (patient_id, clinic_id), one=True)
    if not patient:
        flash("Patient introuvable.", "error")
        return redirect(url_for("patients.list_patients"))
    consultations = query_db(
        "SELECT c.*, u.nom_complet AS medecin_nom FROM consultations c LEFT JOIN users u ON u.id = c.medecin_id "
        "WHERE c.patient_id = ? ORDER BY c.date_consultation DESC", (patient_id,))
    return render_template("patients/consultation_history.html", patient=patient, consultations=consultations)


@bp.route("/<int:patient_id>/rapports")
@login_required
def evolution_report(patient_id):
    clinic_id = session["clinic_id"]
    patient = query_db("SELECT * FROM patients WHERE id = ? AND clinic_id = ?", (patient_id, clinic_id), one=True)
    if not patient:
        flash("Patient introuvable.", "error")
        return redirect(url_for("patients.list_patients"))

    periode = request.args.get("periode", "mois")
    today = date.today()
    if periode == "semaine":
        debut = today - timedelta(days=7)
    elif periode == "annee":
        debut = today - timedelta(days=365)
    elif periode == "personnalise":
        try:
            debut = datetime.strptime(request.args.get("debut", ""), "%Y-%m-%d").date()
        except ValueError:
            debut = today - timedelta(days=30)
    else:
        debut = today - timedelta(days=30)

    consultations = query_db(
        "SELECT * FROM consultations WHERE patient_id = ? AND date(date_consultation) >= ? ORDER BY date_consultation ASC",
        (patient_id, debut))

    series = {"labels": [], "poids": [], "tension_sys": [], "tension_dia": [], "temperature": [],
              "frequence_cardiaque": [], "saturation_oxygene": [], "glycemie": [], "imc": []}
    for c in consultations:
        label = format_date_fr(c["date_consultation"])
        series["labels"].append(label)
        series["poids"].append(c["poids"])
        series["temperature"].append(c["temperature"])
        series["frequence_cardiaque"].append(c["frequence_cardiaque"])
        series["saturation_oxygene"].append(c["saturation_oxygene"])
        series["glycemie"].append(c["glycemie"])
        if c["tension"] and "/" in str(c["tension"]):
            try:
                sys_v, dia_v = c["tension"].split("/")
                series["tension_sys"].append(float(sys_v))
                series["tension_dia"].append(float(dia_v))
            except ValueError:
                series["tension_sys"].append(None)
                series["tension_dia"].append(None)
        else:
            series["tension_sys"].append(None)
            series["tension_dia"].append(None)
        if c["poids"] and c["taille"]:
            imc = c["poids"] / ((c["taille"] / 100) ** 2)
            series["imc"].append(round(imc, 1))
        else:
            series["imc"].append(None)

    return render_template("patients/evolution_report.html", patient=patient, consultations=consultations,
                            series=series, periode=periode, debut=debut, today=today)


@bp.route("/<int:patient_id>/rapports/pdf")
@login_required
def evolution_report_pdf(patient_id):
    from flask import send_file, g
    from app.utils.pdf_generator import generate_evolution_report_pdf

    clinic_id = session["clinic_id"]
    patient = query_db("SELECT * FROM patients WHERE id = ? AND clinic_id = ?", (patient_id, clinic_id), one=True)
    if not patient:
        flash("Patient introuvable.", "error")
        return redirect(url_for("patients.list_patients"))

    periode = request.args.get("periode", "mois")
    today = date.today()
    if periode == "semaine":
        debut = today - timedelta(days=7)
    elif periode == "annee":
        debut = today - timedelta(days=365)
    else:
        debut = today - timedelta(days=30)

    consultations = query_db(
        "SELECT * FROM consultations WHERE patient_id = ? AND date(date_consultation) >= ? ORDER BY date_consultation ASC",
        (patient_id, debut))

    clinic_dict = dict(g.clinic) if g.clinic else {}
    style = clinic_dict.get("documents_template") or "classique"
    buf = generate_evolution_report_pdf(clinic_dict, dict(patient), [dict(c) for c in consultations], periode, style)
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name=f"rapport_evolution_{patient_id}.pdf")
