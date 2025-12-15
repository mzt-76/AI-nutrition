# Scientifically Validated Nutritional Knowledge Base for AI Meal Planning

This comprehensive knowledge base synthesizes current scientific consensus across 10 nutritional domains, designed for RAG retrieval by a personalized AI nutrition agent generating weekly meal plans for healthy adults aged 18-65. All recommendations prioritize peer-reviewed meta-analyses, position stands from ISSN and AND, and official dietary guidelines.

---

## Domain 1: Nutritional Fundamentals

### Synthesis of Current Knowledge

The scientific consensus from IOM Dietary Reference Intakes, DGA 2020-2025, and EFSA establishes Acceptable Macronutrient Distribution Ranges (AMDR) for adults: **carbohydrates 45-65%** of total energy, **protein 10-35%**, and **fats 20-35%**. The minimum carbohydrate requirement is 130g/day based on brain glucose needs, while protein RDA for sedentary adults stands at 0.8g/kg/day. For active individuals, the ISSN 2017 Position Stand recommends **1.4-2.0g protein/kg/day**, with higher intakes of 2.3-3.1g/kg during caloric restriction for lean mass preservation. Essential fatty acids require linoleic acid at 11-17g/day and alpha-linolenic acid at 1.1-1.6g/day.

Key micronutrients of public health concern include vitamin D (RDA: 15-20μg/day), calcium (1000-1300mg/day), iron (8-18mg/day with higher needs for menstruating women), and vitamin B12 (2.4μg/day). EFSA's comprehensive review confirms nutrient bioavailability varies significantly based on food matrix, preparation methods, and nutrient interactions. Populations at deficiency risk include elderly (B12, D), women of childbearing age (folate, iron), vegans/vegetarians (B12, iron, zinc), and those with limited sun exposure (vitamin D).

For fiber, the landmark Reynolds et al. 2019 Lancet meta-analysis demonstrates intakes of **25-29g/day** are associated with 15-24% reduced mortality from CVD, type 2 diabetes, and colorectal cancer. EFSA recommends total water intake of **2.5L/day for men** and **2.0L/day for women** including food moisture. The glycemic index categorizes carbohydrates by blood glucose impact: Low GI ≤55, Medium 56-69, High ≥70.

### Exploitable Quantitative Data

| Parameter | Recommendation | Source |
|-----------|----------------|--------|
| **Protein (sedentary)** | 0.8 g/kg/day | IOM RDA |
| **Protein (active adults)** | 1.4-2.0 g/kg/day | ISSN 2017 |
| **Protein (weight loss)** | 2.3-3.1 g/kg lean mass | ISSN 2017 |
| **Protein (per meal)** | 0.25-0.40 g/kg (20-40g absolute) | ISSN 2017 |
| **Carbohydrates AMDR** | 45-65% of energy | DGA 2020-2025 |
| **Fat AMDR** | 20-35% of energy | DGA 2020-2025 |
| **Saturated fat** | <10% of energy | DGA 2020-2025 |
| **EPA+DHA** | 250-500mg/day | EFSA/AHA |
| **Fiber (men)** | 38g/day | IOM |
| **Fiber (women)** | 25g/day | IOM |
| **Water (men)** | 2.5L/day total | EFSA |
| **Water (women)** | 2.0L/day total | EFSA |
| **Vitamin D** | 15-20μg (600-800 IU) | IOM |
| **Iron (women 19-50)** | 18mg/day | IOM |
| **Vitamin B12** | 2.4μg/day | IOM |

### Practical Applications for AI Agent

**Macronutrient distribution algorithm:**
- General health: Protein 15-20%, Carbs 45-55%, Fat 25-35%
- Muscle gain: Protein 25-30% (1.6-2.2g/kg), Carbs 45-55%, Fat 20-30%
- Fat loss: Protein 25-35% (2.0-2.5g/kg lean mass), Carbs 35-45%, Fat 20-30%

**Fiber per meal target:** 8-12g distributed across 3-4 meals
**GI meal rule:** Aim for meal GL ≤20; pair high-GI foods with protein, fat, or fiber

### Confidence Level
**HIGH** — Strong consensus from IOM, EFSA DRVs, ISSN position stands, and multiple meta-analyses.

### Main Sources
1. DGA 2020-2025 (DietaryGuidelines.gov)
2. ISSN Position Stand: Protein and Exercise (2017) — DOI: 10.1186/s12970-017-0177-8
3. EFSA Dietary Reference Values Summary Report (2017)
4. Reynolds A et al., Lancet (2019) — DOI: 10.1016/S0140-6736(18)31809-9

---

## Domain 2: Metabolism & Energy Expenditure (DEEP DIVE)

### Synthesis of Current Knowledge

The **Mifflin-St Jeor equation is the most accurate** predictive formula for BMR in healthy adults, predicting within ±10% of measured values in 82% of non-obese and 70% of obese individuals according to Frankenfield's 2005 systematic review. The Harris-Benedict equation overestimates by approximately 5% in modern populations. The Katch-McArdle formula offers superior accuracy for lean, athletic individuals when body fat percentage is accurately known.

Total Daily Energy Expenditure (TDEE) comprises three primary components: **BMR (60-75%)**, **Thermic Effect of Food (TEF, ~10%)**, and **Activity Thermogenesis (15-30%)**. TEF varies by macronutrient: protein requires 20-30% of calories for digestion, carbohydrates 5-10%, and fat 0-3%. Non-Exercise Activity Thermogenesis (NEAT) can vary by up to **2,000 kcal/day** between similar-sized individuals according to Levine's Mayo Clinic research.

