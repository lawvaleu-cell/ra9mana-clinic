"""Moteur de l'assistant : relie NLP, extraction d'entités, contexte de
conversation et actions sur la base de données. Aucun LLM, aucune requête
externe — tout est déterministe et local.
"""
from datetime import date

from flask import url_for

from app.assistant import intents as intent_module
from app.assistant import entities as entity_module
from app.assistant import dates as date_utils
from app.assistant import actions
from app.assistant import context as ctx_module
from app.assistant import navigation as nav_module

NAV_ROUTES = {
    "prescription": ("prescriptions.create_prescription", True),
    "lab_request": ("prescriptions.create_lab_request", True),
    "radio_request": ("prescriptions.create_radio_request", True),
    "invoice": ("billing.create_invoice", True),
    "patient_file": ("patients.view_patient", True),
    "inventory_page": ("inventory.list_medicines", False),
    "appointments_page": ("appointments.calendar_view", False),
    "expenses_page": ("billing.expenses", False),
    "settings_page": ("settings.clinic_profile", False),
    "patients_page": ("patients.list_patients", False),
}

NAV_LABELS = {
    "prescription": "l'ordonnance",
    "lab_request": "la demande d'analyses",
    "radio_request": "la demande de radio",
    "invoice": "la facture",
    "patient_file": "le dossier",
    "inventory_page": "le stock",
    "appointments_page": "le calendrier des rendez-vous",
    "expenses_page": "les dépenses",
    "settings_page": "les paramètres",
    "patients_page": "la liste des patients",
    "reports_page": "les rapports",
}

CONFIRM_YES = {"oui", "yes", "ok", "d'accord", "confirmer", "confirm", "نعم", "أكد", "اكد"}
CONFIRM_NO = {"non", "no", "annule", "annuler", "cancel", "لا", "إلغاء", "الغاء"}


def _reply(text, **extra):
    out = {"reply": text}
    out.update(extra)
    return out


def process_message(message, clinic_id, user_id):
    ctx = ctx_module.get_context()
    message = (message or "").strip()
    if not message:
        return _reply("Je n'ai pas bien compris, pouvez-vous reformuler ?")

    low = message.lower().strip()

    # 1) Une confirmation est en attente
    if ctx.get("pending_confirm"):
        if any(w in low.split() or w in low for w in CONFIRM_YES):
            pending = ctx["pending_confirm"]
            ctx["pending_confirm"] = None
            ctx_module.save_context(ctx)
            return _execute(pending["intent"], pending["entities"], clinic_id, user_id, ctx)
        if any(w in low.split() or w in low for w in CONFIRM_NO):
            ctx["pending_confirm"] = None
            ctx_module.save_context(ctx)
            return _reply("D'accord, opération annulée.")
        return _reply("Merci de confirmer par « oui » ou « non ».", requires_confirmation=True)

    # 2) Une action est en attente d'informations complémentaires
    if ctx.get("pending_action") == "navigate":
        return _continue_navigate(message, clinic_id, ctx)
    if ctx.get("pending_action"):
        return _continue_pending(message, clinic_id, user_id, ctx)

    # 3) Commande de navigation explicite ("ouvre-moi une ordonnance pour lui")
    nav_target = nav_module.detect_navigation(message)
    if nav_target:
        return _handle_navigation(nav_target, message, clinic_id, ctx)

    # 4) Nouvelle intention
    intent = intent_module.detect_intent(message)
    entities = _extract_entities(message, intent, clinic_id)
    return _dispatch(intent, entities, message, clinic_id, user_id, ctx)


def _extract_entities(message, intent, clinic_id):
    ents = {}
    patient, score = entity_module.extract_patient(message, clinic_id)
    if patient:
        ents["patient"] = dict(patient)
    ents["date"] = date_utils.parse_date(message)
    ents["period"] = date_utils.parse_period(message)
    ents["time"] = date_utils.parse_time(message)
    ents["amount"] = entity_module.extract_amount(message)
    ents["quantity"] = entity_module.extract_quantity(message)
    if intent in ("add_inventory", "update_inventory", "search_inventory"):
        item, iscore = entity_module.extract_inventory_item(message, clinic_id)
        if item:
            ents["inventory_item"] = dict(item)
    return ents


