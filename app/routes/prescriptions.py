from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file, jsonify, g

from app.db import query_db, execute_db
from app.utils.security import login_required, validate_csrf, log_action
from app.utils.helpers import calculate_age, format_datetime_fr
from app.utils.pdf_generator import generate_prescription_pdf, generate_request_pdf

bp = Blueprint("prescriptions", __name__, url_prefix="/prescriptions")

UNITES_DOSAGE = ["mg", "g", "mcg", "ml", "l", "UI", "%", "comprimé(s)", "gélule(s)", "sachet(s)",
                  "ampoule(s)", "goutte(s)", "cuillère à café", "cuillère à soupe", "patch", "suppositoire"]


def _clinic_dict():
    return dict(g.clinic) if g.clinic else {}


def _style():
    return (g.clinic["documents_template"] if g.clinic and "documents_template" in g.clinic.keys() else None) or "classique"


def _taille():
    t = request.args.get("taille", "A4").upper()
    return t if t in ("A4", "A5") else "A4"


# ---------------- MODÈLES D'ORDONNANCE ----------------

@bp.route("/modeles")
@login_required
def list_templates():
    clinic_id = session["clinic_id"]
    modeles = query_db("SELECT * FROM modeles_prescription WHERE clinic_id = ? ORDER BY nom", (clinic_id,))
    return render_template("prescriptions/templates_list.html", modeles=modeles)


@bp.route("/modeles/nouveau", methods=["GET", "POST"])
@login_required
def create_template():
    clinic_id = session["clinic_id"]
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            flash("Session expirée, veuillez réessayer.", "error")
            return redirect(url_for("prescriptions.create_template"))
        f = request.form
        nom = f.get("nom", "").strip()
        if not nom:
            flash("Le nom du modèle est obligatoire.", "error")
            return render_template("prescriptions/template_form.html")

        medicaments = f.getlist("medicament[]")
        dosages = f.getlist("dosage[]")
        frequences = f.getlist("frequence[]")
        durees = f.getlist("duree[]")
        instructions = f.getlist("instructions[]")

        def _get(lst, i):
            return lst[i] if i < len(lst) else ""

        modele_id = execute_db("INSERT INTO modeles_prescription (clinic_id, nom, notes) VALUES (?,?,?)",
                                (clinic_id, nom, f.get("notes", "")))
        favoris_existants = {fv["nom"].lower() for fv in query_db(
            "SELECT nom FROM medicaments_favoris WHERE clinic_id = ?", (clinic_id,))}
        for i, m in enumerate(medicaments):
            if not m.strip():
                continue
            d, fr = _get(dosages, i), _get(frequences, i)
            execute_db(
                "INSERT INTO modele_prescription_lignes (modele_id, medicament, dosage, frequence, duree, instructions) "
                "VALUES (?,?,?,?,?,?)",
                (modele_id, m, d, fr, _get(durees, i), _get(instructions, i)),
            )
            if m.strip().lower() not in favoris_existants:
                execute_db(
                    "INSERT INTO medicaments_favoris (clinic_id, nom, dosage_defaut, frequence_defaut) VALUES (?,?,?,?)",
                    (clinic_id, m.strip(), d, fr),
                )
                favoris_existants.add(m.strip().lower())
        flash("Modèle d'ordonnance créé avec succès.", "success")
        return redirect(url_for("prescriptions.list_templates"))

    return render_template("prescriptions/template_form.html")


@bp.route("/modeles/<int:modele_id>/json")
@login_required
def template_json(modele_id):
    clinic_id = session["clinic_id"]
    modele = query_db("SELECT * FROM modeles_prescription WHERE id = ? AND clinic_id = ?", (modele_id, clinic_id), one=True)
    if not modele:
        return jsonify({"ok": False}), 404
    lignes = query_db("SELECT * FROM modele_prescription_lignes WHERE modele_id = ?", (modele_id,))
    return jsonify({"ok": True, "notes": modele["notes"], "lignes": [dict(l) for l in lignes]})


