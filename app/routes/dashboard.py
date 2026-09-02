from datetime import date, timedelta
from flask import Blueprint, render_template, session, g

from app.db import query_db
from app.utils.security import login_required

bp = Blueprint("dashboard", __name__, url_prefix="/tableau-de-bord")


@bp.route("/")
@login_required
def index():
    clinic_id = session["clinic_id"]
    today = date.today()
    debut_mois = today.replace(day=1)

    patients_aujourdhui = query_db(
        "SELECT COUNT(*) c FROM rendez_vous WHERE clinic_id = ? AND date_rdv = ?",
        (clinic_id, today), one=True)["c"]

    patients_mois = query_db(
        "SELECT COUNT(*) c FROM patients WHERE clinic_id = ? AND date(date_inscription) >= ?",
        (clinic_id, debut_mois), one=True)["c"]

    total_patients = query_db(
        "SELECT COUNT(*) c FROM patients WHERE clinic_id = ?", (clinic_id,), one=True)["c"]

    rdv_aujourdhui = query_db(
        "SELECT COUNT(*) c FROM rendez_vous WHERE clinic_id = ? AND date_rdv = ? AND statut NOT IN ('annule')",
        (clinic_id, today), one=True)["c"]

    revenu_jour = query_db(
        "SELECT COALESCE(SUM(montant_paye),0) s FROM factures WHERE clinic_id = ? AND date(date_facture) = ?",
        (clinic_id, today), one=True)["s"]
    revenu_jour += query_db(
        "SELECT COALESCE(SUM(montant),0) s FROM paiements_rapides WHERE clinic_id = ? AND statut='paye' AND date(date_creation) = ?",
        (clinic_id, today), one=True)["s"]

    revenu_mois = query_db(
        "SELECT COALESCE(SUM(montant_paye),0) s FROM factures WHERE clinic_id = ? AND date(date_facture) >= ?",
        (clinic_id, debut_mois), one=True)["s"]
    revenu_mois += query_db(
        "SELECT COALESCE(SUM(montant),0) s FROM paiements_rapides WHERE clinic_id = ? AND statut='paye' AND date(date_creation) >= ?",
        (clinic_id, debut_mois), one=True)["s"]

    depenses_mois = query_db(
        "SELECT COALESCE(SUM(montant),0) s FROM depenses WHERE clinic_id = ? AND date_depense >= ?",
        (clinic_id, debut_mois), one=True)["s"]

    impayes = query_db(
        "SELECT COUNT(*) c FROM factures WHERE clinic_id = ? AND statut != 'paye'",
        (clinic_id,), one=True)["c"]

    stock_bas = query_db(
        "SELECT COUNT(*) c FROM medicaments WHERE clinic_id = ? AND quantite <= quantite_min",
        (clinic_id,), one=True)["c"]

    expiration_limite = today + timedelta(days=60)
    perimes = query_db(
        "SELECT COUNT(*) c FROM medicaments WHERE clinic_id = ? AND date_expiration IS NOT NULL AND date_expiration <= ?",
        (clinic_id, expiration_limite), one=True)["c"]

    prochains_rdv = query_db(
        "SELECT r.*, p.prenom, p.nom FROM rendez_vous r JOIN patients p ON p.id = r.patient_id "
        "WHERE r.clinic_id = ? AND r.date_rdv >= ? AND r.statut NOT IN ('annule','termine') "
        "ORDER BY r.date_rdv ASC, r.heure_rdv ASC LIMIT 6",
        (clinic_id, today))

    notifications_recentes = query_db(
        "SELECT * FROM notifications WHERE clinic_id = ? AND user_id = ? ORDER BY date_creation DESC LIMIT 5",
        (clinic_id, session["user_id"]))

    # Revenus des 7 derniers jours (pour le graphique)
    labels_semaine, revenus_semaine = [], []
    for i in range(6, -1, -1):
        jour = today - timedelta(days=i)
        s = query_db(
            "SELECT COALESCE(SUM(montant_paye),0) s FROM factures WHERE clinic_id = ? AND date(date_facture) = ?",
            (clinic_id, jour), one=True)["s"]
        s += query_db(
            "SELECT COALESCE(SUM(montant),0) s FROM paiements_rapides WHERE clinic_id = ? AND statut='paye' AND date(date_creation) = ?",
            (clinic_id, jour), one=True)["s"]
        labels_semaine.append(jour.strftime("%d/%m"))
        revenus_semaine.append(round(s, 2))

    repartition_statuts = query_db(
        "SELECT statut, COUNT(*) c FROM rendez_vous WHERE clinic_id = ? AND date_rdv >= ? GROUP BY statut",
        (clinic_id, debut_mois))

    objectif_revenu = (g.clinic["objectif_revenu_mensuel"] if g.clinic and g.clinic["objectif_revenu_mensuel"] else 100000) or 100000
    pct_objectif_revenu = min(100, round((revenu_mois / objectif_revenu) * 100)) if objectif_revenu else 0
    pct_consultations_jour = min(100, round((patients_aujourdhui / 15) * 100)) if patients_aujourdhui else 0
    total_articles_stock = query_db("SELECT COUNT(*) c FROM medicaments WHERE clinic_id = ?", (clinic_id,), one=True)["c"]
    pct_stock_ok = round(((total_articles_stock - stock_bas) / total_articles_stock) * 100) if total_articles_stock else 100
    total_factures_mois = query_db(
        "SELECT COUNT(*) c FROM factures WHERE clinic_id = ? AND date(date_facture) >= ?", (clinic_id, debut_mois), one=True)["c"]
    factures_payees_mois = query_db(
        "SELECT COUNT(*) c FROM factures WHERE clinic_id = ? AND date(date_facture) >= ? AND statut = 'paye'",
        (clinic_id, debut_mois), one=True)["c"]
    pct_paiements = round((factures_payees_mois / total_factures_mois) * 100) if total_factures_mois else 100

    return render_template(
        "dashboard.html",
        patients_aujourdhui=patients_aujourdhui,
        patients_mois=patients_mois,
        total_patients=total_patients,
        rdv_aujourdhui=rdv_aujourdhui,
        revenu_jour=revenu_jour,
        revenu_mois=revenu_mois,
        depenses_mois=depenses_mois,
        profit_mois=revenu_mois - depenses_mois,
        impayes=impayes,
        stock_bas=stock_bas,
        perimes=perimes,
        prochains_rdv=prochains_rdv,
        notifications_recentes=notifications_recentes,
        labels_semaine=labels_semaine,
        revenus_semaine=revenus_semaine,
        repartition_statuts=repartition_statuts,
        pct_objectif_revenu=pct_objectif_revenu,
        pct_consultations_jour=pct_consultations_jour,
        pct_stock_ok=pct_stock_ok,
        pct_paiements=pct_paiements,
    )
