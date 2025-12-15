# 📋 FICHE DE SYNTHÈSE PROJET - IA NUTRITION V2

**Dernière mise à jour :** 13 décembre 2025  
**Statut :** Prototype fonctionnel - Tests en cours

---

## 🎯 VISION DU PROJET

### **Objectif Principal**
Développer un assistant nutritionnel conversationnel intelligent capable de :
- Créer des plans alimentaires hebdomadaires personnalisés
- Générer des recettes adaptées aux contraintes individuelles
- Mémoriser et apprendre des préférences utilisateur
- S'ajuster dynamiquement en fonction des résultats observés
- **🆕 Analyser la composition corporelle via photo (upload direct)**

### **Proposition de Valeur**
> "Un nutritionniste IA qui te connaît, s'adapte à toi, et te génère chaque semaine un plan alimentaire complet avec recettes et liste de courses - en tenant compte de tes envies et de ton évolution réelle."

### **Utilisateur Cible**
- **Phase 1 (V1) :** Toi-même (test & validation)
- **Phase 2 :** Extension famille/amis
- **Phase 3 :** Ouverture grand public / clients

---

## 🏗️ ARCHITECTURE TECHNIQUE

### **Stack Technologique**

```
┌─────────────────────────────────────────────┐
│      INTERFACE CONVERSATIONNELLE            │
│         n8n + OpenAI API + Claude           │
│     (Prototype) → Code (Production)         │
└─────────────────────────────────────────────┘
                    ↕
┌─────────────────────────────────────────────┐
│         SYSTÈME DE MÉMOIRE (RAG)            │
│              Supabase                       │
│  • Profils utilisateurs enrichis           │
│  • Historique tracking hebdomadaire        │
│  • Préférences évolutives                  │
│  • Memories long terme                     │
└─────────────────────────────────────────────┘
                    ↕
┌─────────────────────────────────────────────┐
│       BASE DE CONNAISSANCES                 │
│              Supabase                       │
│  • Ingrédients référence (50-100)          │
│  • Connaissances scientifiques (RAG)       │
│  • Templates recettes (20-30)              │
│  • Documents Google Drive (sync auto)      │
└─────────────────────────────────────────────┘
                    ↕
┌─────────────────────────────────────────────┐
│      MOTEUR DE GÉNÉRATION & TOOLS           │
│         OpenAI API + Claude API             │
│  • Calculs nutritionnels avancés           │
│  • Génération plans 7 jours                │
│  • Création recettes (hybride)             │
│  • Ajustements adaptatifs                  │
│  • 🆕 Analyse composition corporelle       │
└─────────────────────────────────────────────┘
```

### **Stratégie de Développement**
1. **Phase Prototype :** n8n pour validation rapide workflows et logique métier ✅
2. **Phase Production :** Migration vers code (Python/Node.js) pour scalabilité

---

## 🔧 ARCHITECTURE GLOBALE DU WORKFLOW

### **Vue d'ensemble du flux**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           WEBHOOK2 (POST /chat)                          │
│                    Reçoit messages texte ET images                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                         CODE - EDIT FIELDS                               │
│  • Extrait chatInput, sessionId, gender                                 │
│  • Détecte si image présente (format data:image/xxx;base64,...)         │
│  • Convertit image JSON → binaire                                       │
│  • hasImage = true/false                                                │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                      SWITCH - CHECK IF IMAGE                             │
│                        hasImage === true ?                               │
└─────────────────────────────────────────────────────────────────────────┘
            │                                           │
            │ OUI (image)                               │ NON (texte)
            ↓                                           ↓
┌───────────────────────────┐               ┌───────────────────────────┐
│  🆕 FLUX BODY FAT         │               │   NUTRITION AI AGENT      │
│     ANALYSIS              │               │      (avec Tools)         │
│  (bypass agent)           │               │                           │
└───────────────────────────┘               └───────────────────────────┘
            │                                           │
            ↓                                           ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                        RESPOND TO WEBHOOK                                │
│                    (même node pour les 2 flux)                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🤖 TOOLS DE L'AGENT NUTRITION

