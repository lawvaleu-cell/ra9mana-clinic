PRAGMA foreign_keys = ON;

-- =========================================================
-- CLINIQUES (Tenants SaaS)
-- =========================================================
CREATE TABLE IF NOT EXISTS clinics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom_clinique TEXT NOT NULL,
    nom_medecin TEXT,
    specialite TEXT,
    adresse TEXT,
    telephone TEXT,
    email TEXT,
    site_web TEXT,
    numero_fiscal TEXT,
    logo_path TEXT,
    signature_path TEXT,
    cachet_path TEXT,
    heures_travail TEXT,
    theme TEXT DEFAULT 'light',
    devise TEXT DEFAULT 'DZD',
    fuseau_horaire TEXT DEFAULT 'Africa/Algiers',
    format_papier TEXT DEFAULT 'A4',
    seuil_stock_bas INTEGER DEFAULT 10,
    statut TEXT DEFAULT 'essai',           -- essai, actif, suspendu, expire
    plan TEXT DEFAULT 'essai_gratuit',     -- essai_gratuit, mensuel, annuel
    date_expiration_abonnement DATE,
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- UTILISATEURS (multi-rôles par clinique)
-- =========================================================
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    nom_complet TEXT NOT NULL,
    email TEXT NOT NULL,
    mot_de_passe_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'medecin', -- medecin, receptionniste, assistant, infirmier, comptable, gestionnaire
    permissions TEXT DEFAULT '',           -- liste séparée par virgules (permissions custom)
    actif INTEGER DEFAULT 1,
    email_verifie INTEGER DEFAULT 1,
    derniere_connexion TIMESTAMP,
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(email)
);

CREATE TABLE IF NOT EXISTS password_resets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token TEXT NOT NULL,
    expire_at TIMESTAMP NOT NULL,
    utilise INTEGER DEFAULT 0,
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- SUPER ADMIN (propriétaire du logiciel)
-- =========================================================
CREATE TABLE IF NOT EXISTS super_admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom_complet TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    mot_de_passe_hash TEXT NOT NULL,
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS annonces_globales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titre TEXT NOT NULL,
    message TEXT NOT NULL,
    type TEXT DEFAULT 'information', -- information, avertissement, maintenance, mise_a_jour, urgence
    cible TEXT DEFAULT 'toutes',      -- 'toutes' ou id de clinique specifique
    clinic_id INTEGER REFERENCES clinics(id) ON DELETE CASCADE,
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS parametres_logiciel (
    cle TEXT PRIMARY KEY,
    valeur TEXT
);

-- =========================================================
-- PATIENTS
-- =========================================================
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    numero_patient TEXT NOT NULL,
    prenom TEXT NOT NULL,
    nom TEXT NOT NULL,
    sexe TEXT,
    date_naissance DATE,
    groupe_sanguin TEXT,
    telephone TEXT,
    email TEXT,
    adresse TEXT,
    contact_urgence TEXT,
    allergies TEXT,
    maladies_chroniques TEXT,
    notes_medicales TEXT,
    assurance TEXT,
    photo_path TEXT,
    date_inscription TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS consultations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    medecin_id INTEGER REFERENCES users(id),
    date_consultation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    motif TEXT,
    diagnostic TEXT,
    notes TEXT,
    poids REAL, tension TEXT, temperature REAL, frequence_cardiaque INTEGER
);

CREATE TABLE IF NOT EXISTS pieces_jointes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    nom_fichier TEXT NOT NULL,
    chemin_fichier TEXT NOT NULL,
    type_fichier TEXT,
    date_ajout TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- RENDEZ-VOUS & SALLE D'ATTENTE
