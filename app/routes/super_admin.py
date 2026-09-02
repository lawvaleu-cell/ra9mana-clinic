from datetime import date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from app.db import query_db, execute_db
from app.utils.security import super_admin_required, validate_csrf

bp = Blueprint("super_admin", __name__, url_prefix="/super-admin")


@bp.route("/connexion", methods=["GET", "POST"])
def login():
    if session.get("super_admin_id"):
        return redirect(url_for("super_admin.dashboard"))

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            flash("Session expirée, veuillez réessayer.", "error")
            return redirect(url_for("super_admin.login"))

        email = request.form.get("email", "").strip().lower()
        mot_de_passe = request.form.get("mot_de_passe", "")
        admin = query_db("SELECT * FROM super_admins WHERE email = ?", (email,), one=True)

        if admin and check_password_hash(admin["mot_de_passe_hash"], mot_de_passe):
            session.clear()
            session["super_admin_id"] = admin["id"]
            session["super_admin_nom"] = admin["nom_complet"]
            session["super_admin_theme"] = admin["theme"] if "theme" in admin.keys() and admin["theme"] else "dark"
            return redirect(url_for("super_admin.dashboard"))

        flash("Identifiants administrateur incorrects.", "error")

    return render_template("super_admin/login.html")


@bp.route("/deconnexion")
def logout():
    session.clear()
    return redirect(url_for("super_admin.login"))


@bp.route("/theme", methods=["POST"])
@super_admin_required
def change_theme():
    from flask import jsonify
    theme = request.form.get("theme") or (request.get_json(silent=True) or {}).get("theme")
    if theme not in ("light", "dark"):
        return jsonify({"ok": False}), 400
    execute_db("UPDATE super_admins SET theme = ? WHERE id = ?", (theme, session["super_admin_id"]))
    session["super_admin_theme"] = theme
    if request.is_json:
        return jsonify({"ok": True, "theme": theme})
    flash("Thème mis à jour.", "success")
    return redirect(request.referrer or url_for("super_admin.dashboard"))


@bp.route("/")
@super_admin_required
def dashboard():
    total_clinics = query_db("SELECT COUNT(*) c FROM clinics", one=True)["c"]
    actives = query_db("SELECT COUNT(*) c FROM clinics WHERE statut = 'actif'", one=True)["c"]
    suspendues = query_db("SELECT COUNT(*) c FROM clinics WHERE statut = 'suspendu'", one=True)["c"]
    essai = query_db("SELECT COUNT(*) c FROM clinics WHERE statut = 'essai'", one=True)["c"]
    total_medecins = query_db("SELECT COUNT(*) c FROM users WHERE role = 'medecin'", one=True)["c"]
    total_patients = query_db("SELECT COUNT(*) c FROM patients", one=True)["c"]

    debut_mois = date.today().replace(day=1)
    nouvelles_ce_mois = query_db(
        "SELECT COUNT(*) c FROM clinics WHERE date(date_creation) >= ?", (debut_mois,), one=True)["c"]

    plus_actives = query_db(
        "SELECT c.id, c.nom_clinique, COUNT(p.id) nb_patients FROM clinics c "
        "LEFT JOIN patients p ON p.clinic_id = c.id GROUP BY c.id ORDER BY nb_patients DESC LIMIT 5")

    croissance = []
    for i in range(5, -1, -1):
        mois_ref = (debut_mois.replace(day=1) - timedelta(days=30 * i))
        debut_m = mois_ref.replace(day=1)
        c = query_db("SELECT COUNT(*) c FROM clinics WHERE date(date_creation) >= ? AND date(date_creation) < date(?, '+1 month')",
                     (debut_m, debut_m), one=True)["c"]
        croissance.append({"mois": debut_m.strftime("%m/%Y"), "count": c})

    return render_template(
        "super_admin/dashboard.html", total_clinics=total_clinics, actives=actives, suspendues=suspendues,
        essai=essai, total_medecins=total_medecins, total_patients=total_patients,
        nouvelles_ce_mois=nouvelles_ce_mois, plus_actives=plus_actives, croissance=croissance,
    )


