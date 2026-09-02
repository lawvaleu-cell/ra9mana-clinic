from flask import Blueprint, render_template, redirect, url_for, session, request, jsonify

from app.db import query_db, execute_db
from app.utils.security import login_required, validate_csrf

bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@bp.route("/")
@login_required
def list_notifications():
    q = request.args.get("q", "").strip()
    categorie = request.args.get("categorie", "")
    priorite = request.args.get("priorite", "")
    statut = request.args.get("statut", "")

    where = "WHERE user_id = ?"
    params = [session["user_id"]]
    if q:
        where += " AND (titre LIKE ? OR message LIKE ?)"
        like = f"%{q}%"
        params += [like, like]
    if categorie:
        where += " AND categorie = ?"
        params.append(categorie)
    if priorite:
        where += " AND priorite = ?"
        params.append(priorite)
    if statut == "non_lu":
        where += " AND lu = 0"
    elif statut == "lu":
        where += " AND lu = 1"

    notifs = query_db(f"SELECT * FROM notifications {where} ORDER BY date_creation DESC LIMIT 150", params)
    categories = query_db("SELECT DISTINCT categorie FROM notifications WHERE user_id = ?", (session["user_id"],))
    return render_template("notifications.html", notifications=notifs, q=q, categorie=categorie,
                            priorite=priorite, statut=statut, categories=[c["categorie"] for c in categories])


@bp.route("/<int:notif_id>/lu", methods=["POST"])
@login_required
def mark_read(notif_id):
    execute_db("UPDATE notifications SET lu = 1 WHERE id = ? AND user_id = ?", (notif_id, session["user_id"]))
    if request.is_json:
        return jsonify({"ok": True})
    return redirect(url_for("notifications.list_notifications"))


@bp.route("/tout-marquer-lu", methods=["POST"])
@login_required
def mark_all_read():
    execute_db("UPDATE notifications SET lu = 1 WHERE user_id = ?", (session["user_id"],))
    return redirect(url_for("notifications.list_notifications"))
