---
name: body-analyzing
description: Analyse de composition corporelle par image (estimation body fat). Utiliser quand l'utilisateur partage une photo pour estimer son taux de masse grasse.
---

# Body Analyzing - Analyse de Composition Corporelle

## Quand utiliser

- L'utilisateur partage une photo de son corps
- L'utilisateur demande une estimation de son taux de masse grasse
- L'utilisateur veut un feedback sur sa composition corporelle

## Workflow

1. Valide que l'image est appropriee (personne humaine, torse visible)
2. Utilise `image_analysis` avec un prompt de coach fitness bienveillant
3. Presente l'estimation avec une **fourchette** (ex: 16-20%), jamais un chiffre precis
4. Fournis un feedback encourageant et constructif
5. Rappelle TOUJOURS les limites de l'estimation visuelle

## Regles de Presentation

- **Fourchette obligatoire** : Toujours donner une estimation avec marge (ex: "entre 16% et 20%")
- **Ton positif** : Feedback constructif, jamais critique
- **Disclaimer obligatoire** : "Cette estimation est approximative et a but informatif uniquement"
- **Methodes precises** : Recommande DEXA, impedancemetrie, ou pesee hydrostatique pour resultats precis
- **Pas de diagnostic** : Tu n'es PAS un medecin

## Exécution

```python
run_skill_script("body-analyzing", "image_analysis", {
    "image_url": "https://example.com/photo.jpg",
    "analysis_prompt": "Estime le taux de masse grasse, donne une fourchette et un feedback constructif"
})
```

**Scripts disponibles** :
- `scripts/image_analysis.py` : GPT-4o Vision API → analyse body composition → fourchette estimation
