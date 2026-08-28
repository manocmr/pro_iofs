# FraudGuard

API Django REST de détection de fraude financière mobile : analyse de SMS suspects (phishing, arnaque mobile money) et détection d'anomalies sur les transactions.

## Le problème

Dans les pays où le mobile money (Orange Money, MTN Mobile Money, Wave...) est le principal moyen de paiement, l'arnaque par SMS est un vecteur de fraude massif : un message imitant l'opérateur prétend que le compte est bloqué et pousse la victime à composer un code USSD ou à donner son code PIN à un "agent". Contrairement au phishing par email, ces SMS sont courts, écrits dans un mélange français/anglais/langues locales, et exploitent l'urgence.

FraudGuard part de ce problème concret et l'aborde sous deux angles complémentaires :

1. **Le SMS lui-même** — avant que la victime n'agisse, peut-on scorer le message comme suspect ?
2. **La transaction qui suit** — si l'arnaque a fonctionné, peut-on détecter que le retrait/transfert qui en résulte est anormal pour ce compte ?

## Vue d'ensemble du flux

```
                    ┌─────────────────────────┐
   SMS reçu    ───▶ │   POST /api/analyze/    │
 (texte+sender)     │   ou /api/webhook/      │
                    └───────────┬─────────────┘
                                │
                                ▼
                  ┌─────────────────────────────┐
                  │   detector/fraud_rules.py    │
                  │        analyze_sms()         │
                  ├───────────────────────────────┤
                  │ 1. Mots-clés pondérés         │
                  │ 2. Motifs USSD (regex)        │
                  │ 3. Liens suspects (URL)       │
                  │ 4. Probabilité ML (TF-IDF+LR) │
                  └───────────────┬───────────────┘
                                  │
                     score = 0.6×(règles+URL) + 0.4×ML
                                  │
                                  ▼
                  Bonus si l'expéditeur est un récidiviste
                  (déjà signalé MEDIUM/HIGH dans l'historique)
                                  │
                                  ▼
                  Enregistré (SmsAnalysis) + renvoyé en JSON
                  { risk_score, label, reasons[] }


                    ┌─────────────────────────┐
  Transaction  ───▶ │ POST /api/transactions/ │
(account, montant)  │        analyze/         │
                    └───────────┬─────────────┘
                                │
                                ▼
              ┌───────────────────────────────────┐
              │   detector/transaction_rules.py     │
              │        analyze_transaction()        │
              ├───────────────────────────────────┤
              │ • z-score vs historique du compte   │
              │ • vélocité (nb transac / 10 min)    │
              │ • horaire inhabituel (00h-06h)      │
              │ • montant élevé sans historique      │
              └───────────────┬───────────────────┘
                                │
                                ▼
                  Enregistré (Transaction) + renvoyé en JSON
```

Toutes les requêtes passent par une vérification de clé API (header `X-API-Key`) avant d'atteindre la logique métier.

## Architecture du code

```
fraudguard/                  configuration Django
  settings.py                 SECRET_KEY, DEBUG, ALLOWED_HOSTS, API_KEY — tous via env vars
  urls.py                     racine : /admin/ et /api/

detector/
  models.py                   SmsAnalysis, Transaction
  serializers.py               sérialisation DRF (ModelSerializer)
  views.py                    6 endpoints, tous protégés par clé API
  urls.py                     routes /api/*
  permissions.py               HasAPIKey (permission DRF custom)

  fraud_rules.py               moteur de scoring SMS — combine règles + URL + ML
  url_signals.py                détection de liens suspects (raccourcisseurs, IP brute)
  transaction_rules.py          détection d'anomalies transactionnelles (fonction pure, sans accès DB)

  ml/
    dataset.py                  jeu d'exemples FR/EN (29 fraude / 28 légitime)
    classifier.py                pipeline TF-IDF + régression logistique, singleton lazy
    evaluate.py                  évaluation par validation croisée stratifiée (5-fold)

  tests.py                     28 tests (règles, URL, transactions, auth, 6 endpoints)
```

