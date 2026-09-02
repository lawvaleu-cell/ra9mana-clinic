from datetime import date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file, g

from app.db import query_db, execute_db
from app.utils.security import login_required, validate_csrf, log_action
from app.utils.helpers import generate_invoice_number, format_datetime_fr
from app.utils.pdf_generator import generate_invoice_pdf

bp = Blueprint("billing", __name__, url_prefix="/facturation")


@bp.route("/")
@login_required
def list_invoices():
    clinic_id = session["clinic_id"]
    statut = request.args.get("statut", "")
    where = "WHERE f.clinic_id = ?"
    params = [clinic_id]
    if statut:
        where += " AND f.statut = ?"
        params.append(statut)
    factures = query_db(
        f"SELECT f.*, p.prenom, p.nom FROM factures f JOIN patients p ON p.id = f.patient_id {where} "
        "ORDER BY f.date_facture DESC LIMIT 150", params)
    patients = query_db("SELECT id, prenom, nom, telephone FROM patients WHERE clinic_id = ? ORDER BY nom", (clinic_id,))
    return render_template("billing/invoices.html", factures=factures, statut=statut, patients=patients)


@bp.route("/nouvelle/<int:patient_id>", methods=["GET", "POST"])
@login_required
def create_invoice(patient_id):
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
        designations = f.getlist("designation[]")
        quantites = f.getlist("quantite[]")
        prix = f.getlist("prix[]")
        lignes = [(designations[i], int(quantites[i] or 1), float(prix[i] or 0))
                  for i in range(len(designations)) if designations[i].strip()]
        if not lignes:
            flash("Ajoutez au moins une ligne à la facture.", "error")
            return render_template("billing/invoice_form.html", patient=patient)

        total = sum(q * p for _, q, p in lignes)
        montant_paye = float(f.get("montant_paye") or 0)
        statut = "paye" if montant_paye >= total else ("partiel" if montant_paye > 0 else "impaye")

        last = query_db("SELECT COUNT(*) c FROM factures WHERE clinic_id = ?", (clinic_id,), one=True)["c"]
        numero = generate_invoice_number(clinic_id, last)

        facture_id = execute_db(
            "INSERT INTO factures (clinic_id, patient_id, numero_facture, montant_total, montant_paye, statut) "
            "VALUES (?,?,?,?,?,?)",
            (clinic_id, patient_id, numero, total, montant_paye, statut),
        )
        for desig, qte, pu in lignes:
            execute_db(
                "INSERT INTO facture_lignes (facture_id, designation, quantite, prix_unitaire) VALUES (?,?,?,?)",
                (facture_id, desig, qte, pu),
            )
        log_action("creation_facture", f"Facture {numero} créée ({total} {g.clinic['devise'] if g.clinic else ''})")
        flash("Facture créée avec succès.", "success")
        return redirect(url_for("billing.view_invoice", facture_id=facture_id))

    return render_template("billing/invoice_form.html", patient=patient)


@bp.route("/<int:facture_id>")
@login_required
def view_invoice(facture_id):
    clinic_id = session["clinic_id"]
    facture = query_db(
        "SELECT f.*, p.prenom, p.nom FROM factures f JOIN patients p ON p.id = f.patient_id "
        "WHERE f.id = ? AND f.clinic_id = ?", (facture_id, clinic_id), one=True)
    if not facture:
        flash("Facture introuvable.", "error")
        return redirect(url_for("billing.list_invoices"))
    lignes = query_db("SELECT * FROM facture_lignes WHERE facture_id = ?", (facture_id,))
    return render_template("billing/invoice_detail.html", facture=facture, lignes=lignes)


def _style():
    return (g.clinic["documents_template"] if g.clinic and "documents_template" in g.clinic.keys() else None) or "classique"


def _taille():
    t = request.args.get("taille", "A4").upper()
    return t if t in ("A4", "A5") else "A4"


def _invoice_context(facture_id, clinic_id):
    facture = query_db(
        "SELECT f.*, p.prenom, p.nom FROM factures f JOIN patients p ON p.id = f.patient_id "
        "WHERE f.id = ? AND f.clinic_id = ?", (facture_id, clinic_id), one=True)
    if not facture:
        return None, None, None
    lignes = query_db("SELECT * FROM facture_lignes WHERE facture_id = ?", (facture_id,))
    patient = {"prenom": facture["prenom"], "nom": facture["nom"]}
    f_dict = dict(facture)
    f_dict["date_str"] = format_datetime_fr(facture["date_facture"])
    return f_dict, patient, [dict(l) for l in lignes]


@bp.route("/<int:facture_id>/imprimer")
@login_required
def print_invoice(facture_id):
    f_dict, patient, lignes = _invoice_context(facture_id, session["clinic_id"])
    if not f_dict:
        flash("Facture introuvable.", "error")
        return redirect(url_for("billing.list_invoices"))
    clinic_dict = dict(g.clinic) if g.clinic else {}
    return render_template("documents/invoice_print.html", clinic=clinic_dict, patient=patient, facture=f_dict,
                            lignes=lignes, style=_style(), taille=_taille(), date_str=f_dict["date_str"])