### **Architecture des Tools de l'Agent**

```
┌─────────────────────────────────────────────────────────────┐
│                    NUTRITION AI AGENT                        │
│                      (OpenAI GPT-4)                         │
├─────────────────────────────────────────────────────────────┤
│  TOOLS CONNECTÉS :                                          │
│                                                             │
│  📊 CALCULS NUTRITIONNELS                                   │
│  ├─ calculate_nutritional_needs (BMR, TDEE, macros)        │
│  └─ calculate_weekly_adjustments (feedback hebdo)          │
│                                                             │
│  🗄️ DONNÉES & MÉMOIRE                                       │
│  ├─ fetch_my_profile (profil utilisateur Supabase)         │
│  ├─ memories (RAG mémoires long terme)                     │
│  └─ documents (RAG connaissances nutrition)                │
│                                                             │
│  📁 GESTION DOCUMENTS                                       │
│  ├─ list_documents (liste fichiers disponibles)            │
│  ├─ get_file_contents (contenu fichier par ID)             │
│  └─ query_document_rows (requêtes SQL sur données)         │
│                                                             │
│  🌐 RECHERCHE & ANALYSE                                     │
│  ├─ web_search (recherche Brave API)                       │
│  ├─ image_analysis (analyse image Google Drive)            │
│  └─ execute_code (exécution JavaScript)                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

### **1. TOOL : calculate_nutritional_needs**

**Description :** Calcule BMR, TDEE et cibles macros avec inférence automatique des objectifs.

**Paramètres requis :**
- `age` : nombre (années)
- `gender` : "male"/"homme" ou "female"/"femme"
- `weight_kg` : nombre
- `height_cm` : nombre
- `activity_level` : "sedentary", "light", "moderate", "active", "very_active"

**Paramètres optionnels :**
- `goals` : objet {weight_loss, muscle_gain, performance, maintenance} notés 0-10
- `activities` : tableau ["musculation", "basket", "cardio", etc.]
- `context` : string décrivant la situation utilisateur

**Fonctionnalités :**
- Formule Mifflin-St Jeor pour BMR
- Calcul TDEE avec multiplicateurs d'activité
- Auto-inférence des objectifs depuis activités/contexte
- Ajustement protéines selon objectifs (1.6g à 2.2g/kg)
- Warnings si paramètres hors normes

**Exemple de sortie :**
```json
{
  "bmr": 1850,
  "tdee": 2868,
  "target_calories": 3168,
  "target_protein_g": 191,
  "target_carbs_g": 397,
  "target_fat_g": 88,
  "protein_per_kg": 2.2,
  "goals_used": {
    "muscle_gain": 7,
    "performance": 7
  },
  "inference_rationale": ["Musculation + Sport collectif → objectifs élevés"]
}
```

---

### **2. TOOL : calculate_weekly_adjustments**

**Description :** Analyse le feedback hebdomadaire et calcule les ajustements nutritionnels.

**Paramètres requis :**
- `weight_start` : nombre (kg début semaine)
- `weight_end` : nombre (kg fin semaine)
- `current_calories` : nombre (cible actuelle)

**Paramètres optionnels :**
- `current_protein_g`, `current_carbs_g`, `current_fat_g`
- `adherence_rate` : 0-100 (% repas suivis)
- `hunger_level` : "low" | "medium" | "high"
- `energy_level` : "low" | "medium" | "high"
- `sleep_quality` : "poor" | "medium" | "good"
- `cravings` : ["sucré", "salé", "gras"]
- `user_goal` : "weight_loss" | "muscle_gain" | "maintenance" | "performance"
- `weeks_on_plan` : nombre
- `notes` : string (feedback libre)

**Logique d'ajustement :**
```
1. VÉRIFICATION ADHÉRENCE
   • <50% → Focus sur simplification plan
   • 50-70% → Ajustements conservateurs

2. ANALYSE POIDS selon objectif
   • Perte de poids : cible -0.3 à -0.7 kg/semaine
   • Prise de masse : cible +0.2 à +0.5 kg/semaine
   • Maintenance : stabilité ±0.3 kg