def _dispatch(intent, entities, message, clinic_id, user_id, ctx):
    if intent == "greeting":
        return _reply("Bonjour docteur, comment puis-je vous aider aujourd'hui ?")
    if intent == "help":
        return _reply(
            "Je peux vous aider avec : la recherche de patients, les rendez-vous, "
            "les rappels, les revenus/dépenses et le stock. Par exemple : "
            "« Montre-moi mes rendez-vous de demain » ou « Cherche Ahmed »."
        )

    if intent == "search_patient":
        return _handle_search_patient(entities, message, clinic_id, ctx)

    if intent == "open_patient":
        return _handle_open_patient(entities, message, clinic_id, ctx)

    if intent == "add_patient":
        return _handle_add_patient(entities, message, clinic_id, user_id, ctx)

    if intent == "get_appointments":
        return _handle_get_appointments(entities, clinic_id)

    if intent == "create_appointment":
        return _handle_create_appointment(entities, clinic_id, user_id, ctx)

    if intent == "cancel_appointment":
        return _handle_cancel_appointment(entities, clinic_id, ctx)

    if intent == "reschedule_appointment":
        return _handle_reschedule_appointment(entities, clinic_id, ctx)

    if intent == "create_reminder":
        return _handle_create_reminder(entities, message, clinic_id, user_id, ctx)

    if intent == "get_reminders":
        return _handle_get_reminders(clinic_id, user_id)

    if intent == "delete_reminder":
        return _handle_delete_reminder(entities, clinic_id, user_id, ctx)

    if intent == "complete_reminder":
        return _handle_complete_reminder(entities, clinic_id, user_id, ctx)

    if intent == "get_revenue":
        return _handle_financial(entities, clinic_id, "revenue")
    if intent == "get_expenses":
        return _handle_financial(entities, clinic_id, "expenses")
    if intent == "get_profit":
        return _handle_financial(entities, clinic_id, "profit")

    if intent == "search_inventory":
        return _handle_search_inventory(entities, clinic_id)
    if intent == "add_inventory":
        return _handle_add_inventory(entities, message, clinic_id, ctx)
    if intent == "update_inventory":
        return _handle_update_inventory(entities, message, clinic_id, ctx)

    return _reply(
        "Je n'ai pas compris cette demande. Essayez par exemple : "
        "« Montre mes rendez-vous de demain », « Cherche Ahmed » ou « Mon revenu ce mois-ci »."
    )


# ------------------------------------------------------------------ Patients
def _handle_search_patient(entities, message, clinic_id, ctx):
    patient = entities.get("patient")
    if not patient:
        return _reply("Je n'ai trouvé aucun patient correspondant dans le dossier de la clinique.")
    age_txt = ""
    if patient.get("date_naissance"):
        try:
            from app.utils.helpers import calculate_age
            age_txt = f"\nÂge : {calculate_age(patient['date_naissance'])} ans"
        except Exception:
            pass
    sexe_txt = f"\nSexe : {'Homme' if patient.get('sexe') == 'M' else 'Femme' if patient.get('sexe') == 'F' else '—'}"
    tel_txt = f"\nTéléphone : {patient['telephone']}" if patient.get("telephone") else ""

    ctx["last_patient_id"] = patient["id"]
    ctx["last_patient_name"] = f"{patient['prenom']} {patient['nom']}"
    ctx_module.save_context(ctx)

    suggestions = [
        {"label": "📁 Ouvrir le dossier", "url": _nav_url("patient_file", patient["id"])},
        {"label": "💊 Créer une ordonnance", "url": _nav_url("prescription", patient["id"])},
        {"label": "🧾 Créer une facture", "url": _nav_url("invoice", patient["id"])},
    ]
    follow_up = (
        f"\n\nSouhaitez-vous que j'ouvre son dossier, que je crée une ordonnance, "
        f"une facture, ou autre chose pour {patient['prenom']} ?"
    )
    return _reply(
        f"J'ai trouvé {patient['prenom']} {patient['nom']}.{age_txt}{sexe_txt}{tel_txt}{follow_up}",
        patient_id=patient["id"],
        suggested_actions=suggestions,
    )


