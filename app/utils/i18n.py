"""
Infrastructure multilingue (français / arabe / anglais).

Portée : l'interface de navigation, la page d'accueil publique, les pages
d'authentification, le tableau de bord et les libellés les plus utilisés
sont traduits dans les 3 langues. Les modules très denses en texte libre
(ex. formulaires détaillés de facturation ou de dossier médical) restent
en français par défaut — la clé manquante retombe automatiquement sur le
français plutôt que d'afficher une erreur.
"""
from flask import session

SUPPORTED_LANGUAGES = {"fr": "Français", "ar": "العربية", "en": "English"}
RTL_LANGUAGES = {"ar"}

TRANSLATIONS = {
    "fr": {
        "nav.dashboard": "Tableau de bord", "nav.patients": "Patients", "nav.appointments": "Rendez-vous",
        "nav.waiting_room": "Salle d'attente", "nav.tv_screen": "Écran TV", "nav.prescriptions": "Ordonnances",
        "nav.inventory": "Stock", "nav.invoices": "Factures", "nav.expenses": "Dépenses",
        "nav.reports": "Rapports", "nav.users": "Utilisateurs", "nav.settings": "Paramètres",
        "nav.backup": "Sauvegarde", "nav.audit": "Journal d'audit", "nav.support": "Support", "nav.logout": "Déconnexion",
        "nav.general": "Général", "nav.clinic": "Clinique", "nav.care": "Soins", "nav.finance": "Finances", "nav.admin": "Administration",
        "search.placeholder": "Rechercher un patient, une facture, un médicament…",
        "auth.login": "Se connecter", "auth.login_title": "Bon retour", "auth.login_subtitle": "Connectez-vous pour accéder à votre espace clinique.",
        "auth.email": "Adresse e-mail", "auth.password": "Mot de passe", "auth.remember": "Se souvenir de moi",
        "auth.forgot": "Mot de passe oublié ?", "auth.no_account": "Pas encore de compte ?", "auth.create_account": "Créer une clinique",
        "auth.have_account": "Vous avez déjà un compte ?",
        "landing.nav_features": "Fonctionnalités", "landing.nav_pricing": "Tarifs", "landing.nav_faq": "FAQ",
        "landing.nav_contact": "Contact", "landing.nav_login": "Connexion", "landing.nav_start": "Essai gratuit",
        "landing.hero_cta": "Démarrer l'essai gratuit", "landing.hero_cta_secondary": "Voir la démo",
        "landing.install_app": "Installer l'application", "landing.features_title": "Tout ce qu'il faut pour gérer votre clinique",
        "landing.pricing_title": "Des tarifs simples et transparents", "landing.faq_title": "Questions fréquentes",
        "landing.testimonials_title": "Ils nous font confiance", "landing.contact_title": "Contactez-nous",
        "landing.footer_rights": "Tous droits réservés.",
        "dashboard.greeting": "Bonjour", "dashboard.subtitle": "Voici un aperçu de l'activité de votre clinique aujourd'hui.",
        "common.save": "Enregistrer", "common.cancel": "Annuler", "common.delete": "Supprimer", "common.edit": "Modifier",
        "common.new": "Nouveau", "common.search": "Rechercher", "common.print": "Imprimer", "common.download_pdf": "Télécharger PDF",
    },
    "en": {
        "nav.dashboard": "Dashboard", "nav.patients": "Patients", "nav.appointments": "Appointments",
        "nav.waiting_room": "Waiting Room", "nav.tv_screen": "TV Screen", "nav.prescriptions": "Prescriptions",
        "nav.inventory": "Inventory", "nav.invoices": "Invoices", "nav.expenses": "Expenses",
        "nav.reports": "Reports", "nav.users": "Users", "nav.settings": "Settings",
        "nav.backup": "Backup", "nav.audit": "Audit Log", "nav.support": "Support", "nav.logout": "Log out",
        "nav.general": "General", "nav.clinic": "Clinic", "nav.care": "Care", "nav.finance": "Finance", "nav.admin": "Administration",
        "search.placeholder": "Search a patient, invoice, medicine…",
        "auth.login": "Log in", "auth.login_title": "Welcome back", "auth.login_subtitle": "Sign in to access your clinic workspace.",
        "auth.email": "Email address", "auth.password": "Password", "auth.remember": "Remember me",
        "auth.forgot": "Forgot password?", "auth.no_account": "Don't have an account yet?", "auth.create_account": "Create a clinic",
        "auth.have_account": "Already have an account?",
        "landing.nav_features": "Features", "landing.nav_pricing": "Pricing", "landing.nav_faq": "FAQ",
        "landing.nav_contact": "Contact", "landing.nav_login": "Log in", "landing.nav_start": "Free trial",
        "landing.hero_cta": "Start free trial", "landing.hero_cta_secondary": "See demo",
        "landing.install_app": "Install the app", "landing.features_title": "Everything you need to run your clinic",
        "landing.pricing_title": "Simple, transparent pricing", "landing.faq_title": "Frequently asked questions",
        "landing.testimonials_title": "Trusted by doctors", "landing.contact_title": "Get in touch",
        "landing.footer_rights": "All rights reserved.",
        "dashboard.greeting": "Hello", "dashboard.subtitle": "Here's an overview of your clinic's activity today.",
        "common.save": "Save", "common.cancel": "Cancel", "common.delete": "Delete", "common.edit": "Edit",
        "common.new": "New", "common.search": "Search", "common.print": "Print", "common.download_pdf": "Download PDF",
    },
    "ar": {
        "nav.dashboard": "لوحة التحكم", "nav.patients": "المرضى", "nav.appointments": "المواعيد",
        "nav.waiting_room": "صالة الانتظار", "nav.tv_screen": "شاشة العرض", "nav.prescriptions": "الوصفات الطبية",
        "nav.inventory": "المخزون", "nav.invoices": "الفواتير", "nav.expenses": "المصاريف",
        "nav.reports": "التقارير", "nav.users": "المستخدمون", "nav.settings": "الإعدادات",
        "nav.backup": "النسخ الاحتياطي", "nav.audit": "سجل التدقيق", "nav.support": "الدعم الفني", "nav.logout": "تسجيل الخروج",
        "nav.general": "عام", "nav.clinic": "العيادة", "nav.care": "الرعاية", "nav.finance": "المالية", "nav.admin": "الإدارة",
        "search.placeholder": "ابحث عن مريض، فاتورة، دواء…",
        "auth.login": "تسجيل الدخول", "auth.login_title": "مرحبًا بعودتك", "auth.login_subtitle": "سجل الدخول للوصول إلى مساحة عيادتك.",
        "auth.email": "البريد الإلكتروني", "auth.password": "كلمة المرور", "auth.remember": "تذكرني",
        "auth.forgot": "نسيت كلمة المرور؟", "auth.no_account": "ليس لديك حساب بعد؟", "auth.create_account": "إنشاء عيادة",
        "auth.have_account": "لديك حساب بالفعل؟",
        "landing.nav_features": "المميزات", "landing.nav_pricing": "الأسعار", "landing.nav_faq": "الأسئلة الشائعة",
        "landing.nav_contact": "اتصل بنا", "landing.nav_login": "تسجيل الدخول", "landing.nav_start": "تجربة مجانية",
        "landing.hero_cta": "ابدأ التجربة المجانية", "landing.hero_cta_secondary": "شاهد العرض التوضيحي",
        "landing.install_app": "تثبيت التطبيق", "landing.features_title": "كل ما تحتاجه لإدارة عيادتك",
        "landing.pricing_title": "أسعار بسيطة وشفافة", "landing.faq_title": "الأسئلة الشائعة",
        "landing.testimonials_title": "يثقون بنا", "landing.contact_title": "تواصل معنا",
        "landing.footer_rights": "جميع الحقوق محفوظة.",
        "dashboard.greeting": "مرحبًا", "dashboard.subtitle": "إليك نظرة عامة على نشاط عيادتك اليوم.",
        "common.save": "حفظ", "common.cancel": "إلغاء", "common.delete": "حذف", "common.edit": "تعديل",
        "common.new": "جديد", "common.search": "بحث", "common.print": "طباعة", "common.download_pdf": "تحميل PDF",
    },
}


def get_locale():
    lang = session.get("lang", "fr")
    return lang if lang in SUPPORTED_LANGUAGES else "fr"


def is_rtl(lang=None):
    return (lang or get_locale()) in RTL_LANGUAGES


def translate(key):
    lang = get_locale()
    return TRANSLATIONS.get(lang, {}).get(key) or TRANSLATIONS["fr"].get(key, key)