3. AJUSTEMENTS AUTOMATIQUES
   • Faim élevée → +20g protéines
   • Énergie basse → +30g glucides
   • Fringales grasses → +10g lipides
```

**Exemple de sortie :**
```json
{
  "status": "stable",
  "adjustments": {
    "calories": +150,
    "protein_g": +20
  },
  "new_targets": {
    "calories": 3318,
    "protein_g": 211
  },
  "rationale": ["Faim élevée → +20g protéines pour satiété"],
  "tips": ["Place tes glucides autour de l'entraînement"]
}
```

---

### **3. TOOL : fetch_my_profile**

**Description :** Récupère le profil utilisateur depuis Supabase.

**Requête SQL :**
```sql
SELECT * FROM my_profile LIMIT 1;
```

**Données retournées :**
- Informations biométriques (âge, poids, taille, genre)
- Objectifs pondérés
- Allergies et restrictions
- Préférences alimentaires
- Cibles nutritionnelles calculées
- Tendance métabolique

---

### **4. TOOL : memories (RAG)**

**Description :** Recherche dans les mémoires long terme des conversations passées.

**Fonctionnement :**
- Vectorstore Supabase avec pgvector
- Embeddings OpenAI (text-embedding-3-small)
- Fonction `match_memories` pour recherche sémantique

**Utilisation :**
- Récupérer contexte conversations précédentes
- Maintenir continuité entre sessions
- Personnalisation croissante

---

### **5. TOOL : documents (RAG)**

**Description :** Recherche dans la base de connaissances nutritionnelles.

**Fonctionnement :**
- Documents indexés depuis Google Drive
- Sync automatique (création/modification)
- Chunking sémantique + embeddings
- Fonction `match_documents` pour retrieval

**Types de documents :**
- Guides nutritionnels scientifiques
- Position stands (ISSN, AND, etc.)
- Données ingrédients
- Templates recettes

---

### **6. TOOL : web_search**

**Description :** Recherche web via Brave Search API.

**Fonctionnalités :**
- Recherche web avancée
- Résumé automatique des résultats
- Entités extraites

**Utilisation :**
- Informations nutritionnelles récentes
- Recherche ingrédients/recettes
- Études scientifiques

---

### **7. TOOL : image_analysis**

**Description :** Analyse d'images depuis Google Drive (via l'agent).

**Paramètres :**
- `image_url` : URL Google Drive de l'image
- `query` : prompt d'analyse

**Fonctionnement :**
1. Téléchargement image depuis Google Drive
2. Analyse via OpenAI Vision (GPT-4o-mini)
3. Retour résultat structuré

**Note :** Ce tool est différent du flux body_fat_analysis. Celui-ci est appelé par l'agent pour analyser des images stockées sur Google Drive.

---

## 🆕 📸 FLUX BODY FAT ANALYSIS (BYPASS AGENT)

### **Description**

Ce n'est **PAS un tool de l'agent** mais un **flux séparé** qui s'active automatiquement quand une image est détectée dans la requête. L'image bypass complètement l'agent pour être traitée directement.

### **Pourquoi un flux séparé ?**

1. **Performance** : Pas besoin de passer par l'agent pour une tâche dédiée
2. **Simplicité** : L'image est déjà en binaire, on l'envoie directement à OpenAI Vision
3. **Guardrail** : Validation de l'image avant analyse (vérifie si photo corporelle appropriée)

### **Architecture détaillée du flux**

```
[Webhook2 - reçoit image dans JSON]
    ↓
[Code - Edit Fields]
    → Extrait image du JSON (format data:image/xxx;base64,...)
    → Convertit en binaire pour OpenAI
    → hasImage = true
    ↓
[Switch - Check If Image]
    → hasImage === true → FLUX BODY FAT
    ↓