def _handle_open_patient(entities, message, clinic_id, ctx):
    patient = entities.get("patient")
    if not patient:
        return _reply("Je n'ai trouvé aucun patient correspondant pour ouvrir son dossier.")
    ctx["last_patient_id"] = patient["id"]
    ctx["last_patient_name"] = f"{patient['prenom']} {patient['nom']}"
    ctx_module.save_context(ctx)
    url = _nav_url("patient_file", patient["id"])
    return _reply(f"J'ouvre le dossier de {patient['prenom']} {patient['nom']}.", navigate_url=url)


def _nav_url(target, patient_id=None):
    endpoint, needs_patient = NAV_ROUTES.get(target, (None, False))
    if not endpoint:
        return None
    try:
        if needs_patient and patient_id:
            return url_for(endpoint, patient_id=patient_id)
        if not needs_patient:
            return url_for(endpoint)
    except Exception:
        return None
    return None


def _handle_navigation(target, message, clinic_id, ctx):
    endpoint, needs_patient = NAV_ROUTES.get(target, (None, False)) if target != "reports_page" else (None, None)

    if target == "reports_page":
        patient = entities_patient_or_last(message, clinic_id, ctx)
        if patient:
            url = url_for("patients.evolution_report", patient_id=patient["id"])
            return _reply(f"J'ouvre les rapports de suivi de {patient['prenom']} {patient['nom']}.", navigate_url=url)
        url = url_for("billing.reports")
        return _reply("J'ouvre la page des rapports financiers.", navigate_url=url)

    if needs_patient:
        patient = entities_patient_or_last(message, clinic_id, ctx)
        if not patient:
            ctx_module.set_pending(ctx, "navigate", {"target": target})
            return _reply(f"Pour quel patient souhaitez-vous ouvrir {NAV_LABELS.get(target, 'cette page')} ?")
        url = _nav_url(target, patient["id"])
        return _reply(f"J'ouvre {NAV_LABELS.get(target, 'la page')} pour {patient['prenom']} {patient['nom']}.",
                      navigate_url=url)

    url = _nav_url(target)
    return _reply(f"J'ouvre {NAV_LABELS.get(target, 'la page demandée')}.", navigate_url=url)


def entities_patient_or_last(message, clinic_id, ctx):
    patient, score = entity_module.extract_patient(message, clinic_id)
    if patient:
        return dict(patient)
    if nav_module.references_last_patient(message) and ctx.get("last_patient_id"):
        return actions.get_patient_info(ctx["last_patient_id"], clinic_id)
    # aucune référence explicite à un autre patient : réutiliser le dernier si le
    # message ne mentionne aucun nom du tout (cas "crée-lui une ordonnance")
    if not patient and ctx.get("last_patient_id") and not _looks_like_new_name(message):
        return actions.get_patient_info(ctx["last_patient_id"], clinic_id)
    return None


def _looks_like_new_name(message):
    # Heuristique simple : un message très court sans lettres capitalisables
    # multiples est probablement une commande, pas un nouveau nom de patient.
    return False


def _continue_navigate(message, clinic_id, ctx):
    pending_entities = ctx.get("pending_entities", {})
    target = pending_entities.get("target")
    ctx_module.clear_pending(ctx)
    patient, score = entity_module.extract_patient(message, clinic_id)
    if not patient:
        return _reply("Je n'ai pas trouvé ce patient, pouvez-vous préciser le nom ?")
    ctx["last_patient_id"] = patient["id"]
    ctx["last_patient_name"] = f"{patient['prenom']} {patient['nom']}"
    ctx_module.save_context(ctx)
    url = _nav_url(target, patient["id"])
    return _reply(f"J'ouvre {NAV_LABELS.get(target, 'la page')} pour {patient['prenom']} {patient['nom']}.",
                  navigate_url=url)


