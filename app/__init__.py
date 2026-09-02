import os
from flask import Flask, session, g, request, redirect, url_for
from markupsafe import Markup

from config import Config
from app import db as db_module
from app.utils.security import generate_csrf_token, current_user
from app.utils.helpers import (
    format_date_fr, format_datetime_fr, calculate_age, format_money,
    STATUT_RDV_LABELS, STATUT_RDV_COULEURS,
)


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    os.makedirs(os.path.dirname(app.config["DATABASE_PATH"]), exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db_module.init_app(app)

    # Initialise la base au premier lancement si elle n'existe pas, puis migre le schéma
    with app.app_context():
        if not os.path.exists(app.config["DATABASE_PATH"]):
            db_module.init_db()
            from app.seed import seed_super_admin
            seed_super_admin()
        db_module.migrate_db()
        from app.seed import seed_site_content
        seed_site_content()

    # ---- Blueprints ----
    from app.routes.auth import bp as auth_bp
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.patients import bp as patients_bp
    from app.routes.appointments import bp as appointments_bp
    from app.routes.waiting_room import bp as waiting_room_bp
    from app.routes.prescriptions import bp as prescriptions_bp
    from app.routes.inventory import bp as inventory_bp
    from app.routes.billing import bp as billing_bp
    from app.routes.notifications import bp as notifications_bp
    from app.routes.users import bp as users_bp
    from app.routes.settings import bp as settings_bp
    from app.routes.audit import bp as audit_bp
    from app.routes.search import bp as search_bp
    from app.routes.backup import bp as backup_bp
    from app.routes.super_admin import bp as super_admin_bp
    from app.routes.documents import bp as documents_bp
    from app.routes.site import bp as site_bp
    from app.routes.support import bp as support_bp
    from app.routes.files import bp as files_bp
    from app.routes.assistant import bp as assistant_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(patients_bp)
    app.register_blueprint(appointments_bp)
    app.register_blueprint(waiting_room_bp)
    app.register_blueprint(prescriptions_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(super_admin_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(site_bp)
    app.register_blueprint(support_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(assistant_bp)

    @app.route("/")
    def index():
        if session.get("user_id"):
            return redirect(url_for("dashboard.index"))
        if session.get("super_admin_id"):
            return redirect(url_for("super_admin.dashboard"))
        from app.routes.site import landing
        return landing()

    @app.before_request
    def check_maintenance_mode():
        exempt_paths = ("/super-admin", "/static", "/landing", "/manifest.webmanifest",
                         "/service-worker.js", "/langue/", "/contact")
        is_public_root = request.path == "/" and not session.get("user_id") and not session.get("super_admin_id")
        if is_public_root or any(request.path.startswith(p) for p in exempt_paths):
            return
        from app.db import query_db
        row = query_db("SELECT valeur FROM parametres_logiciel WHERE cle = 'mode_maintenance'", one=True)
        if row and row["valeur"] == "1":
            from flask import render_template
            return render_template("maintenance.html"), 503

    @app.before_request
    def load_logged_in_user():
        user_id = session.get("user_id")
        g.user = None
        g.clinic = None
        if user_id:
            from app.db import query_db
            g.user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
            if g.user:
                g.clinic = query_db("SELECT * FROM clinics WHERE id = ?", (g.user["clinic_id"],), one=True)

    @app.context_processor
    def inject_globals():
        from app.utils.i18n import translate, get_locale, is_rtl, SUPPORTED_LANGUAGES
        from app.db import query_db
        unread_count = 0
        unread_tickets = 0
        if session.get("user_id"):
            row = query_db(
                "SELECT COUNT(*) c FROM notifications WHERE user_id = ? AND lu = 0",
                (session["user_id"],), one=True
            )
            unread_count = row["c"] if row else 0
            row2 = query_db(
                "SELECT COUNT(*) c FROM tickets_support WHERE clinic_id = ? AND non_lu_clinique = 1",
                (session["clinic_id"],), one=True
            )
            unread_tickets = row2["c"] if row2 else 0

        site_rows = query_db(
            "SELECT cle, valeur FROM site_contenu WHERE cle IN "
            "('logo_plateforme','fond_connexion','fond_inscription','fond_landing')")
        site_brand = {r["cle"]: r["valeur"] for r in site_rows}

        return dict(
            csrf_token=generate_csrf_token,
            app_name=app.config["APP_NAME"],
            app_version=app.config["APP_VERSION"],
            current_user=current_user(),
            current_clinic=g.get("clinic"),
            unread_notifications=unread_count,
            unread_tickets=unread_tickets,
            statut_rdv_labels=STATUT_RDV_LABELS,
            statut_rdv_couleurs=STATUT_RDV_COULEURS,
            t=translate,
            lang=get_locale(),
            is_rtl=is_rtl(),
            supported_languages=SUPPORTED_LANGUAGES,
            site_logo=site_brand.get("logo_plateforme"),
            site_bg_login=site_brand.get("fond_connexion"),
            site_bg_register=site_brand.get("fond_inscription"),
            site_bg_landing=site_brand.get("fond_landing"),
        )

    @app.template_filter("date_fr")
    def _date_fr(value, weekday=False):
        return format_date_fr(value, with_weekday=weekday)

    @app.template_filter("datetime_fr")
    def _datetime_fr(value):
        return format_datetime_fr(value)

    @app.template_filter("age")
    def _age(value):
        return calculate_age(value)

    @app.template_filter("money")
    def _money(value):
        devise = g.clinic["devise"] if g.get("clinic") else "DZD"
        return format_money(value, devise)

    @app.template_filter("nl2br")
    def _nl2br(value):
        if not value:
            return ""
        return Markup(str(value).replace("\n", "<br>"))

    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(e):
        from flask import render_template
        return render_template("errors/403.html"), 403

    return app
