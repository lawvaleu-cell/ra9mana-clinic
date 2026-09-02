from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify

from app.db import query_db, execute_db
from app.utils.security import login_required, validate_csrf, log_action, create_notification, notify_clinic
from app.utils.helpers import STATUT_RDV_LABELS, STATUT_RDV_COULEURS

bp = Blueprint("appointments", __name__, url_prefix="/rendez-vous")


@bp.route("/")
@login_required
def calendar_view():
    clinic_id = session["clinic_id"]
    vue = request.args.get("vue", "semaine")
    jour_str = request.args.get("date")
    ref_date = datetime.strptime(jour_str, "%Y-%m-%d").date() if jour_str else date.today()

    if vue == "jour":
        debut, fin = ref_date, ref_date
    elif vue == "mois":
        debut = ref_date.replace(day=1)
        prochain_mois = (debut.replace(day=28) + timedelta(days=4)).replace(day=1)
        fin = prochain_mois - timedelta(days=1)
    else:  # semaine
        debut = ref_date - timedelta(days=ref_date.weekday())
        fin = debut + timedelta(days=6)

    rdvs = query_db(
        "SELECT r.*, p.prenom, p.nom, p.telephone FROM rendez_vous r "
        "JOIN patients p ON p.id = r.patient_id "
        "WHERE r.clinic_id = ? AND r.date_rdv BETWEEN ? AND ? "
        "ORDER BY r.date_rdv, r.heure_rdv",
        (clinic_id, debut, fin))

    patients = query_db("SELECT id, prenom, nom, telephone FROM patients WHERE clinic_id = ? ORDER BY nom", (clinic_id,))

    nb_jours = (fin - debut).days + 1
    jours = [debut + timedelta(days=i) for i in range(nb_jours)]

    if vue == "jour":
        delta = timedelta(days=1)
    elif vue == "mois":
        delta = timedelta(days=nb_jours)
    else:
        delta = timedelta(days=7)
    prev_date = (ref_date - delta).isoformat()
    next_date = (ref_date + delta).isoformat()

    return render_template("appointments/calendar.html", rdvs=rdvs, vue=vue, ref_date=ref_date,
                            debut=debut, fin=fin, patients=patients, jours=jours, today=date.today(),
                            prev_date=prev_date, next_date=next_date,
                            statut_labels=STATUT_RDV_LABELS, statut_couleurs=STATUT_RDV_COULEURS)


@bp.route("/nouveau", methods=["POST"])
@login_required
def create_appointment():
    clinic_id = session["clinic_id"]
    if not validate_csrf(request.form.get("csrf_token")):
        flash("Session expirée, veuillez réessayer.", "error")
        return redirect(url_for("appointments.calendar_view"))

    f = request.form
    couleur = STATUT_RDV_COULEURS.get("planifie")

    mode_patient = f.get("mode_patient", "existant")
    if mode_patient == "nouveau":
        prenom = f.get("nouveau_prenom", "").strip()
        nom = f.get("nouveau_nom", "").strip()
        if not prenom or not nom:
            flash("Le prénom et le nom du nouveau patient sont obligatoires.", "error")
            return redirect(url_for("appointments.calendar_view"))

        last = query_db("SELECT COUNT(*) c FROM patients WHERE clinic_id = ?", (clinic_id,), one=True)["c"]
        from app.utils.helpers import generate_patient_number
        numero = generate_patient_number(clinic_id, last)
        patient_id = execute_db(
            "INSERT INTO patients (clinic_id, numero_patient, prenom, nom, sexe, date_naissance, telephone) "
            "VALUES (?,?,?,?,?,?,?)",
            (clinic_id, numero, prenom, nom, f.get("nouveau_sexe"),
             f.get("nouveau_date_naissance") or None, f.get("nouveau_telephone")),
        )
        log_action("creation_patient_rapide", f"Patient créé rapidement depuis le RDV : {prenom} {nom}")
    else:
        patient_id = f.get("patient_id")
        if not patient_id:
            flash("Veuillez sélectionner un patient.", "error")
            return redirect(url_for("appointments.calendar_view"))

    execute_db(
        "INSERT INTO rendez_vous (clinic_id, patient_id, medecin_id, date_rdv, heure_rdv, motif, statut, couleur) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (clinic_id, patient_id, session["user_id"], f["date_rdv"], f["heure_rdv"],
         f.get("motif"), "planifie", couleur),
    )
    patient_nom_notif = query_db("SELECT prenom, nom FROM patients WHERE id = ?", (patient_id,), one=True)
    if patient_nom_notif:
        notify_clinic(clinic_id, "Nouveau rendez-vous",
                      f"{patient_nom_notif['prenom']} {patient_nom_notif['nom']} — {f['date_rdv']} à {f['heure_rdv']}",
                      "info", "normale", "rendez_vous")
    log_action("creation_rdv", f"Rendez-vous créé pour le {f['date_rdv']} à {f['heure_rdv']}")
    flash("Rendez-vous planifié avec succès.", "success")
    return redirect(url_for("appointments.calendar_view", date=f["date_rdv"]))


