# RA9MANA Clinic — Système SaaS de gestion de cabinet médical

Application web complète (Flask / SQLite / Jinja2) pour la gestion de cliniques, cabinets médicaux et centres de santé. Interface entièrement en français, thèmes multiples, génération de documents PDF, panneau Super Admin multi-clinique.

## 🚀 Installation rapide (GitHub Codespaces ou local)

```bash
# 1. Installer les dépendances
pip install -r requirements.txt

# 2. Lancer l'application (la base SQLite se crée automatiquement au premier lancement)
python run.py
```

L'application démarre sur **http://localhost:5000**.

Si vous utilisez GitHub Codespaces, ouvrez le port 5000 en "Public" ou "Private" depuis l'onglet **Ports**, puis cliquez sur le lien généré.

## 👤 Premiers pas

1. Rendez-vous sur `/auth/inscription` pour créer votre clinique (essai gratuit de 14 jours automatique).
2. Connectez-vous et complétez le profil de la clinique dans **Paramètres** (logo, coordonnées, thème).
3. Créez vos premiers patients, rendez-vous, ordonnances, etc.

### Accès Super Admin (propriétaire du logiciel)

Un compte super admin est créé automatiquement au premier lancement :

- URL : `/super-admin/connexion`
- E-mail : `admin@ra9mana.dz`
- Mot de passe : `Admin@2026`

⚠️ **Changez ce mot de passe** avant toute mise en production (via un script Python ou directement en base — il n'y a pas encore d'écran dédié pour le super admin lui-même).

## 🗂️ Structure du projet

```
clinic_saas_pro/
├── run.py                  # Point d'entrée
├── config.py                # Configuration Flask
├── requirements.txt
├── app/
│   ├── __init__.py          # Factory Flask, blueprints, filtres Jinja
│   ├── db.py                 # Connexion SQLite
│   ├── schema.sql            # Schéma complet de la base de données
│   ├── seed.py                # Création du compte super admin par défaut
│   ├── routes/                # Un blueprint par module fonctionnel
│   │   ├── auth.py            # Inscription / connexion / mot de passe oublié
│   │   ├── dashboard.py
│   │   ├── patients.py
│   │   ├── appointments.py    # Calendrier + statuts + glisser-déposer
│   │   ├── waiting_room.py    # File d'attente + écran TV public
│   │   ├── prescriptions.py   # Ordonnances + labo + radiologie (PDF)
│   │   ├── inventory.py
│   │   ├── billing.py         # Factures, dépenses, rapports
│   │   ├── notifications.py
│   │   ├── users.py
│   │   ├── settings.py
│   │   ├── audit.py
│   │   ├── search.py
│   │   ├── backup.py
│   │   └── super_admin.py     # Panneau propriétaire du logiciel
│   ├── utils/
│   │   ├── security.py        # Auth, rôles, CSRF, audit log
│   │   ├── helpers.py         # Dates FR, formatage monétaire, etc.
│   │   └── pdf_generator.py   # Génération PDF (ordonnances, factures...)
│   ├── templates/             # Jinja2 (un dossier par module)
│   └── static/
│       ├── css/main.css       # Design system (4 thèmes)
│       └── js/app.js
└── instance/
    ├── clinic.db              # Base SQLite (créée automatiquement)
    └── uploads/                # Logos, signatures, cachets
```

## ✅ Fonctionnalités incluses