Metabolic adaptation during caloric restriction is well-documented. The CALERIE studies show adaptation of **80-120 kcal/day** below predicted values, developing within 1-2 weeks of deficit initiation. A 2022 systematic review of 33 studies (2,528 participants) confirmed adaptive thermogenesis occurs in the majority of diet-induced weight loss scenarios. Importantly, "metabolic damage" as commonly described is largely myth—metabolism adapts but doesn't permanently break; recovery occurs when energy balance is restored.

Individual metabolic variation is substantial: BMR can vary 2-3 fold among individuals of equivalent body mass, age, sex, and activity level. A 2005 meta-analysis found **26% of BMR variance remains unexplained** after accounting for fat-free mass, fat mass, and age. Genetic studies indicate approximately **40% of variance in RMR** is explained by inherited characteristics.

### Exploitable Quantitative Data

**BMR Formulas (Complete with Coefficients):**

| Formula | Equation |
|---------|----------|
| **Mifflin-St Jeor (Men)** | BMR = (10 × weight[kg]) + (6.25 × height[cm]) – (5 × age) + 5 |
| **Mifflin-St Jeor (Women)** | BMR = (10 × weight[kg]) + (6.25 × height[cm]) – (5 × age) – 161 |
| **Harris-Benedict Original (Men)** | BMR = 66.47 + (13.75 × weight[kg]) + (5.003 × height[cm]) – (6.75 × age) |
| **Harris-Benedict Original (Women)** | BMR = 655.1 + (9.563 × weight[kg]) + (1.850 × height[cm]) – (4.676 × age) |
| **Katch-McArdle** | BMR = 370 + (21.6 × Lean Body Mass[kg]) |

**Activity Multipliers (PAL):**

| Activity Level | Description | Multiplier |
|----------------|-------------|------------|
| Sedentary | Desk job, little exercise | 1.2 |
| Lightly Active | Light exercise 1-3 days/week | 1.375 |
| Moderately Active | Moderate exercise 3-5 days/week | 1.55 |
| Very Active | Hard exercise 6-7 days/week | 1.725 |
| Extra Active | Very hard exercise, physical job | 1.9 |

**TEF by Macronutrient:**
- Protein: 20-30%
- Carbohydrates: 5-10%
- Fat: 0-3%
- Mixed diet: ~10%

**Metabolic Rates by Tissue:**
- Fat-free mass: ~13 kcal/kg/day
- Fat mass: ~4.5-5 kcal/kg/day
- Age-related decline: 1-2% per decade after age 20

**Adaptive Thermogenesis:**
- Week 1 at 50% deficit: -178 ± 137 kcal/day
- Average sustained adaptation: 80-120 kcal/day below predicted

### Practical Applications for AI Agent

**Formula Selection Algorithm:**
```
IF body_fat_percentage KNOWN AND measurement_reliable:
    IF body_fat < 15% (men) OR < 25% (women):
        USE Katch-McArdle
    ELSE:
        USE Mifflin-St Jeor
ELSE:
    USE Mifflin-St Jeor (default)
```

**TDEE Adjustment Rules:**
- Recalculate BMR every 10 lbs (4.5 kg) weight change
- After 8+ weeks in deficit: assume 5-10% reduction in predicted TDEE
- Implement diet breaks (1-2 weeks at maintenance) every 8-12 weeks

**Plateau Detection Protocol:**
- Definition: <0.5 lb/week loss for 2+ consecutive weeks with confirmed tracking
- Response: First verify tracking → Increase NEAT → Adjust calories by 100-150 kcal → Consider diet break

### Confidence Level
- **BMR formulas accuracy:** HIGH — Multiple systematic reviews validate Mifflin-St Jeor superiority
- **TDEE components:** HIGH — Replicated across populations
- **Adaptive thermogenesis magnitude:** MODERATE-HIGH — Growing evidence base with some methodological variation
- **Activity multipliers:** MODERATE-HIGH — Individual variation significant

### Main Sources
1. Frankenfield D et al., JADA (2005) — Systematic review of BMR equations
2. Mifflin MD et al., AJCN (1990) — Original equation publication
3. Heinitz S et al., Metabolism (2020) — Adaptive thermogenesis study
4. Nunes CL et al., BJN (2021) — Systematic review on adaptive thermogenesis
5. Levine JA, Science (2005) — NEAT variation research

---

## Domain 3: Nutrition by Goals (DEEP DIVE)

### Synthesis of Current Knowledge

**Weight Loss:** Current evidence strongly supports moderate caloric deficits of **250-500 kcal/day (15-25% TDEE)** as optimal for preserving lean mass. Meta-analyses demonstrate deficits exceeding 500 kcal/day significantly impair lean body mass retention even with resistance training. The Garthe et al. study showed athletes losing **0.7% body weight/week** achieved muscle gains while those losing 1.4%/week had unchanged LBM. The ISSN recommends elevated protein of **2.3-3.1g/kg/day** during hypocaloric periods for muscle preservation.

**Muscle Gain:** The prevailing view that large caloric surpluses are necessary has been challenged. The Helms et al. 2023 study found **5% vs 15% surpluses** produced similar muscle thickness gains but fivefold greater fat accumulation in higher surplus groups. The ISSN recommends **1.6-2.2g/kg/day protein** for muscle building, with **0.25-0.4g/kg per meal** (20-40g absolute) optimally stimulating muscle protein synthesis. The leucine threshold is **2.5-3.0g per meal** for young adults, 3-4g for older adults.

**Athletic Performance:** The rigid 30-minute "anabolic window" has been largely debunked. Per the ISSN Position Stand, the anabolic effect of exercise persists at least 24 hours. Immediate post-workout nutrition is only critical when training fasted. For rapid glycogen restoration (<4h recovery), aggressive carbohydrate refeeding at **1.2g/kg/h** with high-GI sources is recommended.

