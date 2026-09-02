from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify

from app.db import query_db, execute_db
from app.utils.security import login_required, validate_csrf, log_action, notify_clinic

bp = Blueprint("waiting_room", __name__, url_prefix="/salle-attente")

CONSEILS_SANTE = [
    "Buvez au moins 1,5 litre d'eau par jour pour rester bien hydraté.",
    "Une marche de 30 minutes par jour améliore la santé cardiovasculaire.",
    "Lavez-vous les mains régulièrement pour prévenir les infections.",
    "Un sommeil de 7 à 8 heures par nuit renforce votre système immunitaire.",
    "Privilégiez les fruits et légumes frais à chaque repas.",
    "Pensez à faire des pauses écran toutes les 20 minutes.",
    "Respectez les horaires de prise de vos traitements prescrits.",
]


@bp.route("/paiement-rapide", methods=["POST"])
@login_required
def quick_payment():
    clinic_id = session["clinic_id"]
    if not validate_csrf(request.form.get("csrf_token")):
        flash("Session expirée, veuillez réessayer.", "error")
        return redirect(url_for("waiting_room.manage"))

    f = request.form
    patient_id = f.get("patient_id")
    montant = float(f.get("montant") or 0)
    statut = f.get("statut", "paye")
    methode = f.get("methode_paiement", "especes")
    notes = f.get("notes", "")
    file_attente_id = f.get("file_attente_id") or None

    execute_db(
        "INSERT INTO paiements_rapides (clinic_id, patient_id, rendez_vous_id, montant, statut, methode_paiement, notes, file_attente_id) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (clinic_id, patient_id, f.get("rendez_vous_id") or None, montant, statut, methode, notes, file_attente_id),
    )

    if statut == "paye" and file_attente_id:
        ticket = query_db("SELECT * FROM file_attente WHERE id = ? AND clinic_id = ?", (file_attente_id, clinic_id), one=True)
        if ticket and ticket["statut"] != "termine":
            execute_db("UPDATE file_attente SET statut = 'termine', heure_fin = ? WHERE id = ?",
                       (datetime.utcnow(), file_attente_id))
            if ticket["rendez_vous_id"]:
                execute_db("UPDATE rendez_vous SET statut = 'termine' WHERE id = ?", (ticket["rendez_vous_id"],))

    if statut == "paye":
        patient = query_db("SELECT prenom, nom FROM patients WHERE id = ?", (patient_id,), one=True)
        if patient:
            from app.utils.helpers import format_money
            notify_clinic(clinic_id, "Paiement encaissé",
                          f"{patient['prenom']} {patient['nom']} — {format_money(montant)}", "info", "normale", "finance")

    log_action("paiement_consultation", f"Paiement de consultation enregistré : {montant} ({statut})")
    flash("Paiement de consultation enregistré.", "success")
    return redirect(url_for("waiting_room.manage"))


@bp.route("/tickets/imprimer")
@login_required
def print_tickets():
    clinic_id = session["clinic_id"]
    taille = request.args.get("taille", "A4").upper()
    taille = taille if taille in ("A4", "A5") else "A4"
    nombre = request.args.get("nombre", 12, type=int)
    nombre = max(1, min(nombre or 12, 60))
    today = date.today()

    dernier = query_db(
        "SELECT COALESCE(MAX(numero_ticket), 0) m FROM file_attente WHERE clinic_id = ? AND date(heure_arrivee) = ?",
        (clinic_id, today), one=True)["m"]
    numeros = list(range(dernier + 1, dernier + 1 + nombre))

    clinic = query_db("SELECT * FROM clinics WHERE id = ?", (clinic_id,), one=True)
    return render_template("documents/waiting_tickets_print.html", numeros=numeros, clinic=clinic, taille=taille)