@bp.route("/modeles/<int:modele_id>/supprimer", methods=["POST"])
@login_required
def delete_template(modele_id):
    clinic_id = session["clinic_id"]
    execute_db("DELETE FROM modeles_prescription WHERE id = ? AND clinic_id = ?", (modele_id, clinic_id))
    flash("Modèle supprimé.", "success")
    return redirect(url_for("prescriptions.list_templates"))


# ---------------- MODÈLES DE DEMANDES (LABO / RADIOLOGIE) ----------------

@bp.route("/demande-modeles/<type_demande>")
@login_required
def list_request_templates(type_demande):
    clinic_id = session["clinic_id"]
    modeles = query_db(
        "SELECT * FROM modeles_demande WHERE clinic_id = ? AND type_demande = ? ORDER BY nom",
        (clinic_id, type_demande))
    titre = "Laboratoire" if type_demande == "laboratoire" else "Radiologie"
    return render_template("prescriptions/request_templates_list.html", modeles=modeles,
                            type_demande=type_demande, titre=titre)


@bp.route("/demande-modeles/<type_demande>/nouveau", methods=["POST"])
@login_required
def create_request_template(type_demande):
    clinic_id = session["clinic_id"]
    if not validate_csrf(request.form.get("csrf_token")):
        flash("Session expirée, veuillez réessayer.", "error")
        return redirect(url_for("prescriptions.list_request_templates", type_demande=type_demande))
    nom = request.form.get("nom", "").strip()
    contenu = request.form.get("contenu", "").strip()
    if nom and contenu:
        execute_db("INSERT INTO modeles_demande (clinic_id, type_demande, nom, contenu) VALUES (?,?,?,?)",
                   (clinic_id, type_demande, nom, contenu))
        flash("Modèle créé avec succès.", "success")
    else:
        flash("Le nom et le contenu sont obligatoires.", "error")
    return redirect(url_for("prescriptions.list_request_templates", type_demande=type_demande))


@bp.route("/demande-modeles/<int:modele_id>/json")
@login_required
def request_template_json(modele_id):
    clinic_id = session["clinic_id"]
    modele = query_db("SELECT * FROM modeles_demande WHERE id = ? AND clinic_id = ?", (modele_id, clinic_id), one=True)
    if not modele:
        return jsonify({"ok": False}), 404
    return jsonify({"ok": True, "contenu": modele["contenu"]})


@bp.route("/demande-modeles/<int:modele_id>/supprimer", methods=["POST"])
@login_required
def delete_request_template(modele_id):
    clinic_id = session["clinic_id"]
    modele = query_db("SELECT * FROM modeles_demande WHERE id = ? AND clinic_id = ?", (modele_id, clinic_id), one=True)
    if modele:
        execute_db("DELETE FROM modeles_demande WHERE id = ? AND clinic_id = ?", (modele_id, clinic_id))
        flash("Modèle supprimé.", "success")
        return redirect(url_for("prescriptions.list_request_templates", type_demande=modele["type_demande"]))
    return redirect(url_for("prescriptions.list_prescriptions"))


@bp.route("/")
@login_required
def list_prescriptions():
    clinic_id = session["clinic_id"]
    prescriptions = query_db(
        "SELECT pr.*, p.prenom, p.nom, p.id as patient_id FROM prescriptions pr "
        "JOIN patients p ON p.id = pr.patient_id WHERE pr.clinic_id = ? "
        "ORDER BY pr.date_prescription DESC LIMIT 100", (clinic_id,))
    return render_template("prescriptions/list.html", prescriptions=prescriptions)