**General Health:** The Mediterranean diet has the strongest evidence base. The PREDIMED trial demonstrated a **30% reduction in cardiovascular events** with additional benefits for breast cancer prevention and cognitive function.

### Exploitable Quantitative Data

**WEIGHT LOSS PARAMETERS:**

| Parameter | Value | Source |
|-----------|-------|--------|
| Caloric deficit range | 250-500 kcal/day (15-25% TDEE) | Meta-analyses |
| Protein requirement | 2.3-3.1 g/kg/day | ISSN 2017 |
| Optimal loss rate | 0.5-1.0% body weight/week | Garthe et al. |
| Elite/lean athletes | 0.7% BW/week max | Elite athlete studies |
| Minimum calories (women) | ≥1200 kcal/day | Position papers |
| Minimum calories (men) | ≥1500 kcal/day | Position papers |

**MUSCLE GAIN PARAMETERS:**

| Parameter | Value | Source |
|-----------|-------|--------|
| Caloric surplus (beginners) | 300-500 kcal/day (5-10% TDEE) | Research consensus |
| Caloric surplus (advanced) | 200-300 kcal/day (5% TDEE) | Helms et al. 2023 |
| Protein requirement | 1.6-2.2 g/kg/day | ISSN + meta-analyses |
| Protein per meal | 20-40g (0.25-0.4 g/kg) | MPS dose-response |
| Leucine threshold (young) | 2.5-3.0g per meal | Norton et al. |
| Leucine threshold (older) | 3.0-4.0g per meal | Aging studies |
| Carbohydrate (hypertrophy) | 4-7 g/kg/day | ISSN |
| Meal frequency | 4-6 protein doses/day (every 3-4h) | ISSN |
| Pre-sleep protein | 30-40g casein | ISSN |

**ATHLETIC PERFORMANCE:**

| Timing | Recommendation |
|--------|----------------|
| Pre-workout meal | 3-4h before: 1-4 g/kg carbs |
| Pre-workout snack | 30-60 min before: 30-60g carbs |
| Post-workout protein | 20-40g within 2 hours |
| Rapid glycogen recovery | 1.2 g/kg/h carbs (high GI) |
| Hydration during exercise | 200-300 mL every 15-20 min |
| Post-exercise rehydration | 150% of weight lost |
| Caffeine (performance) | 3-6 mg/kg, 60 min pre-exercise |

**RATE OF MUSCLE GAIN EXPECTATIONS:**

| Training Level | Male Rate | Female Rate |
|---------------|-----------|-------------|
| Beginner (Year 1) | 0.9-1.3 kg/month | 0.45-0.65 kg/month |
| Intermediate (Year 2-3) | 0.45-0.9 kg/month | 0.22-0.45 kg/month |
| Advanced (Year 4+) | 0.2-0.45 kg/month | 0.1-0.22 kg/month |

### Practical Applications for AI Agent

**Goal-Based Calorie Calculation:**
```
WEIGHT LOSS:
1. Calculate TDEE using Mifflin-St Jeor
2. Subtract 250-500 kcal (or 15-25% TDEE)
3. Set protein: 2.3-2.7 g/kg body weight
4. Set fat: 0.8-1.0 g/kg (minimum)
5. Remaining calories → carbohydrates

MUSCLE GAIN:
1. Calculate TDEE
2. Add 5-10% (200-350 kcal) for beginners; 5% for advanced
3. Set protein: 1.6-2.2 g/kg
4. Set carbs: 4-7 g/kg
5. Remaining → fat
```

**Progress Adjustment Rules:**
- Weight loss <0.3 kg/week for 2 weeks: Reduce calories 100-150 kcal
- Weight loss >1 kg/week: Increase calories 100-200 kcal
- Strength decreasing: Increase protein to 2.5-3.0 g/kg, reduce deficit

**Red Flags for Professional Referral:**
- BMI <18.5 seeking weight loss
- History of eating disorders
- Diabetes (Type 1 or uncontrolled Type 2)
- Pregnancy/breastfeeding
- Significant unintended weight changes (>5% in 1 month)

### Confidence Level
- **Weight loss deficit/protein:** HIGH — ISSN position stand, multiple meta-analyses
- **Muscle gain protein needs:** HIGH — Extensive meta-analyses confirm 1.6-2.2 g/kg
- **Nutrient timing (anabolic window):** HIGH — Myth largely debunked
- **Mediterranean diet CVD benefits:** HIGH — PREDIMED RCT, multiple meta-analyses

### Main Sources
1. ISSN Position Stand: Protein and Exercise (2017)
2. ISSN Position Stand: Nutrient Timing (2017)
3. Garthe I et al., IJSNEM (2011)
4. Helms ER et al., Sports Med Open (2023)
5. PREDIMED Trial, NEJM (2018)

---

## Domain 4: Nutrient Timing & Frequency

### Synthesis of Current Knowledge

**Chronobiology:** Circadian rhythms profoundly influence nutrient metabolism. Glucose tolerance and insulin sensitivity are highest in the morning and decrease toward evening. A 2023 meta-analysis of 9 RCTs showed significantly greater weight loss when energy intake was concentrated earlier in the day. The thermic effect of food is greater in the morning compared to evening.

**Meal Frequency:** The scientific consensus conclusively shows that **meal frequency does NOT significantly affect metabolic rate** when total energy intake is controlled. A 2024 JAMA Network Open meta-analysis of 29 RCTs found that lower meal frequency (2-3 meals/day) may actually reduce body weight compared to higher frequencies (≥6 meals/day).