@bp.route("/<int:rdv_id>/statut", methods=["POST"])
@login_required
def update_status(rdv_id):
    clinic_id = session["clinic_id"]
    data = request.get_json(silent=True) or request.form
    nouveau_statut = data.get("statut")
    if nouveau_statut not in STATUT_RDV_LABELS:
        return jsonify({"ok": False, "error": "Statut invalide"}), 400

    couleur = STATUT_RDV_COULEURS.get(nouveau_statut)
    execute_db("UPDATE rendez_vous SET statut = ?, couleur = ? WHERE id = ? AND clinic_id = ?",
               (nouveau_statut, couleur, rdv_id, clinic_id))
    if nouveau_statut == "annule":
        rdv_info = query_db(
            "SELECT r.date_rdv, r.heure_rdv, p.prenom, p.nom FROM rendez_vous r JOIN patients p ON p.id = r.patient_id "
            "WHERE r.id = ?", (rdv_id,), one=True)
        if rdv_info:
            notify_clinic(clinic_id, "Rendez-vous annulé",
                          f"{rdv_info['prenom']} {rdv_info['nom']} — {rdv_info['date_rdv']} à {rdv_info['heure_rdv']}",
                          "alerte", "haute", "rendez_vous")
    log_action("modification_statut_rdv", f"RDV #{rdv_id} -> {nouveau_statut}")
    return jsonify({"ok": True, "statut": nouveau_statut, "libelle": STATUT_RDV_LABELS[nouveau_statut], "couleur": couleur})


@bp.route("/<int:rdv_id>/deplacer", methods=["POST"])
@login_required
def move_appointment(rdv_id):
    """Utilisé pour le glisser-déposer sur le calendrier."""
    clinic_id = session["clinic_id"]
    data = request.get_json(silent=True) or {}
    date_rdv = data.get("date_rdv")
    heure_rdv = data.get("heure_rdv")
    if not date_rdv or not heure_rdv:
        return jsonify({"ok": False, "error": "Données manquantes"}), 400

    execute_db("UPDATE rendez_vous SET date_rdv = ?, heure_rdv = ? WHERE id = ? AND clinic_id = ?",
               (date_rdv, heure_rdv, rdv_id, clinic_id))
    log_action("deplacement_rdv", f"RDV #{rdv_id} déplacé au {date_rdv} {heure_rdv}")
    return jsonify({"ok": True})


@bp.route("/<int:rdv_id>/supprimer", methods=["POST"])
@login_required
def delete_appointment(rdv_id):
    clinic_id = session["clinic_id"]
    if not validate_csrf(request.form.get("csrf_token")):
        flash("Session expirée, veuillez réessayer.", "error")
    else:
        execute_db("DELETE FROM rendez_vous WHERE id = ? AND clinic_id = ?", (rdv_id, clinic_id))
        log_action("suppression_rdv", f"RDV #{rdv_id} supprimé")
        flash("Rendez-vous supprimé.", "success")
    return redirect(url_for("appointments.calendar_view"))
