"""Fonctions Python prédéfinies exécutant des opérations sur la base de
données réelle de la clinique. Le NLP ne construit jamais de SQL : il ne
fait qu'appeler ces fonctions avec des paramètres validés.
"""
from datetime import date

from app.db import query_db, execute_db
from app.utils.security import log_action, notify_clinic
from app.utils.helpers import STATUT_RDV_COULEURS


# ---------------------------------------------------------------- Patients
def get_patient_info(patient_id, clinic_id):
    return query_db(
        "SELECT * FROM patients WHERE id = ? AND clinic_id = ?", (patient_id, clinic_id), one=True
    )


# ------------------------------------------------------------- Rendez-vous
def get_appointments(clinic_id, patient_id=None, on_date=None):
    where = "WHERE r.clinic_id = ?"
    params = [clinic_id]
    if patient_id:
        where += " AND r.patient_id = ?"
        params.append(patient_id)
    if on_date:
        where += " AND r.date_rdv = ?"
        params.append(on_date.isoformat())
    return query_db(
        f"SELECT r.*, p.prenom, p.nom FROM rendez_vous r "
        f"JOIN patients p ON p.id = r.patient_id {where} "
        f"AND r.statut != 'annule' ORDER BY r.date_rdv, r.heure_rdv",
        params,
    )


def find_conflict(clinic_id, on_date, heure, exclude_id=None):
    q = ("SELECT r.*, p.prenom, p.nom FROM rendez_vous r JOIN patients p ON p.id = r.patient_id "
         "WHERE r.clinic_id = ? AND r.date_rdv = ? AND r.heure_rdv = ? AND r.statut != 'annule'")
    params = [clinic_id, on_date.isoformat(), heure]
    if exclude_id:
        q += " AND r.id != ?"
        params.append(exclude_id)
    return query_db(q, params, one=True)


def create_appointment(clinic_id, user_id, patient_id, on_date, heure, motif=None):
    couleur = STATUT_RDV_COULEURS.get("planifie")
    rdv_id = execute_db(
        "INSERT INTO rendez_vous (clinic_id, patient_id, medecin_id, date_rdv, heure_rdv, motif, statut, couleur) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (clinic_id, patient_id, user_id, on_date.isoformat(), heure, motif or "Assistant IA", "planifie", couleur),
    )
    log_action("creation_rdv_assistant", f"Rendez-vous créé via l'assistant pour le {on_date} à {heure}")
    return rdv_id


def cancel_appointment(clinic_id, rdv_id):
    rdv = query_db(
        "SELECT r.*, p.prenom, p.nom FROM rendez_vous r JOIN patients p ON p.id = r.patient_id "
        "WHERE r.id = ? AND r.clinic_id = ?", (rdv_id, clinic_id), one=True,
    )
    if not rdv:
        return None
    execute_db(
        "UPDATE rendez_vous SET statut = 'annule', couleur = ? WHERE id = ? AND clinic_id = ?",
        (STATUT_RDV_COULEURS.get("annule"), rdv_id, clinic_id),
    )
    log_action("annulation_rdv_assistant", f"RDV #{rdv_id} annulé via l'assistant")
    return rdv


def reschedule_appointment(clinic_id, rdv_id, new_date, new_heure):
    rdv = query_db("SELECT * FROM rendez_vous WHERE id = ? AND clinic_id = ?", (rdv_id, clinic_id), one=True)
    if not rdv:
        return None
    execute_db(
        "UPDATE rendez_vous SET date_rdv = ?, heure_rdv = ? WHERE id = ? AND clinic_id = ?",
        (new_date.isoformat(), new_heure, rdv_id, clinic_id),
    )
    log_action("deplacement_rdv_assistant", f"RDV #{rdv_id} déplacé au {new_date} {new_heure}")
    return True