**Anabolic Window:** The strict 30-minute post-workout window is **largely mythologized**. According to the ISSN and Aragon/Schoenfeld (2013), the anabolic response to a mixed meal lasts up to 6 hours. The practical window extends to **3-6 hours** surrounding training. If training fasted, post-exercise protein within ~2 hours becomes more critical.

**Intermittent Fasting:** An umbrella review in eClinicalMedicine (2024) analyzing 153 studies found IF is **comparable to continuous energy restriction** for weight loss—not superior. Alternate-day fasting shows highest effectiveness, followed by 5:2, then time-restricted eating (16:8). Early time-restricted eating (finishing meals before evening) improves metabolic outcomes beyond late TRE.

### Exploitable Quantitative Data

| Parameter | Value | Source |
|-----------|-------|--------|
| **Protein per meal for MPS** | 20-40g (0.25-0.4 g/kg) | ISSN |
| **Time between protein feedings** | Every 3-4 hours | Moore et al. 2012 |
| **Post-workout window (actual)** | 3-6 hours surrounding training | Research consensus |
| **If training fasted** | Within 2 hours post-exercise | ISSN |
| **Pre-sleep protein** | 30-40g casein, 30 min before bed | ISSN |

**Intermittent Fasting Protocols:**

| Protocol | Structure | Weight Loss Range |
|----------|-----------|-------------------|
| 16:8 (TRE) | 16h fast, 8h eating | 0.95-8.60% body weight |
| 5:2 | 5 normal days, 2 × 500-600 kcal | 1.70-7.97% body weight |
| Alternate Day Fasting | 25% calories every other day | 0.77-12.97% body weight |

### Practical Applications for AI Agent

**Default Meal Timing Templates:**

*Standard (3 meals + snack):*
- Breakfast: 7-8am (~25-30g protein, higher carbs)
- Lunch: 12-1pm (~25-30g protein, moderate carbs)
- Dinner: 6-7pm (~25-30g protein)
- Pre-sleep: 30 min before bed (30-40g casein if desired)

*Training Day (PM workout):*
- Normal meals through lunch
- Pre-workout (1-2h before): 20g protein + carbs
- Post-workout: 20-40g protein + 0.5-1.0 g/kg carbs
- Pre-sleep protein if training ends late

**When to Recommend IF vs Regular Meals:**
- **IF recommended:** Weight loss goal, prefers fewer larger meals, metabolic syndrome, struggles with snacking
- **Regular meals recommended:** Muscle gain goal, athletes with high training volumes, history of eating disorders, Type 1 diabetes, pregnancy

### Confidence Level
- **Meal frequency and metabolism:** HIGH — Multiple meta-analyses show no effect
- **Anabolic window duration:** HIGH — Meta-analyses confirm flexible 3-6h window
- **IF vs CER equivalence:** HIGH — Large umbrella reviews confirm similar outcomes
- **Pre-sleep protein benefits:** MODERATE-HIGH — Strong acute MPS data

### Main Sources
1. ISSN Position Stand: Nutrient Timing (2017)
2. Aragon & Schoenfeld, JISSN (2013)
3. eClinicalMedicine IF Umbrella Review (2024)
4. JAMA Network Open Meta-Analysis (2024)

---

## Domain 5: Food Combinations & Synergies

### Synthesis of Current Knowledge

**Iron and Vitamin C:** While mechanistically, vitamin C enhances iron absorption 2-6 fold in single meals, recent meta-analyses show clinically modest long-term effects (+0.14 g/dL hemoglobin). For practical meal planning, include **50-100mg vitamin C** with iron-rich meals for optimal absorption.

**Fat-Soluble Vitamins:** Absorption of vitamins A, D, E, K is markedly reduced when diets contain ≤5g/day of fat. Research indicates **~11g fat is optimal** for vitamin D absorption—higher fat content paradoxically reduced absorption by 16-20%.

**Antagonistic Interactions:** Calcium inhibits iron absorption by 40-60% at doses above 300mg per meal. **Separation of 1-2 hours** between calcium and iron intake is recommended. Phytates in grains and legumes can be reduced by 16-88% through soaking, germination, and fermentation. Tannins in tea/coffee reduce non-heme iron absorption by 50-60%; a 1-hour separation reduces this inhibition by 50%.

**Plant Protein Complementation:** Current consensus from AND indicates complementary proteins do NOT need to be consumed at the same meal. The body maintains amino acid pools over 24 hours. DIAAS (Digestible Indispensable Amino Acid Score) has superseded PDCAAS as the FAO-recommended standard for protein quality assessment.

### Exploitable Quantitative Data

**Enhancement Effects:**

| Combination | Effect | Magnitude |
|-------------|--------|-----------|
| Iron + Vitamin C (per meal) | Enhanced iron absorption | 2-6 fold increase |
| Fat-soluble vitamins + fat | Enables absorption | Minimum 5g, optimal 10-15g |
| Curcumin + piperine (black pepper) | Bioavailability increase | 2000% (20-fold) |

**Antagonistic Interactions:**

| Interaction | Effect | Mitigation |
|-------------|--------|------------|
| Calcium + Iron | 40-60% iron reduction at >300mg calcium | Separate by 2 hours |
| Tea/coffee + Iron | 50-60% iron reduction | Separate by 1 hour |
| Phytates + minerals | Impaired zinc, iron absorption | Soak, ferment, or cook |

**Protein Quality Scores (DIAAS):**

| Protein Source | DIAAS Score |
|----------------|-------------|
| Whole milk | 132 |
| Whey protein | 109-125 |
| Egg | 113 |
| Chicken breast | 108 |
| Soy protein isolate | 90-98 |
| Pea protein | 64-82 |

**Leucine Threshold:**
- Young adults: 2-2.5g per meal
- Older adults: 3-4g per meal