@bp.route("/cliniques")
@super_admin_required
def clinics_list():
    q = request.args.get("q", "").strip()
    where, params = "", []
    if q:
        where = "WHERE nom_clinique LIKE ? OR nom_medecin LIKE ? OR email LIKE ?"
        like = f"%{q}%"
        params = [like, like, like]
    cliniques = query_db(f"SELECT * FROM clinics {where} ORDER BY date_creation DESC", params)
    return render_template("super_admin/clinics.html", cliniques=cliniques, q=q)


@bp.route("/cliniques/<int:clinic_id>")
@super_admin_required
def clinic_detail(clinic_id):
    clinic = query_db("SELECT * FROM clinics WHERE id = ?", (clinic_id,), one=True)
    if not clinic:
        flash("Clinique introuvable.", "error")
        return redirect(url_for("super_admin.clinics_list"))
    utilisateurs = query_db("SELECT * FROM users WHERE clinic_id = ?", (clinic_id,))
    nb_patients = query_db("SELECT COUNT(*) c FROM patients WHERE clinic_id = ?", (clinic_id,), one=True)["c"]
    return render_template("super_admin/clinic_detail.html", clinic=clinic, utilisateurs=utilisateurs,
                            nb_patients=nb_patients)


@bp.route("/cliniques/<int:clinic_id>/statut", methods=["POST"])
@super_admin_required
def update_clinic_status(clinic_id):
    statut = request.form.get("statut")
    if statut in ("actif", "suspendu", "essai", "expire"):
        execute_db("UPDATE clinics SET statut = ? WHERE id = ?", (statut, clinic_id))
        flash(f"Statut de la clinique mis à jour : {statut}.", "success")
    return redirect(url_for("super_admin.clinic_detail", clinic_id=clinic_id))


@bp.route("/cliniques/<int:clinic_id>/abonnement", methods=["POST"])
@super_admin_required
def update_subscription(clinic_id):
    plan = request.form.get("plan")
    date_expiration = request.form.get("date_expiration") or None
    execute_db("UPDATE clinics SET plan = ?, date_expiration_abonnement = ? WHERE id = ?",
               (plan, date_expiration, clinic_id))
    flash("Abonnement mis à jour.", "success")
    return redirect(url_for("super_admin.clinic_detail", clinic_id=clinic_id))


@bp.route("/cliniques/<int:clinic_id>/reinitialiser-mdp", methods=["POST"])
@super_admin_required
def reset_clinic_password(clinic_id):
    user_id = request.form.get("user_id")
    nouveau_mdp = request.form.get("nouveau_mdp", "")
    if len(nouveau_mdp) < 8:
        flash("Le mot de passe doit contenir au moins 8 caractères.", "error")
    else:
        execute_db("UPDATE users SET mot_de_passe_hash = ? WHERE id = ? AND clinic_id = ?",
                   (generate_password_hash(nouveau_mdp), user_id, clinic_id))
        flash("Mot de passe réinitialisé avec succès.", "success")
    return redirect(url_for("super_admin.clinic_detail", clinic_id=clinic_id))


@bp.route("/cliniques/<int:clinic_id>/modifier", methods=["POST"])
@super_admin_required
def edit_clinic(clinic_id):
    f = request.form
    execute_db(
        "UPDATE clinics SET nom_clinique=?, nom_medecin=?, email=?, telephone=? WHERE id=?",
        (f.get("nom_clinique"), f.get("nom_medecin"), f.get("email"), f.get("telephone"), clinic_id),
    )
    flash("Informations de la clinique mises à jour.", "success")
    return redirect(url_for("super_admin.clinic_detail", clinic_id=clinic_id))


@bp.route("/cliniques/<int:clinic_id>/supprimer", methods=["POST"])
@super_admin_required
def delete_clinic(clinic_id):
    execute_db("DELETE FROM clinics WHERE id = ?", (clinic_id,))
    flash("Clinique et toutes ses données supprimées définitivement.", "success")
    return redirect(url_for("super_admin.clinics_list"))