@bp.route("/enregistrement-rapide", methods=["POST"])
@login_required
def walk_in_registration():
    clinic_id = session["clinic_id"]
    if not validate_csrf(request.form.get("csrf_token")):
        flash("Session expirée, veuillez réessayer.", "error")
        return redirect(url_for("waiting_room.manage"))

    f = request.form
    mode_patient = f.get("mode_patient", "existant")
    if mode_patient == "nouveau":
        prenom = f.get("nouveau_prenom", "").strip()
        nom = f.get("nouveau_nom", "").strip()
        if not prenom or not nom:
            flash("Le prénom et le nom du nouveau patient sont obligatoires.", "error")
            return redirect(url_for("waiting_room.manage"))
        from app.utils.helpers import generate_patient_number
        last = query_db("SELECT COUNT(*) c FROM patients WHERE clinic_id = ?", (clinic_id,), one=True)["c"]
        numero = generate_patient_number(clinic_id, last)
        patient_id = execute_db(
            "INSERT INTO patients (clinic_id, numero_patient, prenom, nom, telephone) VALUES (?,?,?,?,?)",
            (clinic_id, numero, prenom, nom, f.get("nouveau_telephone")),
        )
    else:
        patient_id = f.get("patient_id")
        if not patient_id:
            flash("Veuillez sélectionner un patient.", "error")
            return redirect(url_for("waiting_room.manage"))

    today = date.today()
    heure_actuelle = datetime.now().strftime("%H:%M")
    rdv_id = execute_db(
        "INSERT INTO rendez_vous (clinic_id, patient_id, medecin_id, date_rdv, heure_rdv, motif, statut, couleur) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (clinic_id, patient_id, session["user_id"], today.isoformat(), heure_actuelle,
         "Passage sans rendez-vous", "en_attente", "#F59E0B"),
    )
    dernier = query_db(
        "SELECT COALESCE(MAX(numero_ticket),0) m FROM file_attente WHERE clinic_id = ? AND date(heure_arrivee) = ?",
        (clinic_id, today), one=True)["m"]
    execute_db(
        "INSERT INTO file_attente (clinic_id, patient_id, rendez_vous_id, numero_ticket, statut) VALUES (?,?,?,?,'en_attente')",
        (clinic_id, patient_id, rdv_id, dernier + 1),
    )
    patient = query_db("SELECT prenom, nom FROM patients WHERE id = ?", (patient_id,), one=True)
    notify_clinic(clinic_id, "Patient arrivé (sans RDV)",
                  f"{patient['prenom']} {patient['nom']} — ticket n°{dernier + 1}", "info", "normale", "salle_attente")
    log_action("enregistrement_rapide", f"Patient sans RDV enregistré directement — ticket n°{dernier + 1}")
    flash(f"Patient enregistré et ajouté à la file d'attente — ticket n°{dernier + 1}.", "success")
    return redirect(url_for("waiting_room.manage"))


@bp.route("/")
@login_required
def manage():
    clinic_id = session["clinic_id"]
    today = date.today()
    file_attente = query_db(
        "SELECT f.*, p.prenom, p.nom FROM file_attente f JOIN patients p ON p.id = f.patient_id "
        "WHERE f.clinic_id = ? AND date(f.heure_arrivee) = ? AND f.statut != 'termine' "
        "ORDER BY f.numero_ticket ASC",
        (clinic_id, today))
    rdvs_aujourdhui = query_db(
        "SELECT r.*, p.prenom, p.nom, p.id AS pid FROM rendez_vous r JOIN patients p ON p.id = r.patient_id "
        "WHERE r.clinic_id = ? AND r.date_rdv = ? AND r.statut NOT IN ('annule','termine') "
        "ORDER BY r.heure_rdv", (clinic_id, today))
    en_consultation = query_db(
        "SELECT f.*, p.prenom, p.nom FROM file_attente f JOIN patients p ON p.id = f.patient_id "
        "WHERE f.clinic_id = ? AND f.statut = 'en_consultation' ORDER BY f.heure_appel DESC LIMIT 1",
        (clinic_id,), one=True)
    paiement_a_saisir = query_db(
        "SELECT f.*, p.prenom, p.nom FROM file_attente f JOIN patients p ON p.id = f.patient_id "
        "WHERE f.clinic_id = ? AND f.statut = 'termine' AND date(f.heure_fin) = ? "
        "AND f.id NOT IN (SELECT COALESCE(file_attente_id, 0) FROM paiements_rapides) "
        "ORDER BY f.heure_fin DESC LIMIT 1",
        (clinic_id, today), one=True)
    patients = query_db("SELECT id, prenom, nom, telephone FROM patients WHERE clinic_id = ? ORDER BY nom", (clinic_id,))
    return render_template("appointments/waiting_room.html", file_attente=file_attente,
                            rdvs_aujourdhui=rdvs_aujourdhui, en_consultation=en_consultation,
                            paiement_a_saisir=paiement_a_saisir, patients=patients)