### Practical Applications for AI Agent

**Iron-Rich Meal Rules:**
- ADD vitamin C source ≥50mg (citrus, bell pepper, tomato)
- AVOID tea/coffee within 1-2 hours
- AVOID calcium-rich foods >300mg in same meal

**Fat Inclusion for Vitamins:**
- Include ≥5g fat minimum, optimal 10-15g
- Use oil-based dressings with salads containing carotenoids
- Add avocado, nuts, or olive oil to vitamin-rich meals

**Vegetarian Protein Pairing:**
- Legume + Grain = Complete (rice + beans, hummus + pita)
- Same-meal combining NOT required (24-hour window)
- Complete sources (no pairing needed): soy, quinoa, buckwheat, hemp seeds

### Confidence Level
- **Iron + Vitamin C enhancement:** HIGH for mechanism, MODERATE for clinical significance
- **Fat-soluble vitamin absorption:** HIGH
- **Calcium-iron competition:** HIGH
- **Plant protein complementation:** HIGH — Same-meal combining unnecessary

### Main Sources
1. FAO Expert Consultation on Protein Quality (2013)
2. PMC reviews on nutrient interactions and bioavailability (2020-2024)
3. DIAAS methodology papers

---

## Domain 6: Hunger & Satiety Management

### Synthesis of Current Knowledge

The foundational **Satiety Index** research by Holt et al. (1995) found dramatic differences in satiating capacity among isoenergetic foods. **Boiled potatoes scored 323%** (vs. white bread at 100%), while croissants scored only 47%. Significant positive correlations were found with: serving weight (r=0.66), protein content (r=0.37), fiber content (r=0.46), and water content (r=0.64). Fat content correlated negatively with satiety.

The **protein leverage hypothesis** posits that humans strongly regulate protein intake, causing overconsumption of fats and carbohydrates on protein-dilute diets. Meta-analyses confirm protein consumption significantly decreases hunger and increases satiety, while modulating satiety hormones: decreasing ghrelin, increasing CCK and GLP-1.

The **Volumetrics approach** emphasizes energy density (kcal/g). Category 1 foods (<0.6 kcal/g) include non-starchy vegetables, broth soups, and most fruits. Category 4 foods (>4 kcal/g) include chips, crackers, butter, and oils. Systematic reviews show higher fiber intakes correlate with decreased energy intake and body weight.

Sleep deprivation disrupts appetite hormones: studies show **18% reduction in leptin** and **28% increase in ghrelin** with sleep restriction, leading to 24% increased hunger.

### Exploitable Quantitative Data

**Satiety Index Scores (White Bread = 100%):**

| Food | Satiety Index |
|------|---------------|
| Boiled potatoes | 323% |
| Fish | 225% |
| Oatmeal/porridge | 209% |
| Oranges | 202% |
| Apples | 197% |
| Beef | 176% |
| Eggs | 150% |
| Croissant | 47% |
| Cake | 65% |
| Doughnut | 68% |

**Energy Density Categories:**

| Category | kcal/g | Examples |
|----------|--------|----------|
| 1 (very low) | <0.6 | Vegetables, fruits, broth soups |
| 2 (low) | 0.6-1.5 | Lean proteins, legumes, whole grains |
| 3 (medium) | 1.5-4.0 | Cheese, bread, ice cream |
| 4 (high) | >4.0 | Chips, crackers, butter, oils |

**Protein and Satiety:**
- Optimal per meal: 20-30g
- Daily for weight loss: 25-30% of calories (1.8-2.9 g/kg)

**Fiber for Satiety:**
- Target: 25-38g/day
- Per meal: 8-12g for optimal satiety

### Practical Applications for AI Agent

**High-Satiety Meal Composition:**
1. Include 25-30g protein per meal minimum
2. Start with low-energy-density foods (salad, soup, vegetables)
3. Include ≥8g fiber per meal from whole foods
4. Keep added fats moderate
5. Avoid ultra-processed carb+fat combinations

**Meal Sequencing Strategy:**
1. First course: Large salad or broth-based vegetable soup
2. Second: Protein portion with vegetables
3. Third: Starchy carbohydrates (if included)

**Sleep Optimization:** Target 7-9 hours to prevent ghrelin surge and leptin drop

### Confidence Level
- **Satiety Index scores:** HIGH — Validated methodology
- **Protein-satiety relationship:** HIGH — Multiple meta-analyses
- **Energy density/Volumetrics:** HIGH — Strong RCT evidence
- **Sleep-hunger hormone connection:** MODERATE-HIGH

### Main Sources
1. Holt SHA et al., EJCN (1995) — Satiety Index study
2. Simpson & Raubenheimer, Obesity Reviews (2005) — Protein leverage hypothesis
3. Rolls BJ, Volumetrics research program, Penn State

---

## Domain 7: Specific Diets

### Synthesis of Current Knowledge

**Vegetarian/Vegan:** The AND 2025 position confirms appropriately planned vegetarian and vegan diets are nutritionally adequate across all life stages. Key nutrients requiring attention: vitamin B12 (requires supplementation for all vegans), iron (1.8× higher intake recommended due to lower non-heme absorption), zinc, omega-3s (DHA/EPA), and calcium.

**Ketogenic:** Ketosis is achieved by restricting carbohydrates to **<50g/day** (typically 20-50g). An umbrella review of 23 meta-analyses found high-quality evidence for weight loss (-10 to -15.6 kg with VLCKD) and improved glycemic control (HbA1c -0.7%). The "keto flu" occurs in ~60% of beginners within 2-7 days, typically resolving within 1-4 weeks. Long-term safety data beyond 2 years is limited, and LDL cholesterol increases are a concern.

