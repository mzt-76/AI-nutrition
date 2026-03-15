# TWA & Digital Asset Links — Comment ca marche

## C'est quoi une TWA ?

Une **TWA** (Trusted Web Activity) permet d'emballer un site web dans une app Android native. L'utilisateur installe un APK, l'ouvre, et voit le site en plein ecran — sans barre Chrome — comme si c'etait une vraie app.

Techniquement, c'est Chrome qui affiche le site, mais en mode "confiance" : pas de barre d'adresse, pas de boutons de navigation.

## Le probleme de securite que ca pose

N'importe qui peut creer un APK qui ouvre n'importe quel site web. Sans verification, un attaquant pourrait :
1. Creer une fausse app "BanqueXYZ" qui ouvre le vrai site de la banque
2. L'afficher en plein ecran sans barre URL
3. L'utilisateur croit etre dans l'app officielle → phishing possible

**Chrome refuse donc de masquer la barre URL par defaut.** Il faut une **preuve de confiance bidirectionnelle** entre le site et l'app.

## Digital Asset Links : la chaine de confiance

### Les deux pieces du puzzle

```
┌─────────────────────────┐         ┌─────────────────────────────────┐
│        APK Android       │         │         Site Web                │
│                          │         │                                 │
│  package_name:           │         │  /.well-known/assetlinks.json   │
│    com.monapp.twa        │◄─match─►│    package_name: com.monapp.twa│
│                          │         │                                 │
│  signature SHA256:       │         │    sha256_cert_fingerprints:    │
│    AB:CD:EF:...          │◄─match─►│      AB:CD:EF:...              │
│                          │         │                                 │
│  site a ouvrir:          │         │                                 │
│    monsite.com           │────────►│  (c'est moi!)                   │
└─────────────────────────┘         └─────────────────────────────────┘
```

**Cote APK** (grave dans l'app par Bubblewrap) :
- `package_name` — l'identifiant unique de l'app Android
- `host` — le domaine du site web a ouvrir
- Signature cryptographique — generee a partir du keystore (fichier `android.keystore`)

**Cote site web** — le fichier `/.well-known/assetlinks.json` :
```json
[
  {
    "relation": ["delegate_permission/common.handle_all_urls"],
    "target": {
      "namespace": "android_app",
      "package_name": "com.monapp.twa",
      "sha256_cert_fingerprints": [
        "AB:CD:EF:12:34:..."
      ]
    }
  }
]
```

Ce fichier dit : *"J'autorise l'app Android avec CE package name ET CETTE signature a s'afficher en plein ecran sur mon domaine."*

### Ce que Chrome fait a chaque lancement

```
Etape 1 : L'APK demande a Chrome d'ouvrir monsite.com
          │
Etape 2 : Chrome telecharge https://monsite.com/.well-known/assetlinks.json
          │
Etape 3 : Chrome compare les infos de l'APK avec le fichier :
          │
          ├── package_name de l'APK == package_name dans assetlinks.json ?
          │   └── OUI → continue
          │   └── NON → ❌ barre URL visible
          │
          └── SHA256 de l'APK == sha256_cert_fingerprints dans assetlinks.json ?
              └── OUI → ✅ plein ecran, barre masquee
              └── NON → ❌ barre URL visible
```

### Pourquoi deux verifications ?

| Verification    | Ce qu'elle prouve                                        |
|-----------------|----------------------------------------------------------|
| `package_name`  | Le site autorise **cette app specifique** (son identite) |
| `sha256`        | L'app a ete signee par **le bon developpeur** (sa preuve)|

Les deux sont necessaires :
- Meme package name mais signature differente → quelqu'un a copie le nom de l'app mais n'a pas le keystore → rejete
- Meme signature mais package name different → le site n'a pas autorise cette variante de l'app → rejete

## Exemple concret : notre bug (mars 2026)

### Symptome
La barre Chrome restait visible dans l'app NutriAI apres 48h+ d'attente. On pensait que la propagation DNS ou le cache Chrome etait en cause.

### Diagnostic

En inspectant le package name **dans l'APK** :
```
$ unzip -p app-release-signed.apk resources.arsc | strings | grep "com\."
→ com.onrender.ai_nutrition_frontend_78p7.twa
```

Et dans `assetlinks.json` deploye en production :
```json
"package_name": "com.ainutrition.app"    ← MISMATCH!
```

### Ce qui s'est passe

1. Le script `build-apk.sh` recommandait `com.ainutrition.app` comme package name
2. Bubblewrap a auto-genere `com.onrender.ai_nutrition_frontend_78p7.twa` depuis l'URL Render
3. On a mis `com.ainutrition.app` dans `assetlinks.json` (le nom "propre" prevu)
4. Mais l'APK a ete construit avec le nom auto-genere

### Resultat

```
Chrome compare :
  APK :             com.onrender.ai_nutrition_frontend_78p7.twa
  assetlinks.json : com.ainutrition.app
  → ❌ MISMATCH → barre URL visible

  APK SHA256 :      01:3E:F1:B8:...
  assetlinks SHA256: 01:3E:F1:B8:...
  → ✅ OK (on avait bien verifie ca)
```

La signature matchait (ce qu'on avait verifie ensemble), mais le package name non → verification echouee.

### Fix applique

On a corrige `assetlinks.json` pour matcher le package name reel de l'APK :
```json
"package_name": "com.onrender.ai_nutrition_frontend_78p7.twa"
```

### Lecon retenue

> Lors d'un setup TWA, toujours verifier **les deux** champs : `package_name` ET `sha256_cert_fingerprints`. La verification du fingerprint seul ne suffit pas.

Pour verifier rapidement :
```bash
# 1. Package name dans l'APK
unzip -p app-release-signed.apk resources.arsc | strings | grep "com\."

# 2. Package name dans assetlinks.json
curl -s https://MON-SITE/.well-known/assetlinks.json | python3 -m json.tool

# 3. Les deux doivent matcher
```

## Fichiers cles dans ce projet

| Fichier | Role |
|---------|------|
| `frontend/public/.well-known/assetlinks.json` | Declaration de confiance (deploye avec le frontend) |
| `twa/twa-manifest.json` | Config Bubblewrap (package name, host, theme) |
| `twa/android.keystore` | Cle de signature de l'APK (NE JAMAIS COMMITTER) |
| `twa/app-release-signed.apk` | L'APK genere (gitignore) |
| `scripts/build-apk.sh` | Script de build (init / build / fingerprint) |

## Commandes utiles

```bash
# Initialiser le projet TWA (premiere fois)
./scripts/build-apk.sh init

# Reconstruire l'APK
./scripts/build-apk.sh build

# Afficher le fingerprint SHA256 du keystore
./scripts/build-apk.sh fingerprint

# Verifier que assetlinks.json est accessible en prod
curl -I https://ai-nutrition-frontend-78p7.onrender.com/.well-known/assetlinks.json

# Tester la verification Digital Asset Links (outil Google)
# https://developers.google.com/digital-asset-links/tools/generator
```