@bp.route("/arrivee/<int:rdv_id>", methods=["POST"])
@login_required
def patient_arrived(rdv_id):
    clinic_id = session["clinic_id"]
    rdv = query_db("SELECT * FROM rendez_vous WHERE id = ? AND clinic_id = ?", (rdv_id, clinic_id), one=True)
    if not rdv:
        flash("Rendez-vous introuvable.", "error")
        return redirect(url_for("waiting_room.manage"))

    today = date.today()
    dernier = query_db(
        "SELECT COALESCE(MAX(numero_ticket),0) m FROM file_attente WHERE clinic_id = ? AND date(heure_arrivee) = ?",
        (clinic_id, today), one=True)["m"]

    execute_db(
        "INSERT INTO file_attente (clinic_id, patient_id, rendez_vous_id, numero_ticket, statut) VALUES (?,?,?,?,'en_attente')",
        (clinic_id, rdv["patient_id"], rdv_id, dernier + 1),
    )
    execute_db("UPDATE rendez_vous SET statut = 'en_attente' WHERE id = ?", (rdv_id,))
    patient = query_db("SELECT prenom, nom FROM patients WHERE id = ?", (rdv["patient_id"],), one=True)
    notify_clinic(clinic_id, "Patient arrivé",
                  f"{patient['prenom']} {patient['nom']} — ticket n°{dernier + 1}", "info", "normale", "salle_attente")
    log_action("arrivee_patient", f"Patient arrivé, ticket n°{dernier + 1}")
    flash(f"Patient enregistré dans la file d'attente — ticket n°{dernier + 1}.", "success")
    return redirect(url_for("waiting_room.manage"))


@bp.route("/suivant", methods=["POST"])
@login_required
def call_next():
    clinic_id = session["clinic_id"]
    salle = request.form.get("salle", "1")

    # Termine la consultation en cours dans cette salle, si existante
    en_cours = query_db(
        "SELECT f.*, p.prenom, p.nom FROM file_attente f JOIN patients p ON p.id = f.patient_id "
        "WHERE f.clinic_id = ? AND f.salle = ? AND f.statut = 'en_consultation'", (clinic_id, salle), one=True)
    execute_db(
        "UPDATE file_attente SET statut = 'termine', heure_fin = ? "
        "WHERE clinic_id = ? AND salle = ? AND statut = 'en_consultation'",
        (datetime.utcnow(), clinic_id, salle),
    )
    if en_cours:
        notify_clinic(clinic_id, "Consultation terminée",
                      f"{en_cours['prenom']} {en_cours['nom']} — salle {salle}", "info", "normale", "consultation")

    suivant = query_db(
        "SELECT * FROM file_attente WHERE clinic_id = ? AND statut = 'en_attente' "
        "ORDER BY numero_ticket ASC LIMIT 1", (clinic_id,), one=True)

    if suivant:
        execute_db(
            "UPDATE file_attente SET statut = 'en_consultation', heure_appel = ?, salle = ? WHERE id = ?",
            (datetime.utcnow(), salle, suivant["id"]),
        )
        if suivant["rendez_vous_id"]:
            execute_db("UPDATE rendez_vous SET statut = 'en_consultation' WHERE id = ?", (suivant["rendez_vous_id"],))
        patient = query_db("SELECT prenom, nom FROM patients WHERE id = ?", (suivant["patient_id"],), one=True)
        notify_clinic(clinic_id, "Consultation démarrée",
                      f"{patient['prenom']} {patient['nom']} — salle {salle}", "info", "normale", "consultation")
        log_action("appel_patient_suivant", f"Ticket n°{suivant['numero_ticket']} appelé en salle {salle}")
        flash(f"Patient n°{suivant['numero_ticket']} appelé en salle {salle}.", "success")
    else:
        flash("Aucun patient en attente.", "info")

    return redirect(url_for("waiting_room.manage"))


@bp.route("/ecran")
def tv_display():
    """Écran public pour salle d'attente — aucune authentification requise, plein écran TV."""
    clinic_id = request.args.get("clinic_id", type=int)
    clinic = query_db("SELECT * FROM clinics WHERE id = ?", (clinic_id,), one=True) if clinic_id else None
    return render_template("appointments/tv_display.html", clinic=clinic, conseils=CONSEILS_SANTE)


@bp.route("/ecran/donnees")
def tv_data():
    """Endpoint JSON interrogé périodiquement par l'écran TV."""
    clinic_id = request.args.get("clinic_id", type=int)
    if not clinic_id:
        return jsonify({"ok": False}), 400

    en_cours = query_db(
        "SELECT f.numero_ticket, f.salle FROM file_attente f "
        "WHERE f.clinic_id = ? AND f.statut = 'en_consultation' ORDER BY f.heure_appel DESC LIMIT 1",
        (clinic_id,), one=True)
    prochain = query_db(
        "SELECT numero_ticket FROM file_attente WHERE clinic_id = ? AND statut = 'en_attente' "
        "ORDER BY numero_ticket ASC LIMIT 1", (clinic_id,), one=True)

    return jsonify({
        "ok": True,
        "numero_actuel": en_cours["numero_ticket"] if en_cours else None,
        "salle": en_cours["salle"] if en_cours else None,
        "numero_suivant": prochain["numero_ticket"] if prochain else None,
        "heure": datetime.now().strftime("%H:%M:%S"),
    })