**Mediterranean:** The PREDIMED trial demonstrated a **30% reduction in major cardiovascular events**, 40% reduction in new-onset diabetes, and improvements in multiple metabolic markers. This represents the strongest evidence base among named diets.

**Intermittent Fasting:** Meta-analyses confirm IF is comparable—not superior—to continuous energy restriction for weight loss. ADF shows highest weight loss probability, followed by 5:2, then TRE.

**Gluten-Free:** Non-celiac gluten sensitivity remains controversial with no validated biomarkers. Celiac disease must be excluded through serology and biopsy BEFORE gluten elimination. Unnecessary GFD carries risks including reduced fiber and B vitamins.

### Exploitable Quantitative Data

**Vegetarian/Vegan Supplementation:**

| Nutrient | Vegan Dose | Notes |
|----------|------------|-------|
| Vitamin B12 (daily) | 50-100 µg cyanocobalamin | Essential for all vegans |
| Vitamin B12 (weekly) | 2000 µg once weekly | Alternative dosing |
| Iron RDA multiplier | 1.8× omnivore RDA | Due to lower absorption |
| Omega-3 (EPA+DHA) | 250-500mg algae-sourced | Essential fatty acids |

**Ketogenic:**

| Parameter | Value |
|-----------|-------|
| Carb threshold for ketosis | 20-50 g/day net carbs |
| Time to enter ketosis | 2-4 days |
| Keto flu onset | Days 1-7 |
| Keto flu duration | 1-4 weeks |
| Sodium during adaptation | 3,000-5,000 mg/day |

**Mediterranean Diet Components:**

| Component | Frequency |
|-----------|-----------|
| Extra-virgin olive oil | 1-4 tbsp/day |
| Fish/seafood | 2-3 servings/week |
| Vegetables | 3+ servings/day |
| Legumes | 3+ servings/week |
| Nuts | 30g/day |
| Red meat | <2 servings/week |

### Practical Applications for AI Agent

**Diet Selection Decision Tree:**
- Cardiovascular risk → Mediterranean diet (strongest evidence)
- Ethical/environmental preference → Vegetarian/Vegan with supplementation
- Blood sugar control → Keto/Low-carb OR Mediterranean
- Weight loss (any protocol) → Sustainable preference-based approach

**Contraindications:**
- **Ketogenic:** Type 1 diabetes (without supervision), pregnancy, eating disorder history, kidney/liver disease
- **IF:** Type 1 diabetes, eating disorders, pregnancy, children/adolescents
- **Gluten-free:** Never recommend without proper celiac testing first

**Required Supplements by Diet:**
- **Vegan:** B12 (essential), Vitamin D, Omega-3 algae oil, consider iron/zinc
- **Ketogenic:** Electrolytes (Na, K, Mg) during adaptation
- **Mediterranean:** None typically needed

### Confidence Level
- **Mediterranean CVD benefits:** HIGH — PREDIMED RCT, multiple meta-analyses
- **Vegetarian/Vegan adequacy:** MODERATE-HIGH — AND position, requires planning
- **Ketogenic short-term weight loss:** MODERATE — Effective but limited long-term data
- **IF vs CER equivalence:** MODERATE — No superiority demonstrated

### Main Sources
1. AND Position Paper: Vegetarian Dietary Patterns (2025)
2. PREDIMED Trial, NEJM (2018)
3. BMC Medicine Ketogenic Diet Umbrella Review (2023)
4. Obesity IF Meta-analysis (2023)

---

## Domain 8: Metabolic Adaptations & Learning

### Synthesis of Current Knowledge

**Metabolic Adaptation:** The CALERIE studies provide strong evidence that metabolic adaptation ranges from **80-120 kcal/day** lower than predicted based on weight loss alone. This adaptation develops within 1-2 weeks of caloric deficit initiation, with maximum adaptation reached after 10% weight loss or 12-20 weeks. The adaptation persists even after weight stabilization but recovers when energy balance is restored.

**Weight Cycling:** Research shows 15/18 studies found no significant adverse effects on metabolism from weight cycling in healthy individuals. However, weight cycling is associated with 23% increased diabetes risk and correlates with higher CVD mortality. The popular belief that weight cycling "permanently damages" metabolism is NOT supported—metabolism can recover with appropriate strategies.

**Reverse Dieting:** Evidence remains LIMITED. A 2024 RCT (n=49) found no significant differences in weight regain between reverse dieting, immediate maintenance return, or ad libitum eating. Claims that reverse dieting can "boost metabolism" beyond baseline are NOT supported by current evidence.

**Stress and Cortisol:** Cortisol affects body weight through increased appetite, enhanced visceral fat storage, muscle breakdown, and impaired insulin sensitivity. Sleep deprivation reduces morning RMR by ~5% and postprandial thermogenesis by 20%, while disrupting appetite hormones.

### Exploitable Quantitative Data

| Parameter | Value | Confidence |
|-----------|-------|------------|
| Average metabolic adaptation | 80-120 kcal/day below predicted | HIGH |
| Time to develop | 1-4 weeks | MODERATE-HIGH |
| Calorie adjustment increments | 100-200 kcal/day | MODERATE |
| Reverse diet rate | 50-100 kcal/week increase | LOW-MODERATE |
| Minimum weeks between adjustments | 2-4 weeks | MODERATE-HIGH |
| Weight plateau definition | 4+ weeks no change | Clinical consensus |
| Sleep deprivation RMR effect | ~5% reduction | MODERATE |

### Practical Applications for AI Agent

**Calorie Adjustment Algorithm:**
```
IF (weight_change_over_4_weeks < 0.5% body_weight) AND (adherence_confirmed):
    1. Verify tracking accuracy first
    2. If at minimum safe calories: implement 1-2 week diet break
    3. If room to reduce: decrease by 100-150 kcal/day
    4. Wait minimum 2 weeks before reassessing
```