@bp.route("/<int:facture_id>/pdf")
@login_required
def download_invoice_pdf(facture_id):
    f_dict, patient, lignes = _invoice_context(facture_id, session["clinic_id"])
    if not f_dict:
        flash("Facture introuvable.", "error")
        return redirect(url_for("billing.list_invoices"))
    clinic_dict = dict(g.clinic) if g.clinic else {}
    buf = generate_invoice_pdf(clinic_dict, patient, f_dict, lignes, _style(), _taille())
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name=f"facture_{f_dict['numero_facture']}.pdf")


@bp.route("/<int:facture_id>/paiement", methods=["POST"])
@login_required
def update_payment(facture_id):
    clinic_id = session["clinic_id"]
    if not validate_csrf(request.form.get("csrf_token")):
        flash("Session expirée, veuillez réessayer.", "error")
        return redirect(url_for("billing.view_invoice", facture_id=facture_id))

    facture = query_db("SELECT * FROM factures WHERE id = ? AND clinic_id = ?", (facture_id, clinic_id), one=True)
    if not facture:
        flash("Facture introuvable.", "error")
        return redirect(url_for("billing.list_invoices"))

    montant_paye = float(request.form.get("montant_paye") or 0)
    statut = "paye" if montant_paye >= facture["montant_total"] else ("partiel" if montant_paye > 0 else "impaye")
    execute_db("UPDATE factures SET montant_paye = ?, statut = ? WHERE id = ?", (montant_paye, statut, facture_id))
    log_action("paiement_facture", f"Paiement mis à jour pour facture #{facture_id}")
    flash("Paiement enregistré.", "success")
    return redirect(url_for("billing.view_invoice", facture_id=facture_id))


# ---------------- DÉPENSES ----------------

@bp.route("/depenses", methods=["GET", "POST"])
@login_required
def expenses():
    clinic_id = session["clinic_id"]
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            flash("Session expirée, veuillez réessayer.", "error")
            return redirect(url_for("billing.expenses"))
        f = request.form
        execute_db(
            "INSERT INTO depenses (clinic_id, categorie, description, montant, date_depense) VALUES (?,?,?,?,?)",
            (clinic_id, f["categorie"], f.get("description"), float(f["montant"]), f.get("date_depense") or date.today()),
        )
        log_action("ajout_depense", f"Dépense ajoutée : {f['categorie']} - {f['montant']}")
        flash("Dépense enregistrée.", "success")
        return redirect(url_for("billing.expenses"))

    liste = query_db("SELECT * FROM depenses WHERE clinic_id = ? ORDER BY date_depense DESC LIMIT 100", (clinic_id,))
    total_mois = query_db(
        "SELECT COALESCE(SUM(montant),0) s FROM depenses WHERE clinic_id = ? AND date_depense >= ?",
        (clinic_id, date.today().replace(day=1)), one=True)["s"]
    return render_template("billing/expenses.html", depenses=liste, total_mois=total_mois, today=date.today().isoformat())


@bp.route("/depenses/<int:dep_id>/supprimer", methods=["POST"])
@login_required
def delete_expense(dep_id):
    clinic_id = session["clinic_id"]
    if validate_csrf(request.form.get("csrf_token")):
        execute_db("DELETE FROM depenses WHERE id = ? AND clinic_id = ?", (dep_id, clinic_id))
        flash("Dépense supprimée.", "success")
    return redirect(url_for("billing.expenses"))


# ---------------- RAPPORTS ----------------

@bp.route("/rapports")
@login_required
def reports():
    clinic_id = session["clinic_id"]
    periode = request.args.get("periode", "mois")
    today = date.today()

    if periode == "annee":
        debut = today.replace(month=1, day=1)
    else:
        debut = today.replace(day=1)

    revenus = query_db(
        "SELECT COALESCE(SUM(montant_paye),0) s FROM factures WHERE clinic_id = ? AND date(date_facture) >= ?",
        (clinic_id, debut), one=True)["s"]
    revenus += query_db(
        "SELECT COALESCE(SUM(montant),0) s FROM paiements_rapides WHERE clinic_id = ? AND statut='paye' AND date(date_creation) >= ?",
        (clinic_id, debut), one=True)["s"]
    depenses = query_db(
        "SELECT COALESCE(SUM(montant),0) s FROM depenses WHERE clinic_id = ? AND date_depense >= ?",
        (clinic_id, debut), one=True)["s"]
    par_categorie = query_db(
        "SELECT categorie, SUM(montant) s FROM depenses WHERE clinic_id = ? AND date_depense >= ? GROUP BY categorie",
        (clinic_id, debut))
    nb_factures = query_db(
        "SELECT COUNT(*) c FROM factures WHERE clinic_id = ? AND date(date_facture) >= ?",
        (clinic_id, debut), one=True)["c"]
    impayes_total = query_db(
        "SELECT COALESCE(SUM(montant_total - montant_paye),0) s FROM factures WHERE clinic_id = ? AND statut != 'paye'",
        (clinic_id,), one=True)["s"]

    return render_template("billing/reports.html", periode=periode, revenus=revenus, depenses=depenses,
                            profit=revenus - depenses, par_categorie=par_categorie,
                            nb_factures=nb_factures, impayes_total=impayes_total)