┌─────────────────────────────────────────────────────────────┐
│              ÉTAPE 1 : VALIDATION (Guardrail)               │
├─────────────────────────────────────────────────────────────┤
│  [OpenAI - Validate Body Image] (GPT-4o-mini)               │
│      → Vérifie si c'est une photo corporelle valide         │
│      → Retourne JSON: {is_valid, reason}                    │
│                           ↓                                 │
│  [Code - Parse Validation]                                  │
│      → Extrait isValid et reason                            │
│      → Conserve le binaire pour l'étape suivante            │
│                           ↓                                 │
│  [Switch - Check Valid Image]                               │
│      → isValid === true ?                                   │
└─────────────────────────────────────────────────────────────┘
            │                           │
            │ VALIDE                    │ INVALIDE
            ↓                           ↓
┌─────────────────────────┐   ┌─────────────────────────────┐
│ ÉTAPE 2 : ANALYSE       │   │ MESSAGE D'ERREUR            │
├─────────────────────────┤   ├─────────────────────────────┤
│ [OpenAI - Analyze       │   │ [Set - Format Error         │
│  Body Fat] (GPT-4o)     │   │  Response]                  │
│     ↓                   │   │  → "Image non valide..."    │
│ [Set - Format Body      │   │  → Explique pourquoi        │
│  Fat Response]          │   │  → Conseils pour réessayer  │
└─────────────────────────┘   └─────────────────────────────┘
            │                           │
            └───────────┬───────────────┘
                        ↓
              [Respond to Webhook]
```

---

### **Node 1 : Edit Fields (Code)**

**Rôle :** Extraire l'image du JSON et la convertir en binaire.

**Code complet :**
```javascript
const item = $input.first();

// Récupérer les infos JSON
const chatInput = item.json?.chatInput || item.json.body?.chatInput || '';
const sessionId = item.json?.sessionId || item.json.body?.sessionId || '';
const gender = item.json.body?.gender || item.json?.gender || 'male';

// Vérifier si une image est présente dans le JSON
const imageData = item.json?.image || item.json.body?.image || null;

let result = {
  json: {
    chatInput: chatInput,
    sessionId: sessionId,
    hasImage: false,
    gender: gender
  }
};

// Si l'image est dans le JSON (format data:image/xxx;base64,...)
if (imageData && typeof imageData === 'string' && imageData.startsWith('data:image/')) {
  
  // Extraire le MIME type et les données base64
  // Format: data:image/png;base64,iVBORw0KGgo...
  const matches = imageData.match(/^data:(image\/[a-zA-Z]+);base64,(.+)$/);
  
  if (matches) {
    const mimeType = matches[1];  // "image/png"
    const base64Data = matches[2]; // "iVBORw0KGgo..."
    
    result.json.hasImage = true;
    result.binary = {
      data: {
        data: base64Data,
        mimeType: mimeType,
        fileName: 'uploaded_image.' + mimeType.split('/')[1]
      }
    };
  }
}

return [result];
```

---

### **Node 2 : Check If Image (Switch)**

**Configuration :**
| Paramètre | Valeur |
|-----------|--------|
| Rule 0 - Value 1 | `{{ $json.hasImage }}` |
| Rule 0 - Operation | is true |
| Fallback Output | Extra Output → vers Agent |
| Options | Convert types where required ✅ |

---

### **Node 3 : Validate Body Image (OpenAI)**

**Configuration :**
| Paramètre | Valeur |
|-----------|--------|
| Resource | Image |
| Operation | Analyze |
| Model | GPT-4o-mini |
| Input Type | Base64 |
| Input Data Field Name | data |

**Prompt de validation :**
```
Analyse cette image et détermine si elle est appropriée pour une estimation de body fat (masse grasse).

Une image VALIDE doit montrer :
- Une personne humaine
- Le torse visible (torse nu, en sous-vêtements, maillot de bain, ou vêtements moulants)
- Une photo permettant d'évaluer la composition corporelle

Une image INVALIDE :
- Pas une personne humaine (animal, objet, paysage, nourriture, etc.)
- Personne habillée avec vêtements amples cachant le corps
- Seulement le visage
- Image floue ou trop sombre pour analyser
- Contenu inapproprié

RÉPONDS UNIQUEMENT EN JSON :
{
  "is_valid": true ou false,
  "reason": "explication courte"
}
```

---

### **Node 4 : Parse Validation (Code)**

**Rôle :** Parser la réponse JSON et conserver le binaire.

**Code complet :**
```javascript
const response = $input.first().json;
const content = response.content || response.text || '';

