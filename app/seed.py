from werkzeug.security import generate_password_hash
from app.db import execute_db, query_db


def seed_super_admin():
    existing = query_db("SELECT id FROM super_admins LIMIT 1", one=True)
    if existing:
        return
    execute_db(
        "INSERT INTO super_admins (nom_complet, email, mot_de_passe_hash) VALUES (?, ?, ?)",
        ("Administrateur Logiciel", "admin@ra9mana.dz", generate_password_hash("Admin@2026")),
    )
    execute_db(
        "INSERT INTO parametres_logiciel (cle, valeur) VALUES (?, ?)",
        ("mode_maintenance", "0"),
    )
    execute_db(
        "INSERT INTO parametres_logiciel (cle, valeur) VALUES (?, ?)",
        ("version_application", "1.0.0"),
    )


DEFAULT_SITE_CONTENT = {
    "hero_titre": "Le logiciel de gestion médicale que vos patients remarqueront",
    "hero_sous_titre": "RA9MANA Clinic réunit rendez-vous, dossiers patients, ordonnances, facturation et bien plus dans une seule plateforme élégante, pensée pour les cabinets médicaux modernes.",
    "pourquoi_titre": "Pourquoi choisir RA9MANA Clinic",
    "pourquoi_texte": "Conçu avec des médecins, pour des médecins. Une interface premium, un déploiement en quelques minutes, et un support réactif à chaque étape.",
    "fonctionnalites": (
        "Dossiers patients complets|Historique médical chronologique, allergies, antécédents et pièces jointes centralisés.|🗂️\n"
        "Agenda intelligent|Calendrier jour/semaine/mois avec glisser-déposer et rappels automatiques.|📅\n"
        "Ordonnances premium|Génération de documents professionnels avec signature, cachet et QR code.|💊\n"
        "Facturation intégrée|Suivi des paiements, rapports financiers et export comptable en un clic.|🧾\n"
        "Salle d'attente digitale|File d'attente en temps réel avec écran TV pour vos patients.|🖥️\n"
        "Multi-clinique & multi-langue|Une plateforme pensée pour grandir avec votre activité.|🌍"
    ),
    "faq": (
        "Mes données sont-elles sécurisées ?|Oui, chaque clinique est isolée et vos données ne sont jamais partagées. Des sauvegardes régulières sont disponibles à tout moment.\n"
        "Puis-je essayer gratuitement ?|Oui, chaque nouvelle clinique bénéficie de 14 jours d'essai gratuit, sans carte bancaire requise.\n"
        "Le logiciel fonctionne-t-il hors ligne ?|L'application peut être installée comme une application de bureau (PWA) et reste consultable même en cas de coupure réseau ponctuelle.\n"
        "Puis-je changer de forfait à tout moment ?|Oui, vous pouvez passer du mensuel à l'annuel (ou inversement) depuis votre espace client à tout moment."
    ),
    "temoignages": (
        "Dr. Amine K.|Médecin généraliste|RA9MANA Clinic a transformé la gestion de mon cabinet. Mes patients adorent la salle d'attente digitale.\n"
        "Dr. Sara B.|Pédiatre|La facturation et les rapports me font gagner des heures chaque semaine.\n"
        "Dr. Yacine M.|Dentiste|Interface magnifique et support très réactif. Je recommande à tous mes confrères."
    ),
    "tarif_mensuel_prix": "3 500",
    "tarif_annuel_prix": "35 000",
    "contact_telephone": "+213 555 00 00 00",
    "contact_email": "contact@ra9mana.dz",
    "contact_adresse": "Annaba, Algérie",
    "contact_facebook": "https://facebook.com",
    "contact_instagram": "https://instagram.com",
    "contact_linkedin": "https://linkedin.com",
    "contact_whatsapp": "https://wa.me/213555000000",
    "footer_texte": "RA9MANA Clinic est une plateforme SaaS de gestion de cabinet médical, conçue pour les médecins et cliniques modernes.",
    "a_propos": "RA9MANA Clinic est née de la volonté de simplifier la gestion administrative des cabinets médicaux, pour que les médecins puissent se concentrer sur l'essentiel : leurs patients.",
    "conditions_utilisation": (
        "1. Objet\n"
        "Les présentes conditions générales d'utilisation (« CGU ») régissent l'accès et l'utilisation de la plateforme RA9MANA Clinic, "
        "un logiciel de gestion de cabinet médical proposé en mode SaaS (Software as a Service) aux médecins, cliniques et centres de santé.\n\n"
        "2. Accès au service\n"
        "L'accès à la plateforme est réservé aux professionnels de santé et à leur personnel autorisé. Chaque clinique dispose d'un espace "
        "indépendant et isolé ; les données d'une clinique ne sont jamais accessibles à une autre clinique.\n\n"
        "3. Compte et sécurité\n"
        "L'utilisateur est responsable de la confidentialité de ses identifiants de connexion et de toute activité effectuée depuis son compte. "
        "Toute perte ou usage non autorisé doit être signalé immédiatement au support.\n\n"
        "4. Abonnement et facturation\n"
        "L'utilisation de la plateforme est soumise à un abonnement (mensuel ou annuel) dont les modalités sont précisées lors de l'inscription. "
        "Une période d'essai gratuite peut être proposée avant tout engagement.\n\n"
        "5. Responsabilité médicale\n"
        "RA9MANA Clinic est un outil d'aide à la gestion administrative et documentaire. Il ne se substitue en aucun cas au jugement clinique "
        "du professionnel de santé, seul responsable des décisions médicales prises et des documents qu'il génère.\n\n"
        "6. Propriété des données\n"
        "Les données saisies par une clinique (patients, dossiers, documents) restent la propriété exclusive de cette clinique. RA9MANA Clinic "
        "agit en qualité de sous-traitant technique au sens de la réglementation applicable à la protection des données.\n\n"
        "7. Conformité légale\n"
        "La plateforme est conçue et opérée dans le respect des exigences légales applicables en matière de protection des données personnelles "
        "et de secret médical. Un support juridique dédié est disponible pour toute question relative à la conformité (voir rubrique Support juridique).\n\n"
        "8. Modification des CGU\n"
        "Ces conditions peuvent être mises à jour périodiquement. Les utilisateurs seront informés de toute modification substantielle."
    ),
    "politique_confidentialite": (
        "1. Données collectées\n"
        "RA9MANA Clinic traite les données nécessaires à la gestion d'un cabinet médical : informations d'identification du médecin et de la "
        "clinique, données administratives des patients, dossiers médicaux, documents générés (ordonnances, factures, rapports) et journaux "
        "d'activité technique.\n\n"
        "2. Finalité du traitement\n"
        "Ces données sont utilisées exclusivement pour permettre le fonctionnement du logiciel : gestion des patients, des rendez-vous, des "
        "documents médicaux et de la facturation, dans le cadre de la relation entre le médecin et ses patients.\n\n"
        "3. Confidentialité et secret médical\n"
        "Les données médicales sont soumises au secret professionnel. Elles ne sont jamais partagées avec un tiers non autorisé, ni utilisées "
        "à des fins commerciales, publicitaires ou de revente.\n\n"
        "4. Isolation des données\n"
        "Chaque clinique dispose d'un espace de données totalement isolé des autres cliniques utilisant la plateforme.\n\n"
        "5. Sécurité\n"
        "Des mesures techniques et organisationnelles sont mises en œuvre pour protéger les données : mots de passe chiffrés, protection contre "
        "les accès non autorisés, sauvegardes régulières et journalisation des actions sensibles.\n\n"
        "6. Droits des personnes concernées\n"
        "Conformément à la réglementation applicable en matière de protection des données personnelles, toute personne concernée dispose d'un "
        "droit d'accès, de rectification et de suppression de ses données, à exercer auprès du médecin responsable du traitement (le titulaire "
        "de la clinique) ou via notre support juridique.\n\n"
        "7. Conservation des données\n"
        "Les données sont conservées pendant la durée nécessaire à la finalité du traitement et conformément aux obligations légales de "
        "conservation applicables aux dossiers médicaux.\n\n"
        "8. Contact\n"
        "Pour toute question relative à la présente politique de confidentialité ou à l'exercice de vos droits, contactez notre support juridique."
    ),
    "support_juridique": (
        "RA9MANA Clinic dispose d'un support juridique dédié pour accompagner les cliniques sur les questions de conformité, de protection des "
        "données et d'utilisation de la plateforme dans le respect des obligations légales applicables aux professionnels de santé. "
        "Contact : juridique@ra9mana.dz"
    ),
}


def seed_site_content():
    existing = query_db("SELECT cle FROM site_contenu LIMIT 1", one=True)
    if existing:
        return
    for cle, valeur in DEFAULT_SITE_CONTENT.items():
        execute_db("INSERT INTO site_contenu (cle, valeur) VALUES (?, ?)", (cle, valeur))