@bp.route("/nouveau/<int:patient_id>", methods=["GET", "POST"])
@login_required
def create_prescription(patient_id):
    clinic_id = session["clinic_id"]
    patient = query_db("SELECT * FROM patients WHERE id = ? AND clinic_id = ?", (patient_id, clinic_id), one=True)
    if not patient:
        flash("Patient introuvable.", "error")
        return redirect(url_for("patients.list_patients"))

    favoris = query_db("SELECT * FROM medicaments_favoris WHERE clinic_id = ? ORDER BY nom", (clinic_id,))
    modeles = query_db("SELECT * FROM modeles_prescription WHERE clinic_id = ? ORDER BY nom", (clinic_id,))
    medicaments_connus = sorted(set(
        [f["nom"] for f in favoris] +
        [row["medicament"] for row in query_db(
            "SELECT DISTINCT pl.medicament FROM prescription_lignes pl JOIN prescriptions pr ON pr.id = pl.prescription_id "
            "WHERE pr.clinic_id = ?", (clinic_id,))]
    ))

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            flash("Session expirée, veuillez réessayer.", "error")
            return redirect(url_for("prescriptions.create_prescription", patient_id=patient_id))

        f = request.form
        medicaments = f.getlist("medicament[]")
        dosages = f.getlist("dosage[]")
        frequences = f.getlist("frequence[]")
        durees = f.getlist("duree[]")
        instructions = f.getlist("instructions[]")

        def _get(lst, i):
            return lst[i] if i < len(lst) else ""

        lignes_valides = [(m, _get(dosages, i), _get(frequences, i), _get(durees, i), _get(instructions, i))
                           for i, m in enumerate(medicaments) if m.strip()]
        if not lignes_valides:
            flash("Ajoutez au moins un médicament à l'ordonnance.", "error")
            return render_template("prescriptions/form.html", patient=patient, favoris=favoris, modeles=modeles,
                                    medicaments_connus=medicaments_connus, unites_dosage=UNITES_DOSAGE)

        prescription_id = execute_db(
            "INSERT INTO prescriptions (clinic_id, patient_id, medecin_id, notes) VALUES (?,?,?,?)",
            (clinic_id, patient_id, session["user_id"], f.get("notes")),
        )
        noms_favoris_existants = {fv["nom"].lower() for fv in favoris}
        for m, d, fr, du, ins in lignes_valides:
            execute_db(
                "INSERT INTO prescription_lignes (prescription_id, medicament, dosage, frequence, duree, instructions) "
                "VALUES (?,?,?,?,?,?)", (prescription_id, m, d, fr, du, ins),
            )
            if m.strip().lower() not in noms_favoris_existants:
                execute_db(
                    "INSERT INTO medicaments_favoris (clinic_id, nom, dosage_defaut, frequence_defaut) VALUES (?,?,?,?)",
                    (clinic_id, m.strip(), d, fr),
                )
                noms_favoris_existants.add(m.strip().lower())
        log_action("creation_prescription", f"Ordonnance créée pour le patient #{patient_id}")
        flash("Ordonnance créée avec succès.", "success")
        return redirect(url_for("prescriptions.view_prescription", prescription_id=prescription_id))

    return render_template("prescriptions/form.html", patient=patient, favoris=favoris, modeles=modeles,
                            medicaments_connus=medicaments_connus, unites_dosage=UNITES_DOSAGE)


@bp.route("/<int:prescription_id>")
@login_required
def view_prescription(prescription_id):
    clinic_id = session["clinic_id"]
    prescription = query_db(
        "SELECT pr.*, p.prenom, p.nom, p.id as patient_id, p.numero_patient, p.date_naissance FROM prescriptions pr "
        "JOIN patients p ON p.id = pr.patient_id WHERE pr.id = ? AND pr.clinic_id = ?",
        (prescription_id, clinic_id), one=True)
    if not prescription:
        flash("Ordonnance introuvable.", "error")
        return redirect(url_for("prescriptions.list_prescriptions"))
    lignes = query_db("SELECT * FROM prescription_lignes WHERE prescription_id = ?", (prescription_id,))
    return render_template("prescriptions/detail.html", prescription=prescription, lignes=lignes)


def _prescription_context(prescription_id, clinic_id):
    prescription = query_db(
        "SELECT pr.*, p.prenom, p.nom, p.id as patient_id, p.numero_patient, p.date_naissance FROM prescriptions pr "
        "JOIN patients p ON p.id = pr.patient_id WHERE pr.id = ? AND pr.clinic_id = ?",
        (prescription_id, clinic_id), one=True)
    if not prescription:
        return None, None, None, None
    lignes = query_db("SELECT * FROM prescription_lignes WHERE prescription_id = ?", (prescription_id,))
    patient = {"prenom": prescription["prenom"], "nom": prescription["nom"],
               "numero_patient": prescription["numero_patient"], "id": prescription["patient_id"]}
    age = calculate_age(prescription["date_naissance"])
    pres_dict = dict(prescription)
    pres_dict["date_str"] = format_datetime_fr(prescription["date_prescription"])
    return pres_dict, patient, [dict(l) for l in lignes], age


