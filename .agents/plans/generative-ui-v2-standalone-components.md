# Plan : Generative UI v2 — Composants autonomes hors bulle de chat

**Branche** : `dev/generative-ui-v2`
**Effort estimé** : ~demi-journée
**Risque** : faible (changement frontend only, pas de modif backend/DB)

---

## Objectif

Actuellement, les composants UI (MacroGauges, DayPlanCard, etc.) sont rendus **à l'intérieur**
de la bulle de message texte. On veut qu'ils puissent être rendus comme des **blocs autonomes**
dans le flux de conversation, entre les bulles de texte.

### Avant (v1)
```
┌─ Bulle AI ──────────────────────┐
│ "Voici votre plan repas..."     │
│                                 │
│ ┌─ MacroGauges ──────────────┐  │
│ │ P: 150g  G: 200g  L: 60g  │  │  ← DANS la bulle
│ └────────────────────────────┘  │
│                                 │
│ ┌─ DayPlanCard ──────────────┐  │
│ │ Lundi : petit-dej/dej/din  │  │  ← DANS la bulle
│ └────────────────────────────┘  │
│                                 │
│ "Tu veux que j'ajuste ?"        │
└─────────────────────────────────┘
```

### Après (v2)
```
┌─ Bulle AI ──────────────────────┐
│ "Voici votre plan repas"        │  ← texte court
└─────────────────────────────────┘

┌─ MacroGauges (pleine largeur) ──┐
│ Protéines ████████░░ 150g       │  ← bloc AUTONOME
│ Glucides  ██████░░░░ 200g       │
│ Lipides   ████░░░░░░  60g       │
└─────────────────────────────────┘

┌─ DayPlanCard (pleine largeur) ──┐
│ Lundi : petit-dej / dej / dîner │  ← bloc AUTONOME
└─────────────────────────────────┘

┌─ Bulle AI ──────────────────────┐
│ "Tu veux que j'ajuste ?"        │  ← bulle texte séparée
└─────────────────────────────────┘
```

---

## Architecture actuelle (ce qu'on ne change PAS)

### Backend (aucun changement)
- `src/ui_components.py` : extraction `<!--UI:Component:{json}-->` → zone mapping → OK
- `src/api.py` : streaming NDJSON avec chunks `ui_component` → OK
- `src/db_utils.py` : stockage `message.ui_components[]` → OK

### Frontend data flow (aucun changement)
- `api.ts` : parse NDJSON, émet chunks `ui_component` → OK
- `MessageHandling.tsx` : accumule les composants dans `message.ui_components[]` → OK
- Types : `Message.message.ui_components` → OK

---

## Ce qui change (frontend rendering only)

### Fichiers à modifier

| Fichier | Changement |
|---------|-----------|
| `MessageItem.tsx` | Supprimer le rendu de ComponentRenderer (lignes 229-235) |
| `MessageList.tsx` | Rendre les composants comme blocs autonomes ENTRE les messages |
| `ComponentRenderer.tsx` | Ajouter une variante `standalone` (pleine largeur, pas de max-width) |

### Étape 1 : Nouveau type de bloc dans le flux de conversation

**Fichier** : `frontend/src/types/database.types.ts` ou `generative-ui.types.ts`

Actuellement le flux de messages est `Message[]`. On ajoute un type union :

```typescript
type ConversationBlock =
  | { type: 'message'; data: Message }
  | { type: 'ui_components'; data: UIComponentBlock[]; messageId: string };
```

### Étape 2 : Transformer les messages en blocs

**Fichier** : `MessageList.tsx`

Ajouter une fonction `flattenToBlocks(messages: Message[]): ConversationBlock[]` :

```
Pour chaque message :
  1. Si le message a du texte → émettre un bloc { type: 'message', data: message_sans_components }
  2. Si le message a des ui_components → émettre un bloc { type: 'ui_components', data: components }
```

Résultat : au lieu de rendre une liste de messages, on rend une liste de blocs.

### Étape 3 : Rendu des blocs autonomes

**Fichier** : `MessageList.tsx`

```tsx
{blocks.map(block => {
  if (block.type === 'message') {
    return <MessageItem message={block.data} ... />;
  }
  if (block.type === 'ui_components') {
    return <ComponentRenderer components={block.data} variant="standalone" />;
  }
})}
```

### Étape 4 : Variante standalone du ComponentRenderer

**Fichier** : `ComponentRenderer.tsx`

```tsx
// Ajouter une prop variant
interface Props {
  components: UIComponentBlock[];
  variant?: 'inline' | 'standalone';  // inline = dans la bulle (v1), standalone = pleine largeur (v2)
  ...
}

// Si standalone : pas de max-w-4xl, padding pleine largeur, animation d'entrée
```

### Étape 5 : Supprimer le rendu inline dans MessageItem

**Fichier** : `MessageItem.tsx` (lignes 229-235)

Supprimer le bloc conditionnel qui rend `<ComponentRenderer>` dans la bulle.
Le rendu est maintenant géré par MessageList.

### Étape 6 : Gérer le streaming (composants apparaissent en temps réel)

Pas de changement dans `MessageHandling.tsx` — les composants sont toujours accumulés
dans `message.ui_components[]`. La fonction `flattenToBlocks` est recalculée à chaque
update de messages → les blocs composants apparaissent au fur et à mesure.

---

## Cas edge à gérer

1. **Messages historiques** (chargés depuis la DB) : même traitement — `flattenToBlocks`
   s'applique aussi aux messages stockés qui ont des `ui_components`.

2. **Message sans texte, que des composants** : la bulle texte est vide → ne pas la rendre.
   `flattenToBlocks` doit vérifier `content.trim().length > 0` avant d'émettre un bloc message.

3. **Messages humains** : jamais de composants → toujours un bloc `message`.

4. **Animations** : les blocs composants autonomes devraient avoir une animation d'entrée
   (fade-in + slide-up) pour un effet "wow". Utiliser les transitions CSS existantes.

---

## Tests

- [ ] Build frontend sans erreur (`npm run build`)
- [ ] Vérifier visuellement : envoyer "fais-moi un plan repas" → les composants sortent des bulles
- [ ] Vérifier mobile (390x844) : les composants standalone sont bien pleine largeur
- [ ] Vérifier historique : recharger la page → les anciens messages avec composants s'affichent correctement
- [ ] Vérifier streaming : les composants apparaissent en temps réel pendant la génération

---

## Ce qu'on ne fait PAS dans cette version

- Pas de nouvelle zone "floating" ou "sidebar" — les composants restent dans le flux vertical
- Pas de drag & drop ou réorganisation
- Pas de changement backend (le format NDJSON reste identique)
- Pas de nouveau composant — on utilise les 7 existants