# ---------------- ANNONCES GLOBALES ----------------

@bp.route("/annonces", methods=["GET", "POST"])
@super_admin_required
def announcements():
    if request.method == "POST":
        f = request.form
        cible = f.get("cible")
        clinic_id = f.get("clinic_id") if cible == "specifique" else None
        execute_db(
            "INSERT INTO annonces_globales (titre, message, type, cible, clinic_id) VALUES (?,?,?,?,?)",
            (f["titre"], f["message"], f["type"], "toutes" if cible != "specifique" else "specifique", clinic_id),
        )
        # Pousse une notification à tous les utilisateurs concernés
        if cible == "specifique" and clinic_id:
            utilisateurs = query_db("SELECT id FROM users WHERE clinic_id = ?", (clinic_id,))
        else:
            utilisateurs = query_db("SELECT id FROM users")
        for u in utilisateurs:
            execute_db(
                "INSERT INTO notifications (clinic_id, user_id, titre, message, type) "
                "SELECT clinic_id, id, ?, ?, 'systeme' FROM users WHERE id = ?",
                (f["titre"], f["message"], u["id"]),
            )
        flash("Annonce diffusée avec succès.", "success")
        return redirect(url_for("super_admin.announcements"))

    annonces = query_db(
        "SELECT a.*, c.nom_clinique FROM annonces_globales a LEFT JOIN clinics c ON c.id = a.clinic_id "
        "ORDER BY a.date_creation DESC LIMIT 50")
    cliniques = query_db("SELECT id, nom_clinique FROM clinics ORDER BY nom_clinique")
    return render_template("super_admin/announcements.html", annonces=annonces, cliniques=cliniques)


# ---------------- PAIEMENTS D'ABONNEMENT ----------------

PLAN_PRIX_DEFAUT = {"essai_gratuit": 0, "mensuel": 3500, "annuel": 35000}


