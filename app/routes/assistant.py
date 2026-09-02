from flask import Blueprint, request, session, jsonify

from app.utils.security import login_required, validate_csrf
from app.assistant.engine import process_message
from app.assistant.context import reset_context

bp = Blueprint("assistant", __name__, url_prefix="/assistant")


@bp.route("/chat", methods=["POST"])
@login_required
def chat():
    data = request.get_json(silent=True) or {}
    if not validate_csrf(data.get("csrf_token")):
        return jsonify({"reply": "Session expirée, veuillez recharger la page."}), 400

    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"reply": "Veuillez écrire un message."}), 400
    if len(message) > 500:
        message = message[:500]

    clinic_id = session["clinic_id"]
    user_id = session["user_id"]

    try:
        result = process_message(message, clinic_id, user_id)
    except Exception:
        import logging
        logging.getLogger("assistant").exception("Erreur assistant")
        return jsonify({"reply": "Une erreur est survenue. Merci de reformuler votre demande."}), 200

    return jsonify(result)


@bp.route("/reset", methods=["POST"])
@login_required
def reset():
    data = request.get_json(silent=True) or {}
    if not validate_csrf(data.get("csrf_token")):
        return jsonify({"ok": False}), 400
    reset_context()
    return jsonify({"ok": True})