def _handle_add_patient(entities, message, clinic_id, user_id, ctx):
    import re
    cleaned = re.sub(r"\b(ajoute|créer?|create|add|new|patient|un|nouveau|nouvelle|aa|أضف|مريض)\b", "",
                      message, flags=re.IGNORECASE).strip()
    parts = cleaned.split()
    if len(parts) < 2:
        return _reply("Quel est le prénom et le nom du nouveau patient ?")
    prenom, nom = parts[0], " ".join(parts[1:])
    entities_full = {"prenom": prenom, "nom": nom}
    ctx["pending_confirm"] = {"intent": "add_patient", "entities": entities_full}
    ctx_module.save_context(ctx)
    return _reply(
        f"Créer un nouveau patient : {prenom} {nom} ? (oui / non)",
        requires_confirmation=True,
    )


# --------------------------------------------------------------- Rendez-vous
def _handle_get_appointments(entities, clinic_id):
    patient = entities.get("patient")
    on_date = entities.get("date")
    rows = actions.get_appointments(
        clinic_id, patient_id=patient["id"] if patient else None, on_date=on_date
    )
    if not rows:
        who = f" pour {patient['prenom']} {patient['nom']}" if patient else ""
        when = f" le {on_date.strftime('%d/%m/%Y')}" if on_date else ""
        return _reply(f"Aucun rendez-vous trouvé{who}{when}.")

    lines = []
    for r in rows:
        lines.append(f"{r['heure_rdv']} — {r['prenom']} {r['nom']}" + (f" — {r['motif']}" if r["motif"] else ""))
    intro = f"Vous avez {len(rows)} rendez-vous"
    if on_date:
        intro += f" le {on_date.strftime('%d/%m/%Y')}"
    if patient:
        intro = f"{patient['prenom']} {patient['nom']} a {len(rows)} rendez-vous"
    return _reply(intro + " :\n" + "\n".join(lines), appointment_ids=[r["id"] for r in rows])


def _handle_create_appointment(entities, clinic_id, user_id, ctx):
    patient = entities.get("patient")
    on_date = entities.get("date")
    heure = entities.get("time")

    missing = []
    if not patient:
        missing.append("patient")
    if not on_date:
        missing.append("date")
    if not heure:
        missing.append("heure")

    if missing:
        ctx_module.set_pending(ctx, "create_appointment", {
            "patient_id": patient["id"] if patient else None,
            "patient_name": f"{patient['prenom']} {patient['nom']}" if patient else None,
            "date": on_date.isoformat() if on_date else None,
            "time": heure,
        })
        if "patient" in missing:
            return _reply("Pour quel patient souhaitez-vous programmer ce rendez-vous ?")
        if "date" in missing:
            return _reply(f"À quelle date souhaitez-vous programmer le rendez-vous de {patient['prenom']} {patient['nom']} ?")
        return _reply(f"À quelle heure souhaitez-vous programmer le rendez-vous de {patient['prenom']} {patient['nom']} ?")

    conflict = actions.find_conflict(clinic_id, on_date, heure)
    if conflict:
        return _reply(
            f"⚠️ {conflict['prenom']} {conflict['nom']} a déjà un rendez-vous le "
            f"{on_date.strftime('%d/%m/%Y')} à {heure}. Voulez-vous choisir un autre horaire ?"
        )

    ctx["pending_confirm"] = {
        "intent": "create_appointment",
        "entities": {"patient_id": patient["id"], "date": on_date.isoformat(), "time": heure},
    }
    ctx_module.save_context(ctx)
    return _reply(
        f"Programmer un rendez-vous pour {patient['prenom']} {patient['nom']} "
        f"le {on_date.strftime('%d/%m/%Y')} à {heure} ? (oui / non)",
        requires_confirmation=True,
    )


