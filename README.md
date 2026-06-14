# Projet Architecture Logicielle – Application de gestion de partages de dépenses (Cagnotte)

Ce projet a été réalisé dans le cadre du cours d'Architecture Logicielle du BUT Informatique.  
Il consiste à concevoir et déployer une application de type "Cagnotte" permettant la gestion et l'équilibrage des dépenses entre plusieurs participants.

Le projet mobilise plusieurs domaines : architecture n-tier, développement web, API REST, ligne de commande (CLI), base de données relationnelle et traçabilité.

---

## Organisation du dépôt

Le dépôt est structuré selon les différentes couches de l'architecture logicielle et les domaines du projet.

### SRC
Ce dossier contient le code source complet de l’application, structuré pour respecter la séparation des responsabilités.

Sous-dossiers et fichiers principaux :
- `templates/` : fichiers HTML de l'interface (base, pots, pot_detail, login, error, swagger)
- `api.py` : implémentation de la couche de service API REST avec Spectree
- `auth.py` : gestion des utilisateurs, de la session et de l'authentification par token
- `data.py` : couche d'accès aux données (Data) via SQLAlchemy Core et initialisation SQLite
- `domain.py` : couche métier (Domain) contenant l'algorithme d'équilibrage des comptes
- `validation.py` : schémas Pydantic et fonctions de validation des données entrantes
- `views_cli.py` : interface utilisateur en ligne de commande via Click
- `web.py` : interface utilisateur Web via Flask et contrôleurs de navigation

### Fichiers de configuration à la racine
- `pyproject.toml` : configuration du projet, métadonnées et gestion des dépendances avec Hatchling/UV
- `uv.lock` : verrouillage des versions exactes des dépendances du projet
- `archilog.log` : journal d'activité centralisant la traçabilité de l'application
- `data.db` : base de données SQLite générée pour la persistance locale

---

## Fonctionnalités principales

### Authentification et Autorisation
- Connexion sécurisée à l'interface web par identifiant et mot de passe.
- Authentification par Token Bearer JWT pour l'accès aux services de l'API.
- Contrôle d'accès basé sur les rôles : `admin` et `user`.

### Interface Web (GUI)
- Consultation de la liste des cagnottes existantes.
- Création et suppression de cagnottes (réservé au rôle `admin`).
- Consultation détaillée d'une cagnotte avec historique des dépenses.
- Ajout de dépenses par participant et calcul instantané des remboursements ("Qui doit à qui ?").

### Interface API REST
- Documentation interactive des routes via l'interface Swagger UI.
- Points d'entrée pour la génération de tokens, le listage et la création de cagnottes au format JSON.
- Validation stricte des données d'entrée via des schémas Pydantic.

### Interface Ligne de Commande (CLI)
- Commandes d'administration pour interagir avec le système directement depuis un terminal.
- Listage des cagnottes et calcul des soldes hors navigateur.

### Traçabilité (Logging)
- Journalisation centralisée de tous les événements de l'application (connexions, échecs, création/suppression).

---

## Technologies utilisées

- Python 3.12
- Gestionnaire de projet UV (Astro)
- Flask (Serveur Web WSGI)
- Spectree & Pydantic (API & Validation)
- SQLAlchemy Core (Accès Base de données)
- SQLite (Système de gestion de base de données)
- Tailwind CSS (Interface graphique moderne)

---

## Branche du projet

Le code principal du projet se trouve sur la branche `master`.

---

## Objectif pédagogique

Ce projet permet de mettre en pratique des compétences en :
- architecture logicielle (Patron de conception N-Tier / Application Factory),
- développement d'API sécurisées et documentées,
- manipulation de bases de données relationnelles en Python,
- gestion de la traçabilité et de la robustesse d'un système,
- empaquetage et distribution d'une application Python standardisée.
