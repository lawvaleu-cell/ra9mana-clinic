import sqlite3
import click
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE_PATH"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf8"))
    db.commit()


def migrate_db():
    """Ajoute les nouvelles colonnes/tables sans toucher aux données existantes."""
    db = get_db()

    def add_column_if_missing(table, column, ddl):
        cols = [r["name"] for r in db.execute(f"PRAGMA table_info({table})")]
        if column not in cols:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")

    add_column_if_missing("clinics", "documents_template", "documents_template TEXT DEFAULT 'classique'")
    add_column_if_missing("clinics", "prix_abonnement", "prix_abonnement REAL DEFAULT 0")
    add_column_if_missing("clinics", "statut_paiement", "statut_paiement TEXT DEFAULT 'en_attente'")
    add_column_if_missing("clinics", "methode_paiement", "methode_paiement TEXT")
    add_column_if_missing("super_admins", "theme", "theme TEXT DEFAULT 'dark'")
    add_column_if_missing("patients", "logo_traite", "logo_traite INTEGER DEFAULT 0")

    # Informations multilingues de la clinique (FR est déjà dans les colonnes existantes)
    for champ in ("nom_clinique", "nom_medecin", "specialite", "adresse", "pied_de_page", "description"):
        add_column_if_missing("clinics", f"{champ}_ar", f"{champ}_ar TEXT")
        add_column_if_missing("clinics", f"{champ}_en", f"{champ}_en TEXT")

    # Pièces jointes patient : enrichissement (titre, catégorie, tags, auteur)
    add_column_if_missing("pieces_jointes", "titre", "titre TEXT")
    add_column_if_missing("pieces_jointes", "description", "description TEXT")
    add_column_if_missing("pieces_jointes", "categorie", "categorie TEXT DEFAULT 'autre'")
    add_column_if_missing("pieces_jointes", "tags", "tags TEXT")
    add_column_if_missing("pieces_jointes", "uploaded_by", "uploaded_by INTEGER")
    add_column_if_missing("pieces_jointes", "taille_fichier", "taille_fichier INTEGER DEFAULT 0")

    # Médicaments (stock) : généralisation en stock complet (articles non-médicaux)
    add_column_if_missing("medicaments", "type_article", "type_article TEXT DEFAULT 'medicament'")
    add_column_if_missing("medicaments", "emplacement", "emplacement TEXT")
    add_column_if_missing("medicaments", "notes", "notes TEXT")

    # Rendez-vous : lien vers un paiement rapide de consultation
    add_column_if_missing("clinics", "carte_bio", "carte_bio TEXT")
    add_column_if_missing("clinics", "carte_photo_path", "carte_photo_path TEXT")
    add_column_if_missing("clinics", "carte_langues", "carte_langues TEXT")
    add_column_if_missing("clinics", "ecran_theme", "ecran_theme TEXT DEFAULT 'sombre'")

    # Consultations : signes vitaux complets pour le suivi médical
    add_column_if_missing("consultations", "taille", "taille REAL")
    add_column_if_missing("consultations", "saturation_oxygene", "saturation_oxygene REAL")
    add_column_if_missing("consultations", "glycemie", "glycemie REAL")
    add_column_if_missing("consultations", "symptomes", "symptomes TEXT")

    # Notifications : priorité et catégorie pour le centre de notifications intelligent
    add_column_if_missing("notifications", "priorite", "priorite TEXT DEFAULT 'normale'")
    add_column_if_missing("notifications", "categorie", "categorie TEXT DEFAULT 'general'")

    # Clinique : objectif de revenu mensuel (pour les indicateurs circulaires du dashboard)
    add_column_if_missing("clinics", "objectif_revenu_mensuel", "objectif_revenu_mensuel REAL DEFAULT 100000")

    db.executescript("""
    CREATE TABLE IF NOT EXISTS documents_personnalises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clinic_id INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
        patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
        medecin_id INTEGER REFERENCES users(id),
        type_document TEXT NOT NULL DEFAULT 'rapport_medical',
        titre TEXT NOT NULL,
        contenu TEXT,
        date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS paiements_abonnement (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clinic_id INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
        montant REAL NOT NULL DEFAULT 0,
        plan TEXT DEFAULT 'mensuel',
        methode_paiement TEXT DEFAULT 'virement',
        numero_facture TEXT,
        statut TEXT DEFAULT 'paye',
        date_paiement DATE DEFAULT CURRENT_DATE,
        prochaine_echeance DATE,
        date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_paiements_clinic ON paiements_abonnement(clinic_id);

    CREATE TABLE IF NOT EXISTS site_contenu (
        cle TEXT PRIMARY KEY,
        valeur TEXT
    );

    CREATE TABLE IF NOT EXISTS site_publicites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titre TEXT NOT NULL,
        description TEXT,
        image_path TEXT,
        lien_url TEXT,
        texte_bouton TEXT DEFAULT 'En savoir plus',
        actif INTEGER DEFAULT 1,
        ordre INTEGER DEFAULT 0,
        date_debut DATE,
        date_fin DATE,
        date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS tickets_support (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clinic_id INTEGER REFERENCES clinics(id) ON DELETE CASCADE,
        sujet TEXT NOT NULL,
        statut TEXT DEFAULT 'ouvert',
        epingle INTEGER DEFAULT 0,
        non_lu_admin INTEGER DEFAULT 1,
        non_lu_clinique INTEGER DEFAULT 0,
        date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        date_maj TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS ticket_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER NOT NULL REFERENCES tickets_support(id) ON DELETE CASCADE,
        auteur TEXT NOT NULL,
        auteur_nom TEXT,
        message TEXT NOT NULL,
        date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_ticket_messages ON ticket_messages(ticket_id);

    CREATE TABLE IF NOT EXISTS paiements_rapides (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clinic_id INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
        patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
        rendez_vous_id INTEGER REFERENCES rendez_vous(id),
        montant REAL NOT NULL DEFAULT 0,
        statut TEXT DEFAULT 'paye',
        methode_paiement TEXT DEFAULT 'especes',
        notes TEXT,
        date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_paiements_rapides_clinic ON paiements_rapides(clinic_id, date_creation);

    CREATE TABLE IF NOT EXISTS mouvements_stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clinic_id INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
        article_id INTEGER NOT NULL REFERENCES medicaments(id) ON DELETE CASCADE,
        type_mouvement TEXT NOT NULL,
        quantite INTEGER NOT NULL,
        motif TEXT,
        utilisateur_id INTEGER REFERENCES users(id),
        date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_mouvements_article ON mouvements_stock(article_id);

    CREATE TABLE IF NOT EXISTS modeles_prescription (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clinic_id INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
        nom TEXT NOT NULL,
        notes TEXT,
        date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS modele_prescription_lignes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        modele_id INTEGER NOT NULL REFERENCES modeles_prescription(id) ON DELETE CASCADE,
        medicament TEXT NOT NULL,
        dosage TEXT, frequence TEXT, duree TEXT, instructions TEXT
    );

    CREATE TABLE IF NOT EXISTS modeles_demande (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clinic_id INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
        type_demande TEXT NOT NULL DEFAULT 'laboratoire',
        nom TEXT NOT NULL,
        contenu TEXT NOT NULL,
        date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS plans_tarifaires (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        description TEXT,
        prix_mensuel REAL DEFAULT 0,
        prix_annuel REAL DEFAULT 0,
        fonctionnalites TEXT,
        mis_en_avant INTEGER DEFAULT 0,
        ordre INTEGER DEFAULT 0,
        actif INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS rappels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clinic_id INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(id),
        patient_id INTEGER REFERENCES patients(id) ON DELETE SET NULL,
        titre TEXT NOT NULL,
        date_rappel DATE NOT NULL,
        heure_rappel TEXT,
        statut TEXT DEFAULT 'actif',
        date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    add_column_if_missing("paiements_rapides", "file_attente_id", "file_attente_id INTEGER")
    db.commit()


def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id


@click.command("init-db")
def init_db_command():
    """Efface les données existantes et recrée les tables."""
    init_db()
    click.echo("Base de données initialisée.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