let isValid = false;
let reason = "Impossible d'analyser l'image";

try {
  // Nettoyer la réponse
  const cleanedText = content
    .replace(/```json\n?/g, '')
    .replace(/```\n?/g, '')
    .replace(/\n/g, '')
    .trim();
  
  const parsed = JSON.parse(cleanedText);
  isValid = parsed.is_valid === true;
  reason = parsed.reason || reason;
  
} catch (error) {
  // Si le parsing échoue, chercher des mots clés
  const lowerContent = content.toLowerCase();
  if (lowerContent.includes('"is_valid": true') || lowerContent.includes('"is_valid":true')) {
    isValid = true;
  }
  // Extraire la raison si possible
  const reasonMatch = content.match(/"reason":\s*"([^"]+)"/);
  if (reasonMatch) {
    reason = reasonMatch[1];
  }
}

// Récupérer le binary depuis le node Edit Fields
const binaryData = $('Code in JavaScript').first().binary;

return [{
  json: {
    isValid: isValid,
    reason: reason,
    gender: $('Code in JavaScript').first().json.gender || 'male'
  },
  binary: binaryData
}];
```

**Note :** Remplacer `'Code in JavaScript'` par le nom exact de ton node Edit Fields.

---

### **Node 5 : Check Valid Image (Switch)**

**Configuration :**
| Paramètre | Valeur |
|-----------|--------|
| Rule 0 - Value 1 | `{{ $json.isValid }}` |
| Rule 0 - Operation | is true |
| Fallback Output | Extra Output → vers Format Error Response |
| Options | Convert types where required ✅ |

---

### **Node 6 : Analyze Body Fat (OpenAI)**

**Configuration :**
| Paramètre | Valeur |
|-----------|--------|
| Resource | Image |
| Operation | Analyze |
| Model | GPT-4o |
| Input Type | Base64 |
| Input Data Field Name | data |

**Prompt d'analyse (approche coach fitness) :**
```
Tu es un coach fitness expérimenté qui aide les gens à comprendre leur progression physique.

L'utilisateur souhaite avoir un retour visuel sur sa condition physique actuelle pour mieux orienter son programme d'entraînement et de nutrition.

Genre de la personne : {{ $json.gender }}

En te basant sur les indicateurs visuels observables sur cette photo, donne une évaluation générale de la condition physique :

1. **Niveau de définition musculaire** : Évalue la visibilité des muscles (abdominaux, bras, épaules, pectoraux)
   - Très défini / Défini / Modéré / Peu visible

2. **Estimation de la composition corporelle** : Donne une fourchette approximative du taux de masse grasse basée sur les repères visuels standards utilisés dans le fitness
   - Homme : athlétique (10-14%), fitness (15-19%), moyen (20-24%), à travailler (25%+)
   - Femme : athlétique (18-22%), fitness (23-27%), moyenne (28-32%), à travailler (33%+)

3. **Points forts observés** : Quels groupes musculaires semblent les plus développés ?

4. **Axes d'amélioration** : Suggestions pour progresser

5. **Estimation globale** : Donne un chiffre estimé (ex: "environ 18%") avec une fourchette (ex: "entre 16% et 20%")

IMPORTANT : 
- C'est une évaluation visuelle approximative à but informatif uniquement
- Seules des méthodes professionnelles (DEXA, impédancemétrie) donnent des mesures précises
- Cette estimation sert à orienter l'entraînement, pas à poser un diagnostic

Réponds de manière encourageante et constructive, comme un coach bienveillant.
```

---

### **Node 7 : Format Body Fat Response (Set)**

**Configuration :**
| Name | Type | Value |
|------|------|-------|
| output | String | `{{ $json.content \|\| $json.text \|\| $json.message.content }}` |

---

### **Node 8 : Format Error Response (Set)**

**Configuration :**
| Name | Type | Value |
|------|------|-------|
| output | String | *(voir ci-dessous)* |

**Value :**
```
❌ **Image non valide pour l'analyse body fat**