- **Fichiers patients** : téléversement multi-fichiers (images, PDF, Word, Excel, ZIP) avec titre, description, catégorie, tags, aperçu, renommage, suppression et recherche — accessible depuis la liste des patients et la fiche patient
- **Rendez-vous rapides** : à la création d'un rendez-vous, choix entre patient existant ou création rapide d'un nouveau patient (prénom, nom, téléphone, sexe, date de naissance) — le dossier complet se complète plus tard
- **Paiement rapide de consultation** : depuis la salle d'attente, enregistrement du montant/statut/méthode de paiement sans passer par la facturation — alimente automatiquement les statistiques de revenus
- **Impression des tickets de salle d'attente** (A4/A5, plusieurs tickets par page, QR code)
- **Écran d'attente (TV)** : lien copiable, 2 thèmes premium supplémentaires (Modern Medical Blue, Elegant Minimal) en plus du thème sombre existant (inchangé par défaut), QR code vers la carte professionnelle digitale
- **Carte professionnelle digitale** : page publique partageable par lien ou QR code (photo, bio, spécialité, horaires, contact, itinéraire, enregistrement du contact vCard, demande de rendez-vous par e-mail) — synchronisée automatiquement avec les paramètres de la clinique
- **Module Stock** (généralisation de l'inventaire) : types d'articles (médicaments, équipements, fournitures, consommables, mobilier, informatique, nettoyage, autre), prix de vente optionnel, emplacement de stockage, et **journal des mouvements de stock** (entrée, sortie, usage interne, ajustement, perte, expiré, endommagé, retour)
- **Modèles réutilisables** : modèles d'ordonnances (avec lignes de médicaments) et modèles de demandes de laboratoire/radiologie, applicables en un clic
- **Page d'accueil publique (Landing Page)** premium avec hero, illustration vectorielle légère, fonctionnalités, tarifs, FAQ, témoignages, publicités programmables, formulaire de contact et footer — entièrement gérable depuis le Super Admin
- **Application installable (PWA)** : manifest, service worker, bouton "Installer l'application". Une fois installée, l'app ouvre directement sur le tableau de bord (ou la connexion) sans repasser par la landing page
- **Support multilingue (Français / Arabe / Anglais)** avec bascule instantanée, mémorisation du choix, et support RTL complet pour l'arabe (voir note ci-dessous sur la portée)
- **Informations de clinique multilingues** (nom, médecin, spécialité, adresse, pied de page en AR/EN) affichées en français + arabe simultanément sur les documents imprimés
- **Centre de support** côté clinique (tickets, messagerie avec actualisation automatique, contacts directs) et **centre de communication** côté Super Admin (répondre, archiver, résoudre, épingler, rechercher, non-lus)
- **Authentification** complète : inscription, connexion, mot de passe oublié/réinitialisation, sessions, hachage sécurisé (Werkzeug)
- **Multi-tenant SaaS** : chaque clinique est isolée (`clinic_id`), plans d'essai/abonnement
- **Tableau de bord** avec statistiques temps réel et graphiques (Chart.js)
- **Patients** : fiche complète, dossier médical chronologique (timeline), recherche/filtres/pagination
- **Rendez-vous** : calendrier jour/semaine/mois, statuts colorés, glisser-déposer
- **Salle d'attente** + **écran TV public** (file de tickets, actualisation automatique)
- **Ordonnances, demandes de laboratoire/radiologie, factures et documents médicaux personnalisés** (rapports, lettres d'orientation, certificats, recommandations...) — chacun avec :
  - **Impression directe** en un clic (ouvre la boîte de dialogue d'impression du navigateur, sans téléchargement préalable)
  - **Téléchargement PDF**
  - **QR code et code-barres uniques** générés automatiquement sur chaque document
  - **3 gabarits professionnels** au choix (Classique, Moderne, Audacieux), sélectionnables dans Paramètres et appliqués automatiquement à tous les documents
  - **Choix du format papier A4 / A5** avant impression ou export, avec mise en page, marges, polices et position de signature/cachet qui s'adaptent automatiquement
  - Éditeur de texte enrichi (Quill.js) pour les documents personnalisés
- **Suppression automatique de l'arrière-plan** du logo, de la signature et du cachet lors de l'upload (méthode heuristique par couleur dominante — voir note technique ci-dessous)
- **Facturation** : factures multi-lignes, suivi des paiements, PDF, dépenses, rapports mensuels/annuels
- **Notifications**, **utilisateurs multi-rôles** (médecin, réceptionniste, assistant, infirmier, comptable, gestionnaire)
- **Paramètres** : logo/signature/cachet, 4 thèmes (clair, sombre, bleu médical, émeraude), devise, fuseau horaire, gabarit des documents, informations multilingues, thème écran TV, carte digitale
- **Sauvegarde / restauration** des données (export JSON)
- **Journal d'audit** complet (qui a fait quoi, quand, depuis quelle IP)
- **Recherche globale instantanée** (patients, factures, médicaments)
- **Panneau Super Admin séparé**, avec son propre thème clair/sombre :
  - Gestion des cliniques clientes (statut, abonnement, réinitialisation de mot de passe, suppression)
  - **Module complet de gestion des paiements d'abonnement** : historique par clinique, revenu total/mensuel/annuel, revenu par plan, croissance, comptes payés/expirés/en attente, graphique d'évolution
  - **Gestion du contenu du site public** (hero, fonctionnalités, tarifs, FAQ, témoignages, contact, footer, pages légales) et **gestion des publicités** de la landing page
  - **Centre de support / communication** avec toutes les cliniques
  - Annonces globales, mode maintenance, journaux système (connexions, audit)

## ✨ Dernière vague de personnalisation (image de marque et finitions)

- **Identité de marque RA9MANA Clinic** : nom de la plateforme, logo fourni intégré partout (favicon, icônes PWA, barre latérale, connexion, inscription, landing, carte digitale, écran TV)
- **Arrière-plans configurables par le Super Admin** pour les pages connexion / inscription / accueil, avec un voile bleu appliqué automatiquement pour préserver la lisibilité (menu Super Admin → Site public → Identité visuelle)
- **Pages légales dédiées** : Conditions d'utilisation et Politique de confidentialité, rédigées avec un contenu professionnel par défaut (conformité, secret médical, droits des personnes), personnalisables depuis le Super Admin, avec mention d'un support juridique dédié
- **Paiement de consultation automatique** : dès qu'une consultation passe au statut « Terminée » dans la salle d'attente, la fenêtre de saisie du montant/paiement s'ouvre automatiquement et alimente directement les revenus
- **Tickets de salle d'attente repensés** : impression à l'avance sans qu'aucun patient ne soit encore présent, choix du nombre de tickets, plusieurs tickets par page à découper aux ciseaux, design simple et moderne
- **Écran TV enrichi** : secondes affichées sur l'horloge, météo du jour (température actuelle et maximale), informations complètes de la clinique, logo
- **4ᵉ gabarit de document « Serein »** : élégant, couleurs douces et apaisées, en plus des 3 gabarits existants
- **Carte professionnelle digitale repensée** : typographie plus raffinée (Playfair Display), bouton de prise de rendez-vous retiré, nouvelle section de partage (QR code, WhatsApp, e-mail)
- **Suppression des soulignements** sur la landing page, les pages légales et la carte digitale
- **Auto-complétion des médicaments** (liste des médicaments déjà utilisés, saisie manuelle possible) et **sélecteur d'unité de dosage** (mg, ml, comprimé…) — tout nouveau médicament saisi est automatiquement ajouté à la liste pour la prochaine fois
- **Champs de téléversement de fichiers modernisés** (logo, signature, cachet, photo de carte, publicités, arrière-plans) avec un bouton stylé cohérent avec le reste du tableau de bord
- **Création rapide de facture** directement depuis la page Facturation (sélection du patient puis composition libre des lignes)
- Bouton « Copier le lien de l'écran TV » retiré de la salle d'attente à la demande

### ⚠️ Points de cette dernière liste non implémentés dans cette passe

- **QR code menant à une page de vérification sécurisée du document** (affichant uniquement les médicaments prescrits + infos clinique) : le QR/code-barres référence toujours un identifiant simple plutôt qu'une page de vérification publique dédiée — cette page reste à construire.
- **Partage de l'ordonnance/demande par e-mail au patient** : bouton non ajouté.
- **Liste prête de médicaments/analyses/examens avec auto-complétion pour les demandes de laboratoire et de radiologie** : seul le système de modèles existant (déjà fonctionnel) couvre ce besoin ; une auto-complétion ligne par ligne comme pour les ordonnances n'a pas été ajoutée.
- **Export Excel/PDF de la liste des patients**, et **export complet du dossier patient** (infos + ordonnances + fichiers dans une archive) : non implémentés.
- **Contenu du code-barres limité aux seuls médicaments prescrits** : le code-barres reste un identifiant de document générique, pas une liste de médicaments encodée.

## 🧭 Fonctionnalités volontairement hors périmètre pour cette version

La dernière liste de demandes couvrait un périmètre extrêmement large (plusieurs documents de spécifications représentant des mois de développement pour une équipe complète). Pour rester honnête sur ce qui a été réellement construit et testé plutôt que de livrer des ébauches non fonctionnelles, les éléments suivants n'ont **pas** été implémentés dans cette passe :

- **Mode hors-ligne complet (offline-first)** avec IndexedDB, synchronisation en arrière-plan et résolution de conflits — nécessite une architecture de synchronisation distribuée complète, non réalisable de façon fiable dans cette passe. Le service worker actuel reste basique (cache réseau-prioritaire).
- **Photographie médicale réelle** sur la landing page / connexion — remplacée par des illustrations vectorielles (SVG) originales, plus rapides et sans dépendance à des banques d'images.
- **Cliniques multi-branches et multi-médecins** (agendas et files d'attente séparés par médecin) — changement d'architecture important, non inclus.
- **Rendez-vous récurrents**, redimensionnement du calendrier par glisser-déposer, vue "Agenda" dédiée.
- **Intégrations externes** : SMS, WhatsApp Business API, passerelles de paiement, laboratoires/pharmacies externes, API publique/webhooks — l'architecture reste compatible avec un ajout futur, mais rien n'est branché.
- **Envoi d'e-mails automatiques** (confirmation de rendez-vous, ordonnance par e-mail, etc.) — nécessite un serveur SMTP configuré, absent de cet environnement.
- **Centre de sécurité avancé** (blocage d'IP, sessions actives, 2FA) et **gestion fine des rôles/permissions** au-delà des rôles existants.
- **Plans tarifaires dynamiques, campagnes de lancement, SEO avancé (sitemap, meta par page), tableau de bord analytique BI avec plages de dates personnalisées** côté Super Admin.
- **Import Excel/CSV** de patients, export Excel de chaque rapport, tables virtualisées, raccourcis clavier, widgets de tableau de bord personnalisables (glisser-déposer), sauvegarde automatique de brouillons de formulaire.

Ces éléments restent des extensions naturelles et peuvent être développés dans une prochaine itération, module par module.


## 🎨 Note sur les gabarits de documents

Plutôt que de concevoir 18 gabarits totalement indépendants (3 styles × 6 types de document), le système utilise **3 styles visuels partagés** (Classique / Moderne / Audacieux) appliqués de façon cohérente à tous les types de documents imprimables (ordonnances, labo, radio, factures, documents personnalisés). Le style choisi dans Paramètres devient le défaut pour tous les documents futurs. Cette approche couvre le besoin exprimé (plusieurs gabarits professionnels au choix, cohérents entre eux) tout en restant maintenable.

## 🖼️ Note sur la suppression d'arrière-plan

Aucun accès réseau n'était disponible dans l'environnement de développement pour télécharger un modèle d'IA de segmentation (type `rembg`). La suppression d'arrière-plan implémentée est donc **heuristique** : elle détecte une couleur de fond unie à partir des coins de l'image et la rend transparente. Cela fonctionne très bien pour des logos/signatures/cachets sur fond blanc ou uni (le cas le plus courant), mais ne gère pas les fonds complexes ou les photos. Si un fond n'est pas détecté comme uni, l'image est conservée telle quelle (aucune dégradation).

## 🌍 Note sur le multilinguisme

L'infrastructure de traduction (FR/AR/EN, avec support RTL pour l'arabe) est fonctionnelle et branchée sur la navigation, la landing page, les pages de connexion/inscription et le tableau de bord. Traduire l'intégralité des centaines de libellés de chaque module (formulaires détaillés de facturation, dossier médical, panneau Super Admin, etc.) représente un volume de travail très important : ces zones restent en français par défaut pour l'instant, mais la structure (`app/utils/i18n.py`) est prête à être étendue module par module sans changement d'architecture.

## 💬 Note sur le support / la messagerie

Le centre de support et le centre de communication Super Admin fonctionnent avec une **actualisation automatique par intervalle** (toutes les 8 secondes) plutôt qu'avec une vraie connexion temps réel (WebSocket), qui nécessiterait une infrastructure serveur supplémentaire (ex. Flask-SocketIO + serveur asynchrone) non standard dans cet environnement de déploiement simple. L'expérience reste fluide pour un usage support classique.

## 🔳 Note sur les QR codes et codes-barres

Dans les PDF téléchargés, les QR codes et codes-barres sont dessinés nativement par ReportLab (aucune dépendance externe). Dans les vues imprimables HTML, ils sont générés côté navigateur via la bibliothèque `qrcode.js` chargée depuis un CDN — cela nécessite une connexion internet au moment de l'impression (ce qui est également le cas des polices Google Fonts déjà utilisées dans ces vues).



## ⚙️ Notes techniques importantes

- **Connexion internet côté navigateur** : les polices (Google Fonts), les graphiques (Chart.js), l'éditeur riche (Quill.js) et les QR codes des vues imprimables sont chargés depuis des CDN publics. Le serveur Flask, lui, fonctionne entièrement hors-ligne. Si l'ordinateur qui affiche l'application n'a pas d'accès internet, ces éléments spécifiques ne se chargeront pas (le reste de l'application continue de fonctionner normalement).
- **Base de données** : SQLite (fichier unique `instance/clinic.db`). Adaptée pour un déploiement mono-serveur ou une démo. Pour une charge de production plus importante, une migration vers PostgreSQL est recommandée (le code utilise des requêtes SQL brutes assez proches du standard, la migration reste raisonnable).
- **Envoi d'e-mails** : aucun serveur SMTP n'est configuré dans cet environnement. Le lien de réinitialisation de mot de passe est affiché directement à l'écran (mode démo). Pour la production, branchez un service comme SendGrid/Mailgun dans `app/routes/auth.py`.
- **Sauvegardes automatiques planifiées** : la sauvegarde manuelle (export/import JSON) est fonctionnelle. Une planification automatique nécessite un vrai ordonnanceur (cron, APScheduler) à configurer selon votre hébergement.
- **Sécurité** : protection CSRF sur tous les formulaires, hachage des mots de passe, contrôle d'accès par rôle, isolation stricte des données par `clinic_id`. Pensez à changer `SECRET_KEY` dans `config.py` (ou variable d'environnement) avant toute mise en production.
- **Toutes les données de test créées pendant le développement ont été supprimées** — la base se régénère vide au premier lancement.

## 🎨 Personnalisation

Le système de thèmes est basé sur des variables CSS dans `app/static/css/main.css` (`:root`, `[data-theme="dark"]`, `[data-theme="blue"]`, `[data-theme="emerald"]`). Pour ajouter un thème, dupliquez un bloc et ajoutez l'option dans `THEMES` (`app/routes/settings.py`).

## 📌 Prochaines étapes suggérées

Ce socle couvre l'ensemble du cahier des charges initial. Pour aller plus loin, les pistes naturelles sont : gestion fine des permissions personnalisées par utilisateur, intégration d'un vrai service d'e-mail transactionnel, passage à PostgreSQL pour la montée en charge, génération de QR codes sur les ordonnances, et export Excel des rapports financiers.