# ---------------------------------------------------------------- Rappels
def create_reminder(clinic_id, user_id, titre, on_date, heure=None, patient_id=None):
    rappel_id = execute_db(
        "INSERT INTO rappels (clinic_id, user_id, patient_id, titre, date_rappel, heure_rappel, statut) "
        "VALUES (?,?,?,?,?,?,?)",
        (clinic_id, user_id, patient_id, titre, on_date.isoformat(), heure, "actif"),
    )
    log_action("creation_rappel_assistant", f"Rappel créé via l'assistant : {titre}")
    return rappel_id


def get_reminders(clinic_id, user_id, statut="actif"):
    return query_db(
        "SELECT * FROM rappels WHERE clinic_id = ? AND user_id = ? AND statut = ? "
        "ORDER BY date_rappel, heure_rappel",
        (clinic_id, user_id, statut),
    )


def delete_reminder(clinic_id, rappel_id):
    row = query_db("SELECT * FROM rappels WHERE id = ? AND clinic_id = ?", (rappel_id, clinic_id), one=True)
    if not row:
        return None
    execute_db("DELETE FROM rappels WHERE id = ? AND clinic_id = ?", (rappel_id, clinic_id))
    return row


def complete_reminder(clinic_id, rappel_id):
    row = query_db("SELECT * FROM rappels WHERE id = ? AND clinic_id = ?", (rappel_id, clinic_id), one=True)
    if not row:
        return None
    execute_db("UPDATE rappels SET statut = 'termine' WHERE id = ? AND clinic_id = ?", (rappel_id, clinic_id))
    return row


# --------------------------------------------------------------- Finances
def get_revenue(clinic_id, debut, fin):
    row = query_db(
        "SELECT COALESCE(SUM(montant_paye),0) s FROM factures "
        "WHERE clinic_id = ? AND date(date_facture) BETWEEN ? AND ?",
        (clinic_id, debut.isoformat(), fin.isoformat()), one=True,
    )
    return row["s"] if row else 0


def get_expenses_total(clinic_id, debut, fin):
    row = query_db(
        "SELECT COALESCE(SUM(montant),0) s FROM depenses WHERE clinic_id = ? AND date_depense BETWEEN ? AND ?",
        (clinic_id, debut.isoformat(), fin.isoformat()), one=True,
    )
    return row["s"] if row else 0


def get_profit(clinic_id, debut, fin):
    return get_revenue(clinic_id, debut, fin) - get_expenses_total(clinic_id, debut, fin)


# -------------------------------------------------------------- Inventaire
def search_inventory_all(clinic_id):
    return query_db("SELECT * FROM medicaments WHERE clinic_id = ? ORDER BY nom", (clinic_id,))


def add_inventory_item(clinic_id, nom, quantite):
    existing = query_db(
        "SELECT * FROM medicaments WHERE clinic_id = ? AND lower(nom) = lower(?)", (clinic_id, nom), one=True
    )
    if existing:
        execute_db(
            "UPDATE medicaments SET quantite = quantite + ? WHERE id = ? AND clinic_id = ?",
            (quantite, existing["id"], clinic_id),
        )
        return existing["id"], existing["quantite"] + quantite
    new_id = execute_db(
        "INSERT INTO medicaments (clinic_id, nom, quantite, type_article) VALUES (?,?,?,?)",
        (clinic_id, nom, quantite, "autre"),
    )
    return new_id, quantite


def update_inventory_quantity(clinic_id, item_id, delta):
    item = query_db("SELECT * FROM medicaments WHERE id = ? AND clinic_id = ?", (item_id, clinic_id), one=True)
    if not item:
        return None
    new_qty = max(0, item["quantite"] + delta)
    execute_db("UPDATE medicaments SET quantite = ? WHERE id = ? AND clinic_id = ?", (new_qty, item_id, clinic_id))
    return new_qty


def set_inventory_quantity(clinic_id, item_id, quantite):
    item = query_db("SELECT * FROM medicaments WHERE id = ? AND clinic_id = ?", (item_id, clinic_id), one=True)
    if not item:
        return None
    execute_db("UPDATE medicaments SET quantite = ? WHERE id = ? AND clinic_id = ?",
               (max(0, quantite), item_id, clinic_id))
    return max(0, quantite)