{{ $json.reason }}

Pour une analyse de composition corporelle, j'ai besoin d'une photo qui montre :
📸 Ton torse (torse nu, en sous-vêtements ou maillot)
💡 Un bon éclairage
🧍 Une posture debout, de face

Tu peux réessayer avec une photo adaptée ?
```

---

### **Format d'appel depuis le Frontend**

```javascript
// Envoi image pour analyse body fat
async function analyzeBodyFat(imageFile, gender = 'male', sessionId) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    
    reader.onload = async () => {
      try {
        const response = await fetch('https://ton-n8n.com/webhook/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            chatInput: 'Analyse mon body fat',
            sessionId: sessionId,
            image: reader.result,  // data:image/png;base64,...
            gender: gender
          })
        });
        
        const data = await response.json();
        resolve(data);
      } catch (error) {
        reject(error);
      }
    };
    
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(imageFile);
  });
}

// Envoi message texte normal
async function sendMessage(message, sessionId) {
  const response = await fetch('https://ton-n8n.com/webhook/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      chatInput: message,
      sessionId: sessionId
    })
  });
  
  return await response.json();
}
```

---

## 📊 COMPOSANTS DÉTAILLÉS

### **1. SYSTÈME DE PROFILING UTILISATEUR**

#### **Données Biométriques**
- Âge, sexe, poids, taille
- Niveau d'activité physique
- Description journée type pour estimation métabolisme précise
- **🆕 Body fat estimé (via analyse photo)**

#### **Objectifs Personnalisés (pondération 0-10)**
- Perte de poids
- Prise de masse musculaire
- Maintien
- Performance sportive
- Santé/bien-être général
- Énergie/vitalité

#### **Contraintes & Préférences**
- Allergies et intolérances
- Régime alimentaire
- Aliments détestés / favoris
- Temps de préparation
- Compétences culinaires
- Équipement cuisine
- Cuisines préférées

---

### **2. MOTEUR DE CALCUL NUTRITIONNEL**

#### **Formules Utilisées**
```
BMR (Mifflin-St Jeor) :
- Homme : (10 × poids) + (6.25 × taille) - (5 × âge) + 5
- Femme : (10 × poids) + (6.25 × taille) - (5 × âge) - 161

TDEE = BMR × Multiplicateur activité
- Sédentaire : 1.2
- Léger : 1.375
- Modéré : 1.55
- Actif : 1.725
- Très actif : 1.9

Protéines (g/kg) :
- Base maintien : 1.6
- Perte poids : 1.8-2.0
- Prise muscle : 2.0-2.2
```

---

### **3. SYSTÈME FEEDBACK HEBDOMADAIRE**

#### **Données Collectées**
- Poids début/fin semaine
- Adhérence au plan (%)
- Niveau faim / énergie
- Qualité sommeil
- Fringales spécifiques
- Notes libres

#### **Ajustements Automatiques**
- Calories : ±100-300 selon évolution poids
- Protéines : +10-20g si faim élevée
- Glucides : +20-30g si énergie basse
- Lipides : +10g si fringales grasses

---

## 🗄️ SCHÉMA BASE DE DONNÉES

### **Tables Principales (Supabase)**

```sql
-- Profils utilisateurs
CREATE TABLE my_profile (
  id UUID PRIMARY KEY,
  name TEXT,
  age INT,
  gender TEXT,
  weight_kg DECIMAL,
  height_cm INT,
  activity_level TEXT,
  goals JSONB,
  allergies TEXT[],
  diet_type TEXT,
  target_calories DECIMAL,
  target_protein_g DECIMAL,
  target_carbs_g DECIMAL,
  target_fat_g DECIMAL,
  estimated_body_fat DECIMAL  -- 🆕 Body fat estimé
);

-- Documents RAG
CREATE TABLE documents (
  id BIGSERIAL PRIMARY KEY,
  content TEXT,
  metadata JSONB,
  embedding VECTOR(1536)
);

-- Mémoires long terme
CREATE TABLE memories (
  id BIGSERIAL PRIMARY KEY,
  content TEXT,
  metadata JSONB,
  embedding VECTOR(1536)
);