@bp.route("/paiements")
@super_admin_required
def payments():
    today = date.today()
    debut_mois = today.replace(day=1)
    debut_annee = today.replace(month=1, day=1)

    cliniques = query_db(
        "SELECT c.*, "
        "(SELECT COUNT(*) FROM paiements_abonnement WHERE clinic_id = c.id) AS nb_paiements, "
        "(SELECT numero_facture FROM paiements_abonnement WHERE clinic_id = c.id ORDER BY date_paiement DESC LIMIT 1) AS derniere_facture, "
        "(SELECT date_paiement FROM paiements_abonnement WHERE clinic_id = c.id ORDER BY date_paiement DESC LIMIT 1) AS dernier_paiement "
        "FROM clinics c ORDER BY c.date_creation DESC"
    )

    cliniques_enrichies = []
    for c in cliniques:
        c = dict(c)
        if c.get("date_expiration_abonnement"):
            try:
                exp = date.fromisoformat(str(c["date_expiration_abonnement"]))
                c["jours_restants"] = (exp - today).days
            except (ValueError, TypeError):
                c["jours_restants"] = None
        else:
            c["jours_restants"] = None
        cliniques_enrichies.append(c)

    revenu_total = query_db(
        "SELECT COALESCE(SUM(montant),0) s FROM paiements_abonnement WHERE statut = 'paye'", one=True)["s"]
    revenu_mois = query_db(
        "SELECT COALESCE(SUM(montant),0) s FROM paiements_abonnement WHERE statut = 'paye' AND date_paiement >= ?",
        (debut_mois,), one=True)["s"]
    revenu_annee = query_db(
        "SELECT COALESCE(SUM(montant),0) s FROM paiements_abonnement WHERE statut = 'paye' AND date_paiement >= ?",
        (debut_annee,), one=True)["s"]
    mois_precedent = (debut_mois - timedelta(days=1)).replace(day=1)
    revenu_mois_precedent = query_db(
        "SELECT COALESCE(SUM(montant),0) s FROM paiements_abonnement WHERE statut = 'paye' AND date_paiement >= ? AND date_paiement < ?",
        (mois_precedent, debut_mois), one=True)["s"]
    croissance = 0
    if revenu_mois_precedent > 0:
        croissance = round(((revenu_mois - revenu_mois_precedent) / revenu_mois_precedent) * 100, 1)

    revenu_par_plan = query_db(
        "SELECT plan, COALESCE(SUM(montant),0) s FROM paiements_abonnement WHERE statut = 'paye' GROUP BY plan")

    comptes_payes = query_db(
        "SELECT COUNT(*) c FROM clinics WHERE statut_paiement = 'paye' AND "
        "(date_expiration_abonnement IS NULL OR date_expiration_abonnement >= ?)", (today,), one=True)["c"]
    comptes_expires = query_db(
        "SELECT COUNT(*) c FROM clinics WHERE date_expiration_abonnement IS NOT NULL AND date_expiration_abonnement < ?",
        (today,), one=True)["c"]
    paiements_attente = query_db(
        "SELECT COUNT(*) c FROM clinics WHERE statut_paiement = 'en_attente'", one=True)["c"]

    historique_mois = []
    for i in range(5, -1, -1):
        mois_ref = (debut_mois.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
        s = query_db(
            "SELECT COALESCE(SUM(montant),0) s FROM paiements_abonnement WHERE statut='paye' AND date_paiement >= ? AND date_paiement < date(?, '+1 month')",
            (mois_ref, mois_ref), one=True)["s"]
        historique_mois.append({"mois": mois_ref.strftime("%m/%Y"), "montant": s})

    return render_template(
        "super_admin/payments.html", cliniques=cliniques_enrichies, revenu_total=revenu_total,
        revenu_mois=revenu_mois, revenu_annee=revenu_annee, croissance=croissance,
        revenu_par_plan=revenu_par_plan, comptes_payes=comptes_payes, comptes_expires=comptes_expires,
        paiements_attente=paiements_attente, historique_mois=historique_mois, plan_prix=PLAN_PRIX_DEFAUT,
    )


@bp.route("/cliniques/<int:clinic_id>/paiements")
@super_admin_required
def clinic_payments(clinic_id):
    clinic = query_db("SELECT * FROM clinics WHERE id = ?", (clinic_id,), one=True)
    if not clinic:
        flash("Clinique introuvable.", "error")
        return redirect(url_for("super_admin.payments"))
    paiements = query_db(
        "SELECT * FROM paiements_abonnement WHERE clinic_id = ? ORDER BY date_paiement DESC", (clinic_id,))
    return render_template("super_admin/clinic_payments.html", clinic=clinic, paiements=paiements,
                            plan_prix=PLAN_PRIX_DEFAUT, today=date.today().isoformat())


@bp.route("/cliniques/<int:clinic_id>/paiements/nouveau", methods=["POST"])
@super_admin_required
def add_payment(clinic_id):
    f = request.form
    plan = f.get("plan", "mensuel")
    montant = float(f.get("montant") or PLAN_PRIX_DEFAUT.get(plan, 0))
    methode = f.get("methode_paiement", "virement")
    numero_facture = f.get("numero_facture") or f"AB-{clinic_id:03d}-{date.today().strftime('%Y%m%d%H%M%S')}"
    statut = f.get("statut", "paye")
    date_paiement = f.get("date_paiement") or date.today().isoformat()

    if plan == "annuel":
        prochaine = (date.fromisoformat(date_paiement) + timedelta(days=365)).isoformat()
    else:
        prochaine = (date.fromisoformat(date_paiement) + timedelta(days=30)).isoformat()

    execute_db(
        "INSERT INTO paiements_abonnement (clinic_id, montant, plan, methode_paiement, numero_facture, statut, "
        "date_paiement, prochaine_echeance) VALUES (?,?,?,?,?,?,?,?)",
        (clinic_id, montant, plan, methode, numero_facture, statut, date_paiement, prochaine),
    )

    if statut == "paye":
        execute_db(
            "UPDATE clinics SET plan = ?, prix_abonnement = ?, statut_paiement = 'paye', methode_paiement = ?, "
            "date_expiration_abonnement = ?, statut = 'actif' WHERE id = ?",
            (plan, montant, methode, prochaine, clinic_id),
        )
    else:
        execute_db("UPDATE clinics SET statut_paiement = ? WHERE id = ?", (statut, clinic_id))

    flash("Paiement enregistré avec succès.", "success")
    return redirect(url_for("super_admin.clinic_payments", clinic_id=clinic_id))


# ---------------- CONTENU DU SITE PUBLIC ----------------

@bp.route("/site", methods=["GET", "POST"])
@super_admin_required
def site_content():
    if request.method == "POST":
        for cle, valeur in request.form.items():
            if cle == "csrf_token":
                continue
            existe = query_db("SELECT cle FROM site_contenu WHERE cle = ?", (cle,), one=True)
            if existe:
                execute_db("UPDATE site_contenu SET valeur = ? WHERE cle = ?", (valeur, cle))
            else:
                execute_db("INSERT INTO site_contenu (cle, valeur) VALUES (?, ?)", (cle, valeur))

        import os, uuid
        from flask import current_app
        for champ in ("logo_plateforme", "fond_connexion", "fond_inscription", "fond_landing"):
            fichier = request.files.get(champ)
            if fichier and fichier.filename:
                ext = os.path.splitext(fichier.filename)[1].lower()
                if ext in (".png", ".jpg", ".jpeg", ".webp", ".svg"):
                    filename = f"{uuid.uuid4().hex}{ext}"
                    path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
                    fichier.save(path)
                    existe = query_db("SELECT cle FROM site_contenu WHERE cle = ?", (champ,), one=True)
                    if existe:
                        execute_db("UPDATE site_contenu SET valeur = ? WHERE cle = ?", (path, champ))
                    else:
                        execute_db("INSERT INTO site_contenu (cle, valeur) VALUES (?, ?)", (champ, path))

        flash("Contenu du site mis à jour avec succès.", "success")
        return redirect(url_for("super_admin.site_content"))

    rows = query_db("SELECT cle, valeur FROM site_contenu")
    content = {r["cle"]: r["valeur"] for r in rows}
    return render_template("super_admin/site_content.html", content=content)


@bp.route("/publicites")
@super_admin_required
def ads_list():
    ads = query_db("SELECT * FROM site_publicites ORDER BY ordre ASC, id DESC")
    return render_template("super_admin/ads.html", ads=ads)


@bp.route("/publicites/nouveau", methods=["GET", "POST"])
@super_admin_required
def ads_create():
    if request.method == "POST":
        f = request.form
        image_path = None
        image_file = request.files.get("image")
        if image_file and image_file.filename:
            import os, uuid
            from flask import current_app
            ext = os.path.splitext(image_file.filename)[1].lower()
            if ext in (".png", ".jpg", ".jpeg", ".webp"):
                filename = f"{uuid.uuid4().hex}{ext}"
                path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
                image_file.save(path)
                image_path = path

        execute_db(
            "INSERT INTO site_publicites (titre, description, image_path, lien_url, texte_bouton, actif, ordre, date_debut, date_fin) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (f.get("titre"), f.get("description"), image_path, f.get("lien_url"),
             f.get("texte_bouton") or "En savoir plus", 1 if f.get("actif") == "on" else 0,
             f.get("ordre") or 0, f.get("date_debut") or None, f.get("date_fin") or None),
        )
        flash("Publicité créée avec succès.", "success")
        return redirect(url_for("super_admin.ads_list"))

    return render_template("super_admin/ad_form.html", ad={}, mode="create")