def _handle_cancel_appointment(entities, clinic_id, ctx):
    patient = entities.get("patient")
    on_date = entities.get("date")
    heure = entities.get("time")

    if not patient:
        return _reply("Le rendez-vous de quel patient souhaitez-vous annuler ?")

    rows = actions.get_appointments(clinic_id, patient_id=patient["id"], on_date=on_date)
    if heure:
        rows = [r for r in rows if r["heure_rdv"] == heure]
    if not rows:
        return _reply(f"Je ne trouve aucun rendez-vous correspondant pour {patient['prenom']} {patient['nom']}.")
    if len(rows) > 1:
        lines = [f"{r['date_rdv']} à {r['heure_rdv']}" for r in rows]
        return _reply(
            "Plusieurs rendez-vous correspondent, merci de préciser l'heure :\n" + "\n".join(lines)
        )

    rdv = rows[0]
    ctx["pending_confirm"] = {"intent": "cancel_appointment", "entities": {"rdv_id": rdv["id"]}}
    ctx_module.save_context(ctx)
    return _reply(
        f"Annuler le rendez-vous de {patient['prenom']} {patient['nom']} le "
        f"{rdv['date_rdv']} à {rdv['heure_rdv']} ? (oui / non)",
        requires_confirmation=True,
    )


def _handle_reschedule_appointment(entities, clinic_id, ctx):
    patient = entities.get("patient")
    new_date = entities.get("date")
    new_heure = entities.get("time")

    if not patient:
        return _reply("Le rendez-vous de quel patient souhaitez-vous déplacer ?")
    rows = actions.get_appointments(clinic_id, patient_id=patient["id"])
    if not rows:
        return _reply(f"Je ne trouve aucun rendez-vous pour {patient['prenom']} {patient['nom']}.")
    rdv = rows[0]

    if not new_heure:
        return _reply(f"Vers quelle heure souhaitez-vous déplacer le rendez-vous de {patient['prenom']} {patient['nom']} ?")

    target_date = new_date or date.fromisoformat(rdv["date_rdv"])
    conflict = actions.find_conflict(clinic_id, target_date, new_heure, exclude_id=rdv["id"])
    if conflict:
        return _reply(
            f"⚠️ Il y a déjà un rendez-vous à {new_heure} le {target_date.strftime('%d/%m/%Y')}. "
            "Merci de choisir un autre horaire."
        )

    ctx["pending_confirm"] = {
        "intent": "reschedule_appointment",
        "entities": {"rdv_id": rdv["id"], "date": target_date.isoformat(), "time": new_heure},
    }
    ctx_module.save_context(ctx)
    return _reply(
        f"Déplacer le rendez-vous de {patient['prenom']} {patient['nom']} au "
        f"{target_date.strftime('%d/%m/%Y')} à {new_heure} ? (oui / non)",
        requires_confirmation=True,
    )


# ------------------------------------------------------------------ Rappels
def _handle_create_reminder(entities, message, clinic_id, user_id, ctx):
    import re
    on_date = entities.get("date") or date.today()
    titre = re.sub(
        r"\b(rappelle[- ]moi|rappel(le)?|remind me|create a reminder|de|to|pour|ذكرني|تذكير|aujourd'hui|"
        r"demain|tomorrow|today|غدا|اليوم)\b",
        "", message, flags=re.IGNORECASE,
    ).strip(" .,:;-")
    if not titre:
        titre = "Rappel"
    patient = entities.get("patient")
    rappel_id = actions.create_reminder(
        clinic_id, user_id, titre, on_date, entities.get("time"), patient["id"] if patient else None
    )
    return _reply(f"Rappel créé pour le {on_date.strftime('%d/%m/%Y')} : « {titre} ».")


def _handle_get_reminders(clinic_id, user_id):
    rows = actions.get_reminders(clinic_id, user_id)
    if not rows:
        return _reply("Vous n'avez aucun rappel actif.")
    lines = [f"{r['date_rappel']}" + (f" {r['heure_rappel']}" if r["heure_rappel"] else "") + f" — {r['titre']}"
             for r in rows]
    return _reply("Vos rappels :\n" + "\n".join(lines))


