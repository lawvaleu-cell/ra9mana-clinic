from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify

from app.db import query_db, execute_db
from app.utils.security import login_required, validate_csrf, log_action

bp = Blueprint("support", __name__, url_prefix="/support")


@bp.route("/")
@login_required
def list_tickets():
    clinic_id = session["clinic_id"]
    tickets = query_db(
        "SELECT t.*, (SELECT message FROM ticket_messages WHERE ticket_id = t.id ORDER BY date_creation DESC LIMIT 1) AS dernier_message "
        "FROM tickets_support t WHERE t.clinic_id = ? ORDER BY t.date_maj DESC", (clinic_id,))
    return render_template("support/list.html", tickets=tickets)


@bp.route("/nouveau", methods=["GET", "POST"])
@login_required
def create_ticket():
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            flash("Session expirée, veuillez réessayer.", "error")
            return redirect(url_for("support.create_ticket"))

        sujet = request.form.get("sujet", "").strip()
        message = request.form.get("message", "").strip()
        if not sujet or not message:
            flash("Le sujet et le message sont obligatoires.", "error")
            return render_template("support/form.html")

        ticket_id = execute_db(
            "INSERT INTO tickets_support (clinic_id, sujet, non_lu_admin, non_lu_clinique) VALUES (?,?,1,0)",
            (session["clinic_id"], sujet),
        )
        execute_db(
            "INSERT INTO ticket_messages (ticket_id, auteur, auteur_nom, message) VALUES (?,?,?,?)",
            (ticket_id, "clinique", session.get("user_id") and query_db(
                "SELECT nom_complet FROM users WHERE id = ?", (session["user_id"],), one=True)["nom_complet"], message),
        )
        log_action("creation_ticket_support", f"Ticket support créé : {sujet}")
        flash("Votre message a été envoyé à notre équipe support.", "success")
        return redirect(url_for("support.view_ticket", ticket_id=ticket_id))

    return render_template("support/form.html")


@bp.route("/<int:ticket_id>")
@login_required
def view_ticket(ticket_id):
    clinic_id = session["clinic_id"]
    ticket = query_db("SELECT * FROM tickets_support WHERE id = ? AND clinic_id = ?", (ticket_id, clinic_id), one=True)
    if not ticket:
        flash("Conversation introuvable.", "error")
        return redirect(url_for("support.list_tickets"))
    execute_db("UPDATE tickets_support SET non_lu_clinique = 0 WHERE id = ?", (ticket_id,))
    messages = query_db("SELECT * FROM ticket_messages WHERE ticket_id = ? ORDER BY date_creation ASC", (ticket_id,))
    return render_template("support/thread.html", ticket=ticket, messages=messages)


@bp.route("/<int:ticket_id>/messages")
@login_required
def poll_messages(ticket_id):
    clinic_id = session["clinic_id"]
    ticket = query_db("SELECT * FROM tickets_support WHERE id = ? AND clinic_id = ?", (ticket_id, clinic_id), one=True)
    if not ticket:
        return jsonify({"ok": False}), 404
    execute_db("UPDATE tickets_support SET non_lu_clinique = 0 WHERE id = ?", (ticket_id,))
    messages = query_db("SELECT * FROM ticket_messages WHERE ticket_id = ? ORDER BY date_creation ASC", (ticket_id,))
    return jsonify({"ok": True, "statut": ticket["statut"], "messages": [
        {"auteur": m["auteur"], "auteur_nom": m["auteur_nom"], "message": m["message"],
         "date": m["date_creation"] if isinstance(m["date_creation"], str) else str(m["date_creation"])}
        for m in messages
    ]})


@bp.route("/<int:ticket_id>/repondre", methods=["POST"])
@login_required
def reply_ticket(ticket_id):
    clinic_id = session["clinic_id"]
    ticket = query_db("SELECT * FROM tickets_support WHERE id = ? AND clinic_id = ?", (ticket_id, clinic_id), one=True)
    if not ticket:
        flash("Conversation introuvable.", "error")
        return redirect(url_for("support.list_tickets"))
    if not validate_csrf(request.form.get("csrf_token")):
        flash("Session expirée, veuillez réessayer.", "error")
        return redirect(url_for("support.view_ticket", ticket_id=ticket_id))

    message = request.form.get("message", "").strip()
    if message:
        user = query_db("SELECT nom_complet FROM users WHERE id = ?", (session["user_id"],), one=True)
        execute_db(
            "INSERT INTO ticket_messages (ticket_id, auteur, auteur_nom, message) VALUES (?,?,?,?)",
            (ticket_id, "clinique", user["nom_complet"] if user else "", message),
        )
        execute_db(
            "UPDATE tickets_support SET non_lu_admin = 1, non_lu_clinique = 0, statut = 'ouvert', "
            "date_maj = CURRENT_TIMESTAMP WHERE id = ?", (ticket_id,))
    return redirect(url_for("support.view_ticket", ticket_id=ticket_id))