## Comment fonctionne la détection de SMS

### 1. Les règles par mots-clés ([fraud_rules.py](detector/fraud_rules.py))

Un dictionnaire de mots-clés pondérés (`"code pin": 30`, `"urgent": 15`, ...). Le texte est normalisé avant comparaison :

- accents retirés (`bloqué` → `bloque`) pour que la casse ou l'orthographe ne permette pas d'échapper à la détection ;
- espaces multiples réduits, et une version "sans espace" du texte est aussi comparée, pour capturer l'évasion par espacement lettre par lettre (`c o d e  p i n`).

Des motifs regex complètent la détection pour les vrais codes USSD (`\*\d+(?:\*\d+)*#`), qu'un simple mot-clé ne peut pas capturer puisqu'ils varient à chaque opérateur.

### 2. Les liens suspects ([url_signals.py](detector/url_signals.py))

Extraction des URLs du message, avec une pénalité plus forte pour :
- les raccourcisseurs connus (`bit.ly`, `tinyurl.com`, `t.co`, ...) — technique classique pour masquer un domaine de phishing ;
- les liens pointant vers une adresse IP brute plutôt qu'un nom de domaine.

### 3. Le modèle ML ([ml/classifier.py](detector/ml/classifier.py))

Un pipeline `TfidfVectorizer` (unigrammes + bigrammes) + `LogisticRegression`, entraîné au premier appel puis gardé en mémoire (pas de ré-entraînement à chaque requête). Il donne une probabilité de fraude indépendante des règles explicites — utile pour des formulations qui ne contiennent aucun des mots-clés du dictionnaire mais "sonnent" comme une arnaque.

**Le dataset d'entraînement est fabriqué à la main** (29 exemples de fraude couvrant blocage de compte, SIM swap, faux gain, fausse mise à jour KYC, fausse urgence familiale, fausse offre d'emploi ; 28 exemples légitimes). Ce n'est pas un vrai corpus collecté sur du trafic réel — voir la section Métriques pour ce que ça implique.

### 4. La combinaison finale

```python
score = 0.6 × min(score_règles + score_liens, 100) + 0.4 × score_ml
```

Les règles pèsent plus lourd parce qu'elles sont déterministes et vérifiables (chaque point est justifié par une raison explicite) ; le ML est pondéré plus faible tant qu'il n'est validé que sur des données synthétiques.

Seuils : `< 40` → `LOW-RISK` · `40-69` → `MEDIUM-RISK` · `≥ 70` → `HIGH-RISK FRAUD`.

### 5. Le signal expéditeur récidiviste ([views.py](detector/views.py))

Si un `sender` est fourni et qu'il a déjà été associé à des analyses MEDIUM/HIGH-RISK, un bonus est ajouté (+10 par signalement antérieur, plafonné à +20). C'est le seul signal qui dépend de l'historique en base — le reste de `analyze_sms()` est une fonction pure, testable sans DB.

## Comment fonctionne la détection transactionnelle

`analyze_transaction()` ([transaction_rules.py](detector/transaction_rules.py)) est une fonction pure inspirée des systèmes de surveillance anti-blanchiment (AML) classiques — c'est le même type de règles de première ligne utilisées avant des modèles ML plus lourds dans les vrais systèmes bancaires :

| Règle | Déclencheur | Points |
|---|---|---|
| Écart statistique | z-score du montant ≥ 3 par rapport à l'historique du compte | +45 |
| Écart statistique modéré | z-score ≥ 2 | +25 |
| Montant élevé sans référence | ≥ 500 000 et compte avec moins de 3 transactions passées | +20 |
| Vélocité | ≥ 3 transactions du même compte en 10 minutes | +30 |
| Horaire inhabituel | transaction entre 00h et 06h | +15 |