def _handle_delete_reminder(entities, clinic_id, user_id, ctx):
    rows = actions.get_reminders(clinic_id, user_id)
    if not rows:
        return _reply("Vous n'avez aucun rappel à supprimer.")
    target = rows[0]
    ctx["pending_confirm"] = {"intent": "delete_reminder", "entities": {"rappel_id": target["id"]}}
    ctx_module.save_context(ctx)
    return _reply(f"Supprimer le rappel « {target['titre']} » du {target['date_rappel']} ? (oui / non)",
                  requires_confirmation=True)


def _handle_complete_reminder(entities, clinic_id, user_id, ctx):
    rows = actions.get_reminders(clinic_id, user_id)
    if not rows:
        return _reply("Vous n'avez aucun rappel actif à terminer.")
    target = rows[0]
    row = actions.complete_reminder(clinic_id, target["id"])
    return _reply(f"Rappel « {row['titre']} » marqué comme terminé.")


# ----------------------------------------------------------------- Finances
def _handle_financial(entities, clinic_id, kind):
    period = entities.get("period")
    if period:
        debut, fin, label = period
    else:
        debut, fin, label = date.today().replace(day=1), date.today(), "ce mois-ci"

    if kind == "revenue":
        val = actions.get_revenue(clinic_id, debut, fin)
        return _reply(f"Votre revenu {label} est de {val:.2f}.")
    if kind == "expenses":
        val = actions.get_expenses_total(clinic_id, debut, fin)
        return _reply(f"Vos dépenses {label} s'élèvent à {val:.2f}.")
    val = actions.get_profit(clinic_id, debut, fin)
    return _reply(f"Votre bénéfice {label} est de {val:.2f}.")


# ---------------------------------------------------------------- Inventaire
def _handle_search_inventory(entities, clinic_id):
    item = entities.get("inventory_item")
    if item:
        return _reply(f"{item['nom']} : {item['quantite']} en stock.")
    rows = actions.search_inventory_all(clinic_id)
    if not rows:
        return _reply("Aucun article en stock pour le moment.")
    low = [r for r in rows if r["quantite"] <= (r["quantite_min"] or 10)]
    txt = f"{len(rows)} articles en stock."
    if low:
        txt += "\n⚠️ Stock faible : " + ", ".join(f"{r['nom']} ({r['quantite']})" for r in low[:5])
    return _reply(txt)


def _handle_add_inventory(entities, message, clinic_id, ctx):
    item = entities.get("inventory_item")
    qty = entities.get("quantity")
    if not qty:
        return _reply("Quelle quantité souhaitez-vous ajouter ?")
    if not item:
        import re
        name_guess = re.sub(r"\b(ajoute|add|au|à|to|stock|inventaire|inventory|\d+)\b", "", message,
                             flags=re.IGNORECASE).strip()
        if not name_guess:
            return _reply("Quel article souhaitez-vous ajouter au stock ?")
        item_name = name_guess
    else:
        item_name = item["nom"]

    ctx["pending_confirm"] = {"intent": "add_inventory", "entities": {"nom": item_name, "quantite": qty}}
    ctx_module.save_context(ctx)
    return _reply(f"Ajouter {qty} « {item_name} » au stock ? (oui / non)", requires_confirmation=True)


def _handle_update_inventory(entities, message, clinic_id, ctx):
    item = entities.get("inventory_item")
    qty = entities.get("quantity")
    if not item:
        return _reply("Quel article de stock souhaitez-vous mettre à jour ?")
    if qty is None:
        return _reply(f"Quelle est la nouvelle quantité pour {item['nom']} ?")
    ctx["pending_confirm"] = {
        "intent": "update_inventory", "entities": {"item_id": item["id"], "quantite": qty, "nom": item["nom"]}
    }
    ctx_module.save_context(ctx)
    return _reply(f"Mettre à jour « {item['nom']} » à {qty} unités ? (oui / non)", requires_confirmation=True)