@bp.route("/<int:prescription_id>/imprimer")
@login_required
def print_prescription(prescription_id):
    pres_dict, patient, lignes, age = _prescription_context(prescription_id, session["clinic_id"])
    if not pres_dict:
        flash("Ordonnance introuvable.", "error")
        return redirect(url_for("prescriptions.list_prescriptions"))
    return render_template("documents/prescription_print.html", clinic=_clinic_dict(), patient=patient,
                            prescription=pres_dict, lignes=lignes, age=age, style=_style(), taille=_taille(),
                            date_str=pres_dict["date_str"])


@bp.route("/<int:prescription_id>/pdf")
@login_required
def download_prescription_pdf(prescription_id):
    pres_dict, patient, lignes, age = _prescription_context(prescription_id, session["clinic_id"])
    if not pres_dict:
        flash("Ordonnance introuvable.", "error")
        return redirect(url_for("prescriptions.list_prescriptions"))
    buf = generate_prescription_pdf(_clinic_dict(), patient, pres_dict, lignes, age, _style(), _taille())
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name=f"ordonnance_{prescription_id}.pdf")


@bp.route("/medicament-favori", methods=["POST"])
@login_required
def add_favorite_medicine():
    clinic_id = session["clinic_id"]
    data = request.get_json(silent=True) or request.form
    nom = data.get("nom", "").strip()
    if nom:
        execute_db("INSERT INTO medicaments_favoris (clinic_id, nom, dosage_defaut, frequence_defaut) VALUES (?,?,?,?)",
                    (clinic_id, nom, data.get("dosage", ""), data.get("frequence", "")))
    return jsonify({"ok": True})


# ---------------- LABORATOIRE ----------------

@bp.route("/laboratoire/nouveau/<int:patient_id>", methods=["GET", "POST"])
@login_required
def create_lab_request(patient_id):
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
        req_id = execute_db(
            "INSERT INTO demandes_laboratoire (clinic_id, patient_id, medecin_id, analyses, notes) VALUES (?,?,?,?,?)",
            (clinic_id, patient_id, session["user_id"], f.get("analyses"), f.get("notes")),
        )
        log_action("demande_laboratoire", f"Demande labo créée pour le patient #{patient_id}")
        flash("Demande d'analyse créée avec succès.", "success")
        return redirect(url_for("prescriptions.view_lab_request", request_id=req_id))

    modeles = query_db("SELECT * FROM modeles_demande WHERE clinic_id = ? AND type_demande = 'laboratoire' ORDER BY nom", (clinic_id,))
    return render_template("prescriptions/lab_form.html", patient=patient, modeles=modeles)


def _lab_context(request_id, clinic_id):
    demande = query_db(
        "SELECT d.*, p.prenom, p.nom, p.numero_patient, p.date_naissance, p.id as patient_id FROM demandes_laboratoire d "
        "JOIN patients p ON p.id = d.patient_id WHERE d.id = ? AND d.clinic_id = ?",
        (request_id, clinic_id), one=True)
    if not demande:
        return None, None, None
    patient = {"prenom": demande["prenom"], "nom": demande["nom"], "numero_patient": demande["numero_patient"],
               "id": demande["patient_id"]}
    age = calculate_age(demande["date_naissance"])
    d = dict(demande)
    d["date_str"] = format_datetime_fr(demande["date_creation"])
    return d, patient, age


@bp.route("/laboratoire/<int:request_id>")
@login_required
def view_lab_request(request_id):
    d, patient, age = _lab_context(request_id, session["clinic_id"])
    if not d:
        flash("Demande introuvable.", "error")
        return redirect(url_for("patients.list_patients"))
    return render_template("prescriptions/request_detail.html", demande=d, patient=patient,
                            titre="Demande de laboratoire", type_route="laboratoire")