-- =========================================================
CREATE TABLE IF NOT EXISTS rendez_vous (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    medecin_id INTEGER REFERENCES users(id),
    date_rdv DATE NOT NULL,
    heure_rdv TEXT NOT NULL,
    motif TEXT,
    statut TEXT DEFAULT 'planifie', -- planifie, confirme, en_attente, en_consultation, termine, annule, absent
    couleur TEXT DEFAULT '#2563EB',
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS file_attente (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    rendez_vous_id INTEGER REFERENCES rendez_vous(id),
    numero_ticket INTEGER NOT NULL,
    salle TEXT DEFAULT '1',
    statut TEXT DEFAULT 'en_attente', -- en_attente, en_consultation, termine
    heure_arrivee TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    heure_appel TIMESTAMP,
    heure_fin TIMESTAMP
);

-- =========================================================
-- PRESCRIPTIONS / ORDONNANCES
-- =========================================================
CREATE TABLE IF NOT EXISTS prescriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    medecin_id INTEGER REFERENCES users(id),
    date_prescription TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS prescription_lignes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prescription_id INTEGER NOT NULL REFERENCES prescriptions(id) ON DELETE CASCADE,
    medicament TEXT NOT NULL,
    dosage TEXT,
    frequence TEXT,
    duree TEXT,
    instructions TEXT
);

CREATE TABLE IF NOT EXISTS medicaments_favoris (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    nom TEXT NOT NULL,
    dosage_defaut TEXT,
    frequence_defaut TEXT
);

CREATE TABLE IF NOT EXISTS demandes_laboratoire (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    medecin_id INTEGER REFERENCES users(id),
    analyses TEXT NOT NULL,
    notes TEXT,
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS demandes_radiologie (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    medecin_id INTEGER REFERENCES users(id),
    examens TEXT NOT NULL,
    notes TEXT,
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- INVENTAIRE / PHARMACIE
-- =========================================================
CREATE TABLE IF NOT EXISTS medicaments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    nom TEXT NOT NULL,
    categorie TEXT,
    fournisseur TEXT,
    prix_achat REAL DEFAULT 0,
    prix_vente REAL DEFAULT 0,
    quantite INTEGER DEFAULT 0,
    quantite_min INTEGER DEFAULT 10,
    date_expiration DATE,
    code_barre TEXT,
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- FACTURATION
-- =========================================================
CREATE TABLE IF NOT EXISTS factures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    numero_facture TEXT NOT NULL,
    montant_total REAL DEFAULT 0,
    montant_paye REAL DEFAULT 0,
    statut TEXT DEFAULT 'impaye', -- paye, partiel, impaye
    date_facture TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS facture_lignes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    facture_id INTEGER NOT NULL REFERENCES factures(id) ON DELETE CASCADE,
    designation TEXT NOT NULL,
    quantite INTEGER DEFAULT 1,
    prix_unitaire REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS depenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    categorie TEXT NOT NULL, -- salaire, loyer, electricite, internet, taxes, autre
    description TEXT,
    montant REAL NOT NULL,
    date_depense DATE DEFAULT CURRENT_DATE
);

-- =========================================================
-- NOTIFICATIONS
-- =========================================================
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    titre TEXT NOT NULL,
    message TEXT,
    type TEXT DEFAULT 'info', -- info, alerte, rappel, systeme
    lu INTEGER DEFAULT 0,
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- AUDIT LOG
-- =========================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id INTEGER REFERENCES clinics(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    details TEXT,
    adresse_ip TEXT,
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tentatives_connexion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT,
    succes INTEGER DEFAULT 0,
    adresse_ip TEXT,
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index utiles
CREATE INDEX IF NOT EXISTS idx_patients_clinic ON patients(clinic_id);
CREATE INDEX IF NOT EXISTS idx_users_clinic ON users(clinic_id);
CREATE INDEX IF NOT EXISTS idx_rdv_clinic_date ON rendez_vous(clinic_id, date_rdv);
CREATE INDEX IF NOT EXISTS idx_medicaments_clinic ON medicaments(clinic_id);
CREATE INDEX IF NOT EXISTS idx_factures_clinic ON factures(clinic_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, lu);