La vue ([views.py](detector/views.py)) fait le lien entre cette fonction pure et la base : elle récupère l'historique des montants du compte et compte les transactions récentes, avant d'appeler `analyze_transaction()`.

## Métriques du classifieur ML

Évaluées par validation croisée stratifiée à 5 folds (chaque exemple sert de test au moins une fois — plus fiable qu'un split unique sur un dataset de cette taille) :

| Métrique | Valeur |
|---|---|
| Échantillons | 57 (29 fraude / 28 légitime) |
| Accuracy | 87.7% |
| Precision (classe fraude) | 86.7% |
| Recall (classe fraude) | 89.7% |
| F1-score (classe fraude) | 88.1% |
| Matrice de confusion | `[[24 vrais négatifs, 4 faux positifs], [3 faux négatifs, 26 vrais positifs]]` |

Reproductible via `GET /api/ml/evaluation/` ou `python -m detector.ml.evaluate`.

**Ce que ces chiffres prouvent** : le pipeline fonctionne et généralise raisonnablement sur des formulations variées.
**Ce qu'ils ne prouvent pas** : la performance en production — le dataset est trop petit et entièrement synthétique. Étape suivante indispensable : remplacer par de vrais SMS labellisés (nécessite un partenariat avec un opérateur/une banque, avec les questions de confidentialité que ça soulève, le contenu d'un SMS étant une communication privée).

## Endpoints de l'API