@bp.route("/publicites/<int:ad_id>/modifier", methods=["GET", "POST"])
@super_admin_required
def ads_edit(ad_id):
    ad = query_db("SELECT * FROM site_publicites WHERE id = ?", (ad_id,), one=True)
    if not ad:
        flash("Publicité introuvable.", "error")
        return redirect(url_for("super_admin.ads_list"))

    if request.method == "POST":
        f = request.form
        image_path = ad["image_path"]
        image_file = request.files.get("image")
        if image_file and image_file.filename:
            import os, uuid
            from flask import current_app
            ext = os.path.splitext(image_file.filename)[1].lower()
            if ext in (".png", ".jpg", ".jpeg", ".webp"):
                filename = f"{uuid.uuid4().hex}{ext}"
                path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
                image_file.save(path)
                image_path = path

        execute_db(
            "UPDATE site_publicites SET titre=?, description=?, image_path=?, lien_url=?, texte_bouton=?, "
            "actif=?, ordre=?, date_debut=?, date_fin=? WHERE id=?",
            (f.get("titre"), f.get("description"), image_path, f.get("lien_url"),
             f.get("texte_bouton") or "En savoir plus", 1 if f.get("actif") == "on" else 0,
             f.get("ordre") or 0, f.get("date_debut") or None, f.get("date_fin") or None, ad_id),
        )
        flash("Publicité mise à jour.", "success")
        return redirect(url_for("super_admin.ads_list"))

    return render_template("super_admin/ad_form.html", ad=ad, mode="edit")