**Weight Trend Analysis Rules:**
- IGNORE first 7-10 days of any new diet (water weight)
- Use 7-day rolling average for trend analysis
- True plateau = 4+ weeks of <0.3% weight change
- Menstrual cycle: compare same phase month-to-month

**When to Suggest Reverse Dieting:**
- Extended dieting >12 weeks at significant deficit
- Severe restriction history (<1200 kcal women, <1500 kcal men)
- Signs of metabolic suppression: persistent fatigue, cold intolerance, hair loss
- Post-competition phase for athletes

**Protocol:** Increase 50-100 kcal/week for 4-12 weeks

### Confidence Level
- **Metabolic adaptation exists:** HIGH — CALERIE studies
- **Adaptation magnitude:** HIGH — Consistent 80-120 kcal/day
- **Weight cycling "damages" metabolism:** LOW evidence for claim
- **Reverse dieting effectiveness:** LOW — Limited direct evidence

### Main Sources
1. CALERIE Studies (Redman et al., 2018)
2. Nunes CL et al., BJN (2022) — Adaptive thermogenesis systematic review
3. PMC Reverse Dieting RCT (2024)

---

## Domain 9: Myths vs Scientific Realities

### Synthesis of Current Knowledge

**Meal Frequency Myth:** The belief that eating every 2-3 hours "boosts metabolism" is definitively NOT supported. Multiple systematic reviews show meal frequency does not affect TDEE when caloric intake is controlled. A 2024 JAMA meta-analysis found **lower meal frequency associated with greater weight loss** (-1.85 kg). TEF is determined by total caloric intake and macronutrient composition, not meal frequency.

**Detox/Cleanse Products:** Johns Hopkins Medicine explicitly states there is no clinical evidence supporting detox cleanses. The liver and kidneys function continuously without special products. Potential harms include electrolyte imbalances, nutrient deficiencies, and liver injury.

**Fat-Burning Foods:** "Negative calorie foods" are a myth—even protein only requires 20-30% of calories for digestion. Thermogenic effects from caffeine, capsaicin, and green tea are modest: **caffeine increases RMR by 3-4%** (79-150 kcal/day), capsaicin adds ~50 kcal/day. These are clinically insignificant without accompanying caloric deficit.

**Carbs at Night:** Carbs eaten at night don't automatically turn to fat—total daily calories matter most. However, diet-induced thermogenesis is 44% lower for evening meals, and glucose tolerance naturally decreases at night.

**Supplement Hierarchy:**
- **Creatine:** Most evidence-backed ergogenic supplement; 3-5g/day is safe and effective
- **Protein powder:** Effective when dietary protein is insufficient
- **BCAAs:** Unnecessary when protein intake is adequate (≥1.2 g/kg/day)
- **Fat burners:** Meta-analysis shows 95% CI crossed zero—no statistically significant effect

### Exploitable Quantitative Data

**Thermic Effect of Food:**
- Protein: 20-30%
- Carbohydrates: 5-10%
- Fat: 0-3%
- Total TEF: ~10% of daily intake (regardless of meal frequency)

**Creatine Dosing (ISSN):**

| Protocol | Dose |
|----------|------|
| Loading | 0.3 g/kg/day for 5-7 days (~20-25g/day) |
| Maintenance | 3-5 g/day |
| Alternative (no loading) | 3-5 g/day from start (saturates in 3-4 weeks) |

**Caffeine Thermogenic Effect:**
- Single 100mg dose: 3-4% RMR increase
- Repeated dosing: 8-11% daily EE increase (79-150 kcal/day)

**BCAA Threshold:**
- Unnecessary when protein ≥1.2 g/kg/day from complete sources

### Practical Applications for AI Agent

**Myth-Busting Response Templates:**

*Meal frequency:* "Research shows total daily calorie intake determines metabolic rate—not meal frequency. Eating 3 or 6 meals with the same total calories burns the same amount."

*Detox cleanses:* "Your liver and kidneys continuously detoxify your body without special products. Johns Hopkins confirms no clinical evidence for detox efficacy."

*Fat-burning foods:* "There are no 'negative calorie' foods. Thermogenic effects from caffeine or spicy foods add only 50-150 calories/day—meaningful fat loss requires a caloric deficit."

**Supplement Recommendations:**
- RECOMMEND: Creatine (3-5g/day), protein powder if needed, caffeine for performance
- DISCOURAGE: Fat burners, BCAAs if protein adequate, detox products
- CONTEXT-DEPENDENT: Multivitamins (beneficial for elderly, pregnant women, restrictive diets)

### Confidence Level
- **Meal frequency doesn't boost metabolism:** VERY HIGH (95%)
- **Detox cleanses lack evidence:** VERY HIGH (95%)
- **Creatine is effective and safe:** VERY HIGH (95%)
- **Fat burners mostly ineffective:** HIGH (85%)
- **BCAAs unnecessary with adequate protein:** HIGH (85%)

### Main Sources
1. ISSN Position Stand: Creatine (2017)
2. JAMA Network Open Meal Timing Meta-Analysis (2024)
3. Johns Hopkins Medicine: Liver Detox Facts
4. PubMed BCAA Systematic Reviews (2022)

---

## Domain 10: Food Quality & Microbiome

### Synthesis of Current Knowledge