Toutes les routes exigent le header `X-API-Key` (valeur définie par la variable d'environnement `API_KEY`, `dev-demo-key` par défaut en local — sans quoi la réponse est `403`).

| Méthode | Route | Description | Corps attendu |
|---|---|---|---|
| POST | `/api/analyze/` | Analyse un SMS | `{"message": "...", "sender": "..."}` |
| POST | `/api/webhook/` | Même analyse, format générique passerelle SMS | `{"from": "...", "text": "..."}` |
| POST | `/api/feedback/<id>/` | Corrige le verdict d'une analyse passée | `{"feedback": "false_positive"}` |
| GET | `/api/stats/` | Statistiques agrégées | — |
| POST | `/api/transactions/analyze/` | Analyse une transaction | `{"account_id": "...", "amount": 50000}` |
| GET | `/api/ml/evaluation/` | Métriques de validation croisée du modèle | — |

### Exemple de réponse — `/api/analyze/`

```json
{
  "id": 1,
  "message": "Votre compte mobile money est bloqué, composez *123# et entrez votre code pin",
  "sender": "+225700000",
  "risk_score": 88,
  "label": "HIGH-RISK FRAUD",
  "reasons": [
    "Contient le mot suspect : 'bloqué'",
    "Contient le mot suspect : 'code pin'",
    "Contient un code USSD suspect",
    "Le modèle ML estime une probabilité de fraude de 69%"
  ],
  "user_feedback": "",
  "created_at": "2026-08-28T03:39:41.797534Z"
}
```

## Sécurité

- **Authentification** : clé API partagée via header `X-API-Key`, vérifiée par [permissions.py](detector/permissions.py) sur chaque endpoint.
- **Configuration sensible externalisée** : `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `API_KEY` se lisent depuis des variables d'environnement (avec des valeurs par défaut permissives réservées au développement local — à définir explicitement pour tout déploiement réel).

## Interface de démo

Une page web simple ([detector/templates/detector/demo.html](detector/templates/detector/demo.html)) est servie à la racine (`/`) pour présenter le projet sans montrer de code ni de JSON brut : un formulaire "Analyser un SMS", un formulaire "Analyser une transaction", et un panneau de statistiques, avec un résultat affiché sous forme de badge coloré (vert/orange/rouge) et de raisons en français simple. Elle appelle les mêmes endpoints `/api/*` que n'importe quel client, la clé API étant injectée côté serveur au chargement de la page.

## Installation

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Puis ouvrir `http://127.0.0.1:8000/` pour la démo visuelle, ou appeler directement les endpoints `/api/*` documentés ci-dessus.

Variables d'environnement optionnelles (défauts adaptés au dev local uniquement) :

| Variable | Rôle | Défaut dev |
|---|---|---|
| `DJANGO_SECRET_KEY` | clé secrète Django | valeur insecure fournie |
| `DJANGO_DEBUG` | mode debug | `True` |
| `DJANGO_ALLOWED_HOSTS` | hôtes autorisés, séparés par virgules | `localhost,127.0.0.1` |
| `API_KEY` | clé exigée sur `/api/*` | `dev-demo-key` |

## Tests

### Suite automatisée (recommandé)

```bash
python manage.py test detector
```

28 tests : moteur de règles SMS (évasion par accents/espacement, plafonnement du score), heuristiques d'URL, règles transactionnelles (z-score, vélocité, horaire), authentification, et les 6 endpoints de bout en bout. C'est la méthode la plus fiable — elle ne dépend d'aucun outil externe et vérifie le comportement, pas juste "ça répond".

### Tester l'API manuellement, sans l'interface web

**PowerShell** (`Invoke-RestMethod` gère l'UTF-8 correctement — contrairement à `curl` en Git Bash sous Windows, qui peut corrompre les accents passés en argument) :

```powershell
$headers = @{ "X-API-Key" = "dev-demo-key"; "Content-Type" = "application/json" }
$body = @{ message = "Votre compte est bloqué, composez *123# et entrez votre code pin" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/analyze/" -Method Post -Headers $headers -Body $body
```

**Postman / Insomnia** : pratique pour explorer les 6 endpoints sans écrire de requêtes à la main — sauvegarder le header `X-API-Key` une fois dans la collection, puis tester chaque route au clic. Gère aussi l'UTF-8 correctement.

**curl** (fonctionne, mais éviter les accents en argument direct sous Git Bash — passer par un fichier si besoin) :

```bash
curl -X POST http://127.0.0.1:8000/api/stats/ -H "X-API-Key: dev-demo-key"
```

### Consulter les données enregistrées sans repasser par l'API

```bash
python manage.py createsuperuser
python manage.py runserver
```

puis `http://127.0.0.1:8000/admin/` → les tables `SmsAnalysis` et `Transaction` sont consultables et filtrables directement, sans ligne de code.

## Cas d'usage réaliste

Ce projet n'est **pas** un filtre déployable en frontal du trafic SMS d'un opérateur — l'échelle (SQLite, un seul process), les données (dataset synthétique) et le cadre légal (contenu de SMS = communication privée) en sont loin.

Ce pour quoi il est réaliste aujourd'hui : un **outil d'aide à la décision pour une équipe fraude**. Un agent reçoit un signalement, le passe dans `/api/analyze/`, obtient un score argumenté au lieu d'un jugement à l'œil nu, et `/api/stats/` fait ressortir les numéros récidivistes sur l'ensemble des signalements traités. La boucle de feedback (`/api/feedback/`) permet de tracer les erreurs de verdict — la base pour améliorer le système avec l'usage réel, plutôt qu'un modèle figé.

## Limites connues et pistes d'amélioration

- **Dataset ML synthétique** — la priorité n°1 est de le remplacer par de vrais SMS labellisés.
- **Pas d'intégration réelle à une passerelle SMS** — le webhook est prêt (`/api/webhook/`) mais non branché à un fournisseur (Twilio, Africa's Talking...).
- **Clé API unique partagée** — pas de gestion multi-client, pas de quota, pas de rotation de clé.
- **Détection transactionnelle par règles statistiques simples** — pas encore de modèle ML dédié aux transactions (contrairement aux SMS).
- **SQLite** — suffisant pour le développement, à remplacer par PostgreSQL avant tout déploiement avec plusieurs utilisateurs concurrents.
- **Pas de ré-entraînement continu** — le modèle ML est figé au démarrage du serveur ; un vrai système de production aurait besoin d'un pipeline de ré-entraînement régulier pour suivre l'évolution des techniques de fraude.
