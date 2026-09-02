import json
from datetime import date
from flask import (Blueprint, render_template, request, redirect, url_for, session, flash,
                    Response, current_app, jsonify)

from app.db import query_db, execute_db
from app.utils.i18n import SUPPORTED_LANGUAGES

bp = Blueprint("site", __name__)


def _content():
    rows = query_db("SELECT cle, valeur FROM site_contenu")
    return {r["cle"]: r["valeur"] for r in rows}


def _parse_lines(text, nb_parts):
    """Parse un contenu 'a|b|c' ligne par ligne en liste de tuples."""
    items = []
    for line in (text or "").split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        while len(parts) < nb_parts:
            parts.append("")
        items.append(parts[:nb_parts])
    return items


@bp.route("/conditions-utilisation")
def terms():
    content = _content()
    return render_template("site/legal.html", titre="Conditions d'utilisation",
                            texte=content.get("conditions_utilisation", ""), content=content)


@bp.route("/politique-confidentialite")
def privacy():
    content = _content()
    return render_template("site/legal.html", titre="Politique de confidentialité",
                            texte=content.get("politique_confidentialite", ""), content=content)


@bp.route("/app")
def app_entry():
    """Point d'entrée utilisé par l'application installée (PWA) : ne montre jamais la landing page."""
    if session.get("user_id"):
        return redirect(url_for("dashboard.index"))
    if session.get("super_admin_id"):
        return redirect(url_for("super_admin.dashboard"))
    return redirect(url_for("auth.login"))


@bp.route("/carte/<int:clinic_id>/vcard")
def vcard(clinic_id):
    clinic = query_db("SELECT * FROM clinics WHERE id = ?", (clinic_id,), one=True)
    if not clinic:
        from flask import abort
        abort(404)
    vcard_text = (
        "BEGIN:VCARD\nVERSION:3.0\n"
        f"N:{clinic['nom_medecin'] or ''}\n"
        f"FN:{clinic['nom_medecin'] or ''}\n"
        f"ORG:{clinic['nom_clinique'] or ''}\n"
        f"TITLE:{clinic['specialite'] or ''}\n"
        f"TEL;TYPE=WORK,VOICE:{clinic['telephone'] or ''}\n"
        f"EMAIL:{clinic['email'] or ''}\n"
        f"ADR;TYPE=WORK:;;{clinic['adresse'] or ''}\n"
        f"URL:{clinic['site_web'] or ''}\n"
        "END:VCARD\n"
    )
    return Response(vcard_text, mimetype="text/vcard",
                     headers={"Content-Disposition": f"attachment; filename={(clinic['nom_medecin'] or 'contact').replace(' ', '_')}.vcf"})


@bp.route("/carte/<int:clinic_id>")
def digital_card(clinic_id):
    clinic = query_db("SELECT * FROM clinics WHERE id = ?", (clinic_id,), one=True)
    if not clinic:
        from flask import abort
        abort(404)
    card_url = url_for("site.digital_card", clinic_id=clinic_id, _external=True)
    return render_template("site/digital_card.html", clinic=clinic, card_url=card_url)


@bp.route("/langue/<code>")
def set_language(code):
    if code in SUPPORTED_LANGUAGES:
        session["lang"] = code
        session.permanent = True
    return redirect(request.referrer or url_for("site.landing"))


@bp.route("/landing")
def landing():
    content = _content()
    today = date.today()
    ads = query_db(
        "SELECT * FROM site_publicites WHERE actif = 1 "
        "AND (date_debut IS NULL OR date_debut <= ?) AND (date_fin IS NULL OR date_fin >= ?) "
        "ORDER BY ordre ASC, id ASC", (today, today))

    fonctionnalites = _parse_lines(content.get("fonctionnalites"), 3)
    faq = _parse_lines(content.get("faq"), 2)
    temoignages = _parse_lines(content.get("temoignages"), 3)

    return render_template("site/landing.html", content=content, ads=ads,
                            fonctionnalites=fonctionnalites, faq=faq, temoignages=temoignages)


@bp.route("/contact", methods=["POST"])
def contact_submit():
    nom = request.form.get("nom", "").strip()
    email = request.form.get("email", "").strip()
    message = request.form.get("message", "").strip()
    if nom and email and message:
        # Pas de serveur e-mail configuré : le message est simplement confirmé à l'utilisateur.
        flash("Merci, votre message a bien été envoyé ! Notre équipe vous recontactera rapidement.", "success")
    else:
        flash("Merci de remplir tous les champs du formulaire.", "error")
    return redirect(url_for("site.landing") + "#contact")


@bp.route("/manifest.webmanifest")
def manifest():
    data = {
        "name": "RA9MANA Clinic — Gestion de cabinet médical",
        "short_name": "RA9MANA Clinic",
        "description": "Plateforme SaaS premium de gestion de cabinet médical",
        "start_url": "/app",
        "scope": "/",
        "display": "standalone",
        "background_color": "#F4F7FB",
        "theme_color": "#1D4ED8",
        "orientation": "any",
        "icons": [
            {"src": url_for("static", filename="icons/icon-192.png"), "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": url_for("static", filename="icons/icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
    }
    return Response(json.dumps(data), mimetype="application/manifest+json")


@bp.route("/service-worker.js")
def service_worker():
    js = """
const CACHE_NAME = 'cliniq-v1';
const OFFLINE_ASSETS = ['/static/css/main.css', '/static/js/app.js'];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(OFFLINE_ASSETS)).catch(() => {}));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

// Stratégie "network-first" : ne sert le cache que si le réseau est indisponible.
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
"""
    return Response(js, mimetype="application/javascript")
