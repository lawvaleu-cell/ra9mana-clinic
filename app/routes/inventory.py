from datetime import date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from app.db import query_db, execute_db
from app.utils.security import login_required, validate_csrf, log_action, notify_clinic

bp = Blueprint("inventory", __name__, url_prefix="/inventaire")

TYPES_ARTICLE = {
    "medicament": "Médicament",
    "equipement": "Équipement médical",
    "fourniture": "Fourniture de bureau",
    "consommable": "Consommable",
    "mobilier": "Mobilier",
    "informatique": "Informatique",
    "nettoyage": "Produit de nettoyage",
    "autre": "Autre",
}

TYPES_MOUVEMENT = {
    "entree": "Entrée de stock",
    "sortie": "Sortie de stock",
    "usage_interne": "Usage interne",
    "ajustement": "Ajustement",
    "perte": "Perte",
    "expire": "Expiré",
    "endommage": "Endommagé",
    "retour": "Retour",
}


@bp.route("/")
@login_required
def list_medicines():
    clinic_id = session["clinic_id"]
    q = request.args.get("q", "").strip()
    filtre = request.args.get("filtre", "")
    type_article = request.args.get("type", "")

    where = "WHERE clinic_id = ?"
    params = [clinic_id]
    if q:
        where += " AND (nom LIKE ? OR categorie LIKE ? OR fournisseur LIKE ?)"
        like = f"%{q}%"
        params += [like, like, like]
    if type_article:
        where += " AND type_article = ?"
        params.append(type_article)
    if filtre == "stock_bas":
        where += " AND quantite <= quantite_min"
    elif filtre == "expire":
        where += " AND date_expiration IS NOT NULL AND date_expiration <= date('now')"
    elif filtre == "bientot_expire":
        limite = (date.today() + timedelta(days=60)).isoformat()
        where += f" AND date_expiration IS NOT NULL AND date_expiration <= '{limite}' AND date_expiration > date('now')"

    medicaments = query_db(f"SELECT * FROM medicaments {where} ORDER BY nom", params)

    stats = {
        "total": query_db("SELECT COUNT(*) c FROM medicaments WHERE clinic_id = ?", (clinic_id,), one=True)["c"],
        "stock_bas": query_db("SELECT COUNT(*) c FROM medicaments WHERE clinic_id = ? AND quantite <= quantite_min",
                               (clinic_id,), one=True)["c"],
        "expire": query_db(
            "SELECT COUNT(*) c FROM medicaments WHERE clinic_id = ? AND date_expiration IS NOT NULL AND date_expiration <= date('now')",
            (clinic_id,), one=True)["c"],
    }

    return render_template("inventory/list.html", medicaments=medicaments, q=q, filtre=filtre, stats=stats,
                            today_iso=date.today().isoformat(), types_article=TYPES_ARTICLE, type_article=type_article)


@bp.route("/nouveau", methods=["GET", "POST"])
@login_required
def create_medicine():
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            flash("Session expirée, veuillez réessayer.", "error")
            return redirect(url_for("inventory.create_medicine"))
        f = request.form
        execute_db(
            "INSERT INTO medicaments (clinic_id, nom, categorie, fournisseur, prix_achat, prix_vente, quantite, "
            "quantite_min, date_expiration, code_barre, type_article, emplacement, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (session["clinic_id"], f["nom"], f.get("categorie"), f.get("fournisseur"),
             f.get("prix_achat") or 0, f.get("prix_vente") or None, f.get("quantite") or 0,
             f.get("quantite_min") or 10, f.get("date_expiration") or None, f.get("code_barre"),
             f.get("type_article") or "medicament", f.get("emplacement"), f.get("notes")),
        )
        log_action("ajout_article_stock", f"Article ajouté au stock : {f['nom']}")
        flash("Article ajouté au stock.", "success")
        return redirect(url_for("inventory.list_medicines"))
    return render_template("inventory/form.html", medicament={}, mode="create", types_article=TYPES_ARTICLE)