@bp.route("/publicites/<int:ad_id>/supprimer", methods=["POST"])
@super_admin_required
def ads_delete(ad_id):
    execute_db("DELETE FROM site_publicites WHERE id = ?", (ad_id,))
    flash("Publicité supprimée.", "success")
    return redirect(url_for("super_admin.ads_list"))


# ---------------- SUPPORT / COMMUNICATION ----------------

@bp.route("/support")
@super_admin_required
def support_inbox():
    q = request.args.get("q", "").strip()
    statut = request.args.get("statut", "")
    where, params = "", []
    conditions = []
    if q:
        conditions.append("t.sujet LIKE ?")
        params.append(f"%{q}%")
    if statut:
        conditions.append("t.statut = ?")
        params.append(statut)
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    tickets = query_db(
        f"SELECT t.*, c.nom_clinique, "
        "(SELECT message FROM ticket_messages WHERE ticket_id = t.id ORDER BY date_creation DESC LIMIT 1) AS dernier_message "
        f"FROM tickets_support t LEFT JOIN clinics c ON c.id = t.clinic_id {where} "
        "ORDER BY t.epingle DESC, t.date_maj DESC", params)

    non_lus = query_db("SELECT COUNT(*) c FROM tickets_support WHERE non_lu_admin = 1", one=True)["c"]
    return render_template("super_admin/support.html", tickets=tickets, q=q, statut=statut, non_lus=non_lus)


@bp.route("/support/<int:ticket_id>")
@super_admin_required
def support_thread(ticket_id):
    ticket = query_db(
        "SELECT t.*, c.nom_clinique FROM tickets_support t LEFT JOIN clinics c ON c.id = t.clinic_id WHERE t.id = ?",
        (ticket_id,), one=True)
    if not ticket:
        flash("Conversation introuvable.", "error")
        return redirect(url_for("super_admin.support_inbox"))
    execute_db("UPDATE tickets_support SET non_lu_admin = 0 WHERE id = ?", (ticket_id,))
    messages = query_db("SELECT * FROM ticket_messages WHERE ticket_id = ? ORDER BY date_creation ASC", (ticket_id,))
    return render_template("super_admin/support_thread.html", ticket=ticket, messages=messages)