**Ultra-Processed Foods:** The **Hall NIH Study (2019)** provided the first RCT evidence that UPF diets cause excess calorie intake. Participants consumed **508 ± 106 kcal/day more** on UPF vs unprocessed diets despite matching for calories, macronutrients, sugar, sodium, and fiber. A 2024 BMJ umbrella review (45 meta-analyses, ~10 million participants) found convincing evidence linking UPF to CVD mortality, type 2 diabetes, anxiety, and depression. Americans currently obtain ~55% of calories from UPFs.

**Cooking Impact:** Vitamin C is most heat-sensitive (boiling: 40-70% loss; steaming: 8-15% loss). However, cooking **enhances** lycopene bioavailability by **54-171%** after heating, with absorption boosted 82% when cooked with olive oil. Ranking by nutrient preservation: steaming > microwaving > stir-frying > roasting > boiling > deep frying.

**Fermented Foods:** A Stanford clinical trial (2021) demonstrated a 10-week high-fermented food diet significantly **increased gut microbiome diversity and decreased 19 inflammatory proteins**. Effective probiotic doses range from **10⁸ to 10¹⁰ CFU/day**.

**Plant Diversity:** The American Gut Project (10,000+ participants) found consuming **30+ different plant types per week** correlated with significantly more diverse gut microbiomes. This includes all vegetables, fruits, grains, legumes, nuts, seeds, herbs, and spices.

### Exploitable Quantitative Data

**NOVA Classification:**

| Group | Description | Examples |
|-------|-------------|----------|
| 1 | Unprocessed/minimally processed | Fresh produce, meat, eggs, plain grains |
| 2 | Processed culinary ingredients | Oils, butter, salt, sugar, flour |
| 3 | Processed foods | Canned vegetables, cheese, cured meats |
| 4 | Ultra-processed | Soft drinks, chips, packaged snacks, commercial bread |

**UPF Target:** Aim for <30-40% calories from UPF

**Vitamin C Loss by Cooking Method:**

| Method | Loss |
|--------|------|
| Steaming (5 min) | 8-15% |
| Microwaving | 20-30% |
| Boiling (5 min) | 40-55% |
| Extended boiling | 50-70% |

**Probiotic CFU Recommendations:**

| Purpose | CFU/day |
|---------|---------|
| General maintenance | 1-10 billion |
| Digestive support | 10-20 billion |
| Therapeutic/recovery | 20-50 billion |

**Plant Diversity:**
- Optimal: 30+ different plants per week
- Minimum beneficial: 10+ plants/week
- Count all: vegetables, fruits, grains, legumes, nuts, seeds, herbs, spices

**Fresh vs Frozen:**
- Frozen vegetables picked at peak: equivalent or higher nutrients than fresh stored 5+ days
- Fresh produce after 5 days refrigeration: often lower vitamin C than frozen

### Practical Applications for AI Agent

**Food Quality Scoring:**
- Prioritize NOVA Group 1-2 foods
- Include fermented foods daily (yogurt, kefir, sauerkraut, kimchi)
- Target 30+ plant types weekly
- Use steaming/microwaving over boiling for vegetables

**Cooking Method Recommendations:**
- Cruciferous vegetables: Steam 3-5 min (preserves sulforaphane)
- Tomatoes: Sauté with olive oil (increases lycopene 2-5×)
- Leafy greens: Light steam or quick sauté
- Carrots: Roast or steam (increases beta-carotene availability)

**Weekly Plant Diversity Tracking:**
- Count each unique plant type once per week
- Different colors of same vegetable count separately
- Fresh, frozen, dried, canned all count
- Herbs and spices count toward total

### Confidence Level
- **UPF health associations:** HIGH — Multiple meta-analyses
- **Hall NIH Study findings:** VERY HIGH — Rigorous RCT methodology
- **Vitamin C cooking losses:** HIGH — Multiple controlled studies
- **30 plants/week recommendation:** MODERATE-HIGH — Large observational study

### Main Sources
1. Hall KD et al., Cell Metabolism (2019) — NIH UPF study
2. McDonald D et al., mSystems (2018) — American Gut Project
3. Sonnenburg JL et al., Cell (2021) — Stanford fermented food study
4. BMJ Umbrella Review (2024) — UPF and health outcomes

---

## Quick Reference: Key Decision Rules for AI Agent

### Calorie Calculation
```
1. Calculate BMR using Mifflin-St Jeor
2. Multiply by activity factor (1.2-1.9)
3. Apply goal modifier:
   - Weight loss: -250 to -500 kcal (15-25%)
   - Muscle gain: +200 to +350 kcal (5-10%)
   - Maintenance: ±0
```

### Protein Targets (g/kg body weight/day)
- Sedentary: 0.8
- Active: 1.4-2.0
- Weight loss: 2.3-3.1 (of lean mass)
- Muscle gain: 1.6-2.2
- Per meal: 20-40g

### Meal Composition Priorities
1. Protein: 25-30g per meal
2. Fiber: 8-12g per meal
3. Vegetables: 50% of plate volume
4. Energy density: Prioritize <1.5 kcal/g foods
5. Minimize ultra-processed foods (<30-40% of calories)

### Adjustment Triggers
- Plateau (4+ weeks): Reduce 100-150 kcal or implement diet break
- Too rapid loss (>1.5%/week): Increase 100-200 kcal
- Slow progress: Verify tracking before adjusting

### Red Flags for Professional Referral
- BMI <18.5 seeking weight loss
- History of eating disorders
- Type 1 diabetes
- Pregnancy/breastfeeding
- Unintended weight changes >5% in 1 month
- Persistent fatigue, hair loss, or cold intolerance

---

*Document compiled from peer-reviewed sources including ISSN Position Stands, AND Position Papers, EFSA DRVs, Cochrane Reviews, and major RCTs (PREDIMED, CALERIE, Hall NIH Study). All recommendations target healthy adults aged 18-65. Individual medical conditions require professional consultation.*