@bp.route("/laboratoire/<int:request_id>/imprimer")
@login_required
def print_lab_request(request_id):
    d, patient, age = _lab_context(request_id, session["clinic_id"])
    if not d:
        flash("Demande introuvable.", "error")
        return redirect(url_for("patients.list_patients"))
    return render_template("documents/lab_print.html", clinic=_clinic_dict(), patient=patient, demande=d, age=age,
                            style=_style(), taille=_taille(), date_str=d["date_str"])


@bp.route("/laboratoire/<int:request_id>/pdf")
@login_required
def download_lab_pdf(request_id):
    d, patient, age = _lab_context(request_id, session["clinic_id"])
    if not d:
        flash("Demande introuvable.", "error")
        return redirect(url_for("patients.list_patients"))
    buf = generate_request_pdf(_clinic_dict(), patient, d, d["analyses"], age,
                                "DEMANDE D'ANALYSES DE LABORATOIRE", _style(), _taille())
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name=f"demande_labo_{request_id}.pdf")


# ---------------- RADIOLOGIE ----------------

@bp.route("/radiologie/nouveau/<int:patient_id>", methods=["GET", "POST"])
@login_required
def create_radio_request(patient_id):
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
        req_id = execute_db(
            "INSERT INTO demandes_radiologie (clinic_id, patient_id, medecin_id, examens, notes) VALUES (?,?,?,?,?)",
            (clinic_id, patient_id, session["user_id"], f.get("examens"), f.get("notes")),
        )
        log_action("demande_radiologie", f"Demande radio créée pour le patient #{patient_id}")
        flash("Demande d'examen radiologique créée avec succès.", "success")
        return redirect(url_for("prescriptions.view_radio_request", request_id=req_id))

    modeles = query_db("SELECT * FROM modeles_demande WHERE clinic_id = ? AND type_demande = 'radiologie' ORDER BY nom", (clinic_id,))
    return render_template("prescriptions/radio_form.html", patient=patient, modeles=modeles)


def _radio_context(request_id, clinic_id):
    demande = query_db(
        "SELECT d.*, p.prenom, p.nom, p.numero_patient, p.date_naissance, p.id as patient_id FROM demandes_radiologie d "
        "JOIN patients p ON p.id = d.patient_id WHERE d.id = ? AND d.clinic_id = ?",
        (request_id, clinic_id), one=True)
    if not demande:
        return None, None, None
    patient = {"prenom": demande["prenom"], "nom": demande["nom"], "numero_patient": demande["numero_patient"],
               "id": demande["patient_id"]}
    age = calculate_age(demande["date_naissance"])
    d = dict(demande)
    d["date_str"] = format_datetime_fr(demande["date_creation"])
    return d, patient, age


@bp.route("/radiologie/<int:request_id>")
@login_required
def view_radio_request(request_id):
    d, patient, age = _radio_context(request_id, session["clinic_id"])
    if not d:
        flash("Demande introuvable.", "error")
        return redirect(url_for("patients.list_patients"))
    return render_template("prescriptions/request_detail.html", demande=d, patient=patient,
                            titre="Demande de radiologie", type_route="radiologie")


@bp.route("/radiologie/<int:request_id>/imprimer")
@login_required
def print_radio_request(request_id):
    d, patient, age = _radio_context(request_id, session["clinic_id"])
    if not d:
        flash("Demande introuvable.", "error")
        return redirect(url_for("patients.list_patients"))
    return render_template("documents/radio_print.html", clinic=_clinic_dict(), patient=patient, demande=d, age=age,
                            style=_style(), taille=_taille(), date_str=d["date_str"])


@bp.route("/radiologie/<int:request_id>/pdf")
@login_required
def download_radio_pdf(request_id):
    d, patient, age = _radio_context(request_id, session["clinic_id"])
    if not d:
        flash("Demande introuvable.", "error")
        return redirect(url_for("patients.list_patients"))
    buf = generate_request_pdf(_clinic_dict(), patient, d, d["examens"], age,
                                "DEMANDE D'EXAMEN RADIOLOGIQUE", _style(), _taille())
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name=f"demande_radio_{request_id}.pdf")