@bp.route("/support/<int:ticket_id>/repondre", methods=["POST"])
@super_admin_required
def support_reply(ticket_id):
    message = request.form.get("message", "").strip()
    if message:
        execute_db(
            "INSERT INTO ticket_messages (ticket_id, auteur, auteur_nom, message) VALUES (?,?,?,?)",
            (ticket_id, "admin", session.get("super_admin_nom", "Support"), message),
        )
        execute_db(
            "UPDATE tickets_support SET non_lu_clinique = 1, non_lu_admin = 0, date_maj = CURRENT_TIMESTAMP WHERE id = ?",
            (ticket_id,))
        ticket = query_db("SELECT clinic_id, sujet FROM tickets_support WHERE id = ?", (ticket_id,), one=True)
        if ticket and ticket["clinic_id"]:
            from app.utils.security import notify_clinic
            notify_clinic(ticket["clinic_id"], "Réponse du support",
                          f"Nouvelle réponse sur « {ticket['sujet']} »", "info", "normale", "support")
    return redirect(url_for("super_admin.support_thread", ticket_id=ticket_id))


@bp.route("/support/<int:ticket_id>/statut", methods=["POST"])
@super_admin_required
def support_update_status(ticket_id):
    statut = request.form.get("statut")
    if statut in ("ouvert", "resolu", "archive"):
        execute_db("UPDATE tickets_support SET statut = ? WHERE id = ?", (statut, ticket_id))
        flash(f"Conversation marquée comme « {statut} ».", "success")
    return redirect(url_for("super_admin.support_thread", ticket_id=ticket_id))


@bp.route("/support/<int:ticket_id>/epingler", methods=["POST"])
@super_admin_required
def support_toggle_pin(ticket_id):
    t = query_db("SELECT epingle FROM tickets_support WHERE id = ?", (ticket_id,), one=True)
    if t:
        execute_db("UPDATE tickets_support SET epingle = ? WHERE id = ?", (0 if t["epingle"] else 1, ticket_id))
    return redirect(request.referrer or url_for("super_admin.support_inbox"))


@bp.route("/support/<int:ticket_id>/marquer-non-lu", methods=["POST"])
@super_admin_required
def support_mark_unread(ticket_id):
    execute_db("UPDATE tickets_support SET non_lu_admin = 1 WHERE id = ?", (ticket_id,))
    return redirect(url_for("super_admin.support_inbox"))


# ---------------- GESTION LOGICIEL ----------------

@bp.route("/logiciel", methods=["GET", "POST"])
@super_admin_required
def software():
    if request.method == "POST":
        valeurs = {
            "mode_maintenance": "1" if request.form.get("mode_maintenance") == "1" else "0",
            "version_application": request.form.get("version_application", ""),
            "notes_version": request.form.get("notes_version", ""),
        }
        for cle, valeur in valeurs.items():
            existe = query_db("SELECT cle FROM parametres_logiciel WHERE cle = ?", (cle,), one=True)
            if existe:
                execute_db("UPDATE parametres_logiciel SET valeur = ? WHERE cle = ?", (valeur, cle))
            else:
                execute_db("INSERT INTO parametres_logiciel (cle, valeur) VALUES (?, ?)", (cle, valeur))
        flash("Paramètres logiciels mis à jour.", "success")
        return redirect(url_for("super_admin.software"))

    parametres = {row["cle"]: row["valeur"] for row in query_db("SELECT * FROM parametres_logiciel")}
    return render_template("super_admin/software.html", parametres=parametres)


# ---------------- LOGS ----------------

@bp.route("/logs")
@super_admin_required
def logs():
    connexions = query_db(
        "SELECT * FROM tentatives_connexion ORDER BY date_creation DESC LIMIT 100")
    audit = query_db(
        "SELECT a.*, c.nom_clinique, u.nom_complet FROM audit_log a "
        "LEFT JOIN clinics c ON c.id = a.clinic_id LEFT JOIN users u ON u.id = a.user_id "
        "ORDER BY a.date_creation DESC LIMIT 100")
    echecs = query_db(
        "SELECT COUNT(*) c FROM tentatives_connexion WHERE succes = 0 AND date_creation >= datetime('now','-1 day')",
        one=True)["c"]
    return render_template("super_admin/logs.html", connexions=connexions, audit=audit, echecs_24h=echecs)