-- Métadonnées documents
CREATE TABLE document_metadata (
  id TEXT PRIMARY KEY,
  title TEXT,
  url TEXT,
  created_at TIMESTAMP,
  schema TEXT
);

-- Lignes documents (données tabulaires)
CREATE TABLE document_rows (
  id SERIAL PRIMARY KEY,
  dataset_id TEXT REFERENCES document_metadata(id),
  row_data JSONB
);
```

---

## 💡 INNOVATIONS CLÉS

### **1. Pondération Objectifs Utilisateur**
L'utilisateur définit l'importance relative de chaque objectif (0-10). Le système adapte automatiquement les macros.

### **2. Auto-inférence des Objectifs**
Le tool `calculate_nutritional_needs` détecte automatiquement les objectifs depuis le contexte ("je fais de la musculation et du basket" → muscle_gain: 7, performance: 7).

### **3. Ajustements Adaptatifs**
Analyse écart résultats attendus vs réels, ajuste calories/macros selon réponse métabolique observée.

### **4. Gestion Intelligente des Envies**
Intégration des demandes spécifiques avec optimisation nutritionnelle.

### **5. 🆕 Analyse Composition Corporelle (Flux Dédié)**
- **Upload direct d'image** (format data:image/xxx;base64 dans le JSON)
- **Bypass agent** pour traitement direct
- **Guardrail de validation** (vérifie si photo corporelle appropriée)
- **Estimation body fat** avec prompt coach fitness (contourne restrictions OpenAI)
- **Message d'erreur explicite** si image invalide

### **6. Mémoire Conversationnelle RAG**
L'agent se souvient des préférences, historique, feedbacks. Personnalisation croissante.

---

## 🛠️ STACK TECHNIQUE

### **Infrastructure**
- **Base de données :** Supabase (PostgreSQL + pgvector)
- **Orchestration :** n8n Cloud
- **IA Principale :** OpenAI API (GPT-4, GPT-4o, GPT-4o-mini)
- **Embeddings :** OpenAI text-embedding-3-small
- **Recherche web :** Brave Search API
- **Stockage documents :** Google Drive (sync auto)
- **Mémoire chat :** PostgreSQL (n8n memory)

### **Coûts Estimés**
- **Supabase :** Free tier
- **n8n Cloud :** ~€20/mois
- **OpenAI API :** ~€10-20/mois
- **Brave API :** Free tier
- **Total :** ~€30-40/mois

---

## ✅ STATUT DÉVELOPPEMENT

### **Fonctionnalités Implémentées ✅**
- [x] Webhook chat avec interface
- [x] Agent conversationnel avec mémoire
- [x] Tool calcul nutritionnel (BMR, TDEE, macros)
- [x] Tool ajustements hebdomadaires
- [x] RAG documents (sync Google Drive)
- [x] RAG mémoires long terme
- [x] Fetch profil utilisateur
- [x] Recherche web (Brave)
- [x] Analyse image (Google Drive via agent)
- [x] **🆕 Flux body fat analysis (upload direct, bypass agent)**
- [x] **🆕 Guardrail validation image corporelle**

### **À Implémenter 🔄**
- [ ] Génération plans alimentaires 7 jours
- [ ] Création recettes personnalisées
- [ ] Génération liste courses
- [ ] Stockage feedback hebdomadaire en DB
- [ ] Mise à jour profil automatique (body fat)
- [ ] Interface frontend complète

---

## 📞 PROCHAINES ACTIONS

1. **Tester** le flux body fat analysis avec différentes images
2. **Affiner** le prompt d'analyse si GPT-4o refuse encore
3. **Implémenter** le stockage du body fat estimé dans le profil Supabase
4. **Créer** le tool de génération de plans alimentaires
5. **Développer** l'interface frontend avec upload d'image

---

**📌 Document vivant - À mettre à jour au fil de l'avancement**

**Version :** 2.1  
**Dernière modification :** 13 décembre 2025

---

# 🎯 FIN DE LA FICHE DE SYNTHÈSE V2.1