# ------------------------------------------------------------ Multi-tours
def _continue_pending(message, clinic_id, user_id, ctx):
    pending_action = ctx["pending_action"]
    pending_entities = ctx.get("pending_entities", {})

    new_date = date_utils.parse_date(message)
    new_time = date_utils.parse_time(message)
    if new_date:
        pending_entities["date"] = new_date.isoformat()
    if new_time:
        pending_entities["time"] = new_time

    if not pending_entities.get("patient_id"):
        patient, _ = entity_module.extract_patient(message, clinic_id)
        if patient:
            pending_entities["patient_id"] = patient["id"]
            pending_entities["patient_name"] = f"{patient['prenom']} {patient['nom']}"

    ctx_module.clear_pending(ctx)

    rebuilt = {}
    if pending_entities.get("patient_id"):
        rebuilt["patient"] = actions.get_patient_info(pending_entities["patient_id"], clinic_id)
    if pending_entities.get("date"):
        rebuilt["date"] = date.fromisoformat(pending_entities["date"])
    rebuilt["time"] = pending_entities.get("time")

    if pending_action == "create_appointment":
        return _handle_create_appointment(rebuilt, clinic_id, user_id, ctx)
    if pending_action == "reschedule_appointment":
        return _handle_reschedule_appointment(rebuilt, clinic_id, ctx)

    return _reply("D'accord.")


# -------------------------------------------------------------- Exécution
def _execute(intent, entities, clinic_id, user_id, ctx):
    if intent == "create_appointment":
        rdv_id = actions.create_appointment(
            clinic_id, user_id, entities["patient_id"], date.fromisoformat(entities["date"]), entities["time"]
        )
        patient = actions.get_patient_info(entities["patient_id"], clinic_id)
        notify_clinic_safe(clinic_id, patient, entities)
        return _reply(
            f"Rendez-vous créé avec succès pour {patient['prenom']} {patient['nom']} "
            f"le {entities['date']} à {entities['time']}."
        )

    if intent == "cancel_appointment":
        rdv = actions.cancel_appointment(clinic_id, entities["rdv_id"])
        if not rdv:
            return _reply("Ce rendez-vous n'existe plus.")
        return _reply(f"Rendez-vous de {rdv['prenom']} {rdv['nom']} annulé.")

    if intent == "reschedule_appointment":
        ok = actions.reschedule_appointment(
            clinic_id, entities["rdv_id"], date.fromisoformat(entities["date"]), entities["time"]
        )
        if not ok:
            return _reply("Ce rendez-vous n'existe plus.")
        return _reply(f"Rendez-vous déplacé au {entities['date']} à {entities['time']}.")

    if intent == "add_patient":
        from app.utils.helpers import generate_patient_number
        from app.db import query_db as _q, execute_db as _e
        total = _q("SELECT COUNT(*) c FROM patients WHERE clinic_id = ?", (clinic_id,), one=True)["c"]
        numero = generate_patient_number(clinic_id, total)
        new_id = _e(
            "INSERT INTO patients (clinic_id, numero_patient, prenom, nom) VALUES (?,?,?,?)",
            (clinic_id, numero, entities["prenom"], entities["nom"]),
        )
        return _reply(f"Patient {entities['prenom']} {entities['nom']} créé avec succès.", patient_id=new_id)

    if intent == "delete_reminder":
        row = actions.delete_reminder(clinic_id, entities["rappel_id"])
        if not row:
            return _reply("Ce rappel n'existe plus.")
        return _reply(f"Rappel « {row['titre']} » supprimé.")

    if intent == "add_inventory":
        item_id, new_qty = actions.add_inventory_item(clinic_id, entities["nom"], entities["quantite"])
        return _reply(f"{entities['nom']} mis à jour : {new_qty} en stock.")

    if intent == "update_inventory":
        new_qty = actions.set_inventory_quantity(clinic_id, entities["item_id"], entities["quantite"])
        return _reply(f"{entities['nom']} mis à jour : {new_qty} en stock.")

    return _reply("D'accord.")


def notify_clinic_safe(clinic_id, patient, entities):
    try:
        notify_clinic(
            clinic_id, "Nouveau rendez-vous (assistant)",
            f"{patient['prenom']} {patient['nom']} — {entities['date']} à {entities['time']}",
            "info", "normale", "rendez_vous",
        )
    except Exception:
        pass
