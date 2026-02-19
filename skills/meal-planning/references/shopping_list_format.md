# Format de Liste de Courses

## Parametres

- `week_start` : Date de debut (YYYY-MM-DD, auto si omis)
- `selected_days` : Indices de jours [0-6] (0=Lundi, optionnel = tous)
- `servings_multiplier` : Multiplicateur de portions (defaut 1.0)

## Format de Presentation

```
Liste de courses generee (7 jours)

Resume
- 42 articles au total
- 6 categories

Fruits & Legumes (15 articles)
- Tomate : 1200g
- Oignon : 450g
- Banane : 14 pieces
- ...

Proteines (8 articles)
- Poulet : 1400g
- Saumon : 600g
- Oeufs : 18 pieces
- ...

Feculents (6 articles)
- Riz : 1050g
- Pates : 400g
- ...

Astuce
Tu peux generer une liste pour quelques jours seulement : "Liste pour lundi-mercredi"
ou ajuster les quantites : "Liste x2 pour meal prep"
```
