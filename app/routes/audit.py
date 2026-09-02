from flask import Blueprint, render_template, request, session

from app.db import query_db
from app.utils.security import login_required, roles_required

bp = Blueprint("audit", __name__, url_prefix="/journal-audit")

PAGE_SIZE = 30


@bp.route("/")
@login_required
@roles_required("medecin", "gestionnaire")
def list_logs():
    clinic_id = session["clinic_id"]
    page = max(1, request.args.get("page", 1, type=int))
    offset = (page - 1) * PAGE_SIZE

    total = query_db("SELECT COUNT(*) c FROM audit_log WHERE clinic_id = ?", (clinic_id,), one=True)["c"]
    logs = query_db(
        "SELECT a.*, u.nom_complet FROM audit_log a LEFT JOIN users u ON u.id = a.user_id "
        "WHERE a.clinic_id = ? ORDER BY a.date_creation DESC LIMIT ? OFFSET ?",
        (clinic_id, PAGE_SIZE, offset))
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    return render_template("audit.html", logs=logs, page=page, total_pages=total_pages, total=total)