@bp.route("/<int:med_id>/modifier", methods=["GET", "POST"])
@login_required
def edit_medicine(med_id):
    clinic_id = session["clinic_id"]
    medicament = query_db("SELECT * FROM medicaments WHERE id = ? AND clinic_id = ?", (med_id, clinic_id), one=True)
    if not medicament:
        flash("Article introuvable.", "error")
        return redirect(url_for("inventory.list_medicines"))

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            flash("Session expirée, veuillez réessayer.", "error")
            return redirect(url_for("inventory.edit_medicine", med_id=med_id))
        f = request.form
        execute_db(
            "UPDATE medicaments SET nom=?, categorie=?, fournisseur=?, prix_achat=?, prix_vente=?, quantite=?, "
            "quantite_min=?, date_expiration=?, code_barre=?, type_article=?, emplacement=?, notes=? WHERE id=? AND clinic_id=?",
            (f["nom"], f.get("categorie"), f.get("fournisseur"), f.get("prix_achat") or 0,
             f.get("prix_vente") or None, f.get("quantite") or 0, f.get("quantite_min") or 10,
             f.get("date_expiration") or None, f.get("code_barre"), f.get("type_article") or "medicament",
             f.get("emplacement"), f.get("notes"), med_id, clinic_id),
        )
        log_action("modification_article_stock", f"Article modifié : {f['nom']}")
        flash("Article mis à jour.", "success")
        return redirect(url_for("inventory.list_medicines"))

    mouvements = query_db(
        "SELECT m.*, u.nom_complet FROM mouvements_stock m LEFT JOIN users u ON u.id = m.utilisateur_id "
        "WHERE m.article_id = ? ORDER BY m.date_creation DESC LIMIT 30", (med_id,))
    return render_template("inventory/form.html", medicament=medicament, mode="edit", types_article=TYPES_ARTICLE,
                            types_mouvement=TYPES_MOUVEMENT, mouvements=mouvements)


@bp.route("/<int:med_id>/mouvement", methods=["POST"])
@login_required
def add_movement(med_id):
    clinic_id = session["clinic_id"]
    article = query_db("SELECT * FROM medicaments WHERE id = ? AND clinic_id = ?", (med_id, clinic_id), one=True)
    if not article:
        flash("Article introuvable.", "error")
        return redirect(url_for("inventory.list_medicines"))
    if not validate_csrf(request.form.get("csrf_token")):
        flash("Session expirée, veuillez réessayer.", "error")
        return redirect(url_for("inventory.edit_medicine", med_id=med_id))

    f = request.form
    type_mouvement = f.get("type_mouvement", "ajustement")
    quantite = int(f.get("quantite") or 0)
    motif = f.get("motif", "")

    if type_mouvement in ("entree", "retour"):
        nouvelle_quantite = article["quantite"] + quantite
    elif type_mouvement in ("sortie", "usage_interne", "perte", "expire", "endommage"):
        nouvelle_quantite = max(0, article["quantite"] - quantite)
    else:  # ajustement : la quantité saisie devient la nouvelle quantité
        nouvelle_quantite = quantite

    execute_db("UPDATE medicaments SET quantite = ? WHERE id = ?", (nouvelle_quantite, med_id))
    execute_db(
        "INSERT INTO mouvements_stock (clinic_id, article_id, type_mouvement, quantite, motif, utilisateur_id) "
        "VALUES (?,?,?,?,?,?)",
        (clinic_id, med_id, type_mouvement, quantite, motif, session["user_id"]),
    )
    log_action("mouvement_stock", f"{TYPES_MOUVEMENT.get(type_mouvement, type_mouvement)} — {article['nom']} ({quantite})")
    if nouvelle_quantite <= article["quantite_min"]:
        notify_clinic(clinic_id, "Stock bas",
                      f"{article['nom']} — quantité restante : {nouvelle_quantite}", "alerte", "haute", "stock")
    flash("Mouvement de stock enregistré.", "success")
    return redirect(url_for("inventory.edit_medicine", med_id=med_id))


@bp.route("/<int:med_id>/supprimer", methods=["POST"])
@login_required
def delete_medicine(med_id):
    clinic_id = session["clinic_id"]
    if validate_csrf(request.form.get("csrf_token")):
        execute_db("DELETE FROM medicaments WHERE id = ? AND clinic_id = ?", (med_id, clinic_id))
        log_action("suppression_article_stock", f"Article #{med_id} supprimé")
        flash("Article supprimé.", "success")
    return redirect(url_for("inventory.list_medicines"))
