"""
Format meal plans as downloadable Markdown documents.

Generates user-friendly Markdown files with day-by-day breakdowns, ingredient lists,
cooking instructions, and weekly summary tables. Designed for easy reading and
conversion to PDF with pandoc.
"""

from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def format_meal_plan_as_markdown(meal_plan: dict, meal_plan_id: int) -> str:
    """
    Generate a downloadable Markdown document from meal plan.

    Structure:
    - Header: ID, dates, structure, macro targets
    - Daily sections: Each day with all meals, ingredients, instructions, macros
    - Summary table: Weekly macro totals and daily averages

    Args:
        meal_plan: Meal plan dictionary from database/LLM with structure:
            {
                "days": [
                    {
                        "day": "Lundi",
                        "date": "2024-12-23",
                        "meals": [
                            {
                                "meal_type": "Petit-déjeuner",
                                "time": "07:30",
                                "recipe_name": "Omelette protéinée",
                                "ingredients": [{"name": "Eggs", "quantity": 3, "unit": "units"}],
                                "instructions": ["Step 1", "Step 2"],
                                "macros": {"calories": 400, "protein_g": 30, ...}
                            }
                        ],
                        "daily_totals": {"calories": 3000, "protein_g": 180, ...}
                    }
                ],
                "start_date": "2024-12-23",
                "end_date": "2024-12-29",
                "meal_structure": "3_meals_2_snacks",
                "weekly_totals": {"calories": 21000, "protein_g": 1260, ...}
            }
        meal_plan_id: Database ID for reference

    Returns:
        Complete Markdown document as string

    Example:
        >>> plan = {
        ...     "days": [{"day": "Lundi", "meals": [], "daily_totals": {}}],
        ...     "start_date": "2024-12-23"
        ... }
        >>> md = format_meal_plan_as_markdown(plan, 123)
        >>> "# Plan de Repas" in md
        True
        >>> "ID: 123" in md
        True
    """
    # Extract metadata
    start_date = meal_plan.get("start_date", "N/A")
    end_date = meal_plan.get("end_date", "N/A")
    meal_structure = meal_plan.get("meal_structure", "N/A")
    days = meal_plan.get("days", [])
    weekly_totals = meal_plan.get("weekly_totals", {})

    # Build markdown document
    lines = []

    # Header section
    lines.append("# Plan de Repas Hebdomadaire")
    lines.append("")
    lines.append(f"**ID:** {meal_plan_id}")
    lines.append(f"**Période:** {start_date} → {end_date}")
    lines.append(f"**Structure:** {meal_structure}")
    lines.append(f"**Généré le:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Daily sections
    for day_data in days:
        day_name = day_data.get("day", "Jour inconnu")
        day_date = day_data.get("date", "")
        meals = day_data.get("meals", [])
        daily_totals = day_data.get("daily_totals", {})

        lines.append(f"## {day_name} ({day_date})")
        lines.append("")

        # Each meal
        for meal in meals:
            meal_type = meal.get("meal_type", "Repas")
            meal_time = meal.get("time", "")
            recipe_name = meal.get("recipe_name", "Sans nom")
            ingredients = meal.get("ingredients", [])
            instructions = meal.get("instructions", [])
            macros = meal.get("macros", {})

            lines.append(f"### {meal_type} ({meal_time}) - {recipe_name}")
            lines.append("")

            # Ingredients list
            if ingredients:
                lines.append("**Ingrédients:**")
                for ing in ingredients:
                    name = ing.get("name", "Ingrédient")
                    quantity = ing.get("quantity", 0)
                    unit = ing.get("unit", "")
                    # Escape pipes for markdown table compatibility
                    name_escaped = name.replace("|", "\\|")
                    lines.append(f"- {name_escaped}: {quantity} {unit}")
                lines.append("")

            # Instructions
            if instructions:
                lines.append("**Instructions:**")
                for i, instruction in enumerate(instructions, 1):
                    lines.append(f"{i}. {instruction}")
                lines.append("")

            # Meal macros
            if macros:
                calories = macros.get("calories", 0)
                protein = macros.get("protein_g", 0)
                carbs = macros.get("carbs_g", 0)
                fat = macros.get("fat_g", 0)
                lines.append(
                    f"**Macros:** {calories} kcal | "
                    f"Protéines: {protein}g | "
                    f"Glucides: {carbs}g | "
                    f"Lipides: {fat}g"
                )
                lines.append("")

        # Daily totals
        if daily_totals:
            daily_cals = daily_totals.get("calories", 0)
            daily_prot = daily_totals.get("protein_g", 0)
            daily_carbs = daily_totals.get("carbs_g", 0)
            daily_fat = daily_totals.get("fat_g", 0)
            lines.append(
                f"**Total du jour:** {daily_cals} kcal | "
                f"Protéines: {daily_prot}g | "
                f"Glucides: {daily_carbs}g | "
                f"Lipides: {daily_fat}g"
            )
            lines.append("")

        lines.append("---")
        lines.append("")

    # Weekly summary table
    lines.append("## Récapitulatif Hebdomadaire")
    lines.append("")

    if days:
        # Calculate averages
        num_days = len(days)
        avg_calories = (
            sum(d.get("daily_totals", {}).get("calories", 0) for d in days) // num_days
            if num_days > 0
            else 0
        )
        avg_protein = (
            sum(d.get("daily_totals", {}).get("protein_g", 0) for d in days) // num_days
            if num_days > 0
            else 0
        )
        avg_carbs = (
            sum(d.get("daily_totals", {}).get("carbs_g", 0) for d in days) // num_days
            if num_days > 0
            else 0
        )
        avg_fat = (
            sum(d.get("daily_totals", {}).get("fat_g", 0) for d in days) // num_days
            if num_days > 0
            else 0
        )

        # Table header
        lines.append("| Jour | Calories | Protéines (g) | Glucides (g) | Lipides (g) |")
        lines.append("|------|----------|---------------|--------------|-------------|")

        # Daily rows
        for day_data in days:
            day_name = day_data.get("day", "N/A")
            totals = day_data.get("daily_totals", {})
            cals = totals.get("calories", 0)
            prot = totals.get("protein_g", 0)
            carbs = totals.get("carbs_g", 0)
            fat = totals.get("fat_g", 0)
            lines.append(f"| {day_name} | {cals} | {prot} | {carbs} | {fat} |")

        # Average row
        lines.append(
            f"| **Moyenne** | **{avg_calories}** | **{avg_protein}** | **{avg_carbs}** | **{avg_fat}** |"
        )

        lines.append("")

    # Weekly totals
    if weekly_totals:
        weekly_cals = weekly_totals.get("calories", 0)
        weekly_prot = weekly_totals.get("protein_g", 0)
        weekly_carbs = weekly_totals.get("carbs_g", 0)
        weekly_fat = weekly_totals.get("fat_g", 0)
        lines.append(
            f"**Total hebdomadaire:** {weekly_cals} kcal | "
            f"Protéines: {weekly_prot}g | "
            f"Glucides: {weekly_carbs}g | "
            f"Lipides: {weekly_fat}g"
        )
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*Généré par AI-Nutrition Assistant*")
    lines.append("")
    lines.append("**Notes:**")
    lines.append("- Ajustez les quantités selon votre faim et vos besoins")
    lines.append("- Hydratation: boire 2-3L d'eau par jour")
    lines.append("- Les macros sont calculées avec OpenFoodFacts (précision ±5%)")
    lines.append("")

    markdown_content = "\n".join(lines)

    logger.info(
        f"Generated Markdown document: {len(lines)} lines, "
        f"{len(days)} days, meal_plan_id={meal_plan_id}"
    )

    return markdown_content


def generate_meal_plan_document(
    meal_plan: dict,
    output_dir: str,
    meal_plan_id: int | None = None,
) -> str:
    """
    Generate and save a Markdown document for the meal plan.

    Creates a file in the specified directory with a timestamped filename.

    Args:
        meal_plan: Meal plan dictionary from database/LLM
        output_dir: Directory to save the markdown file
        meal_plan_id: Optional database ID (defaults to extracting from meal_plan)

    Returns:
        Full path to the generated markdown file

    Example:
        >>> path = generate_meal_plan_document(plan, "/tmp/plans")
        >>> path.endswith(".md")
        True
    """
    from pathlib import Path

    # Get meal_plan_id
    if meal_plan_id is None:
        meal_plan_id = meal_plan.get("meal_plan_id", 0)
        if isinstance(meal_plan_id, str):
            # Extract numeric ID if string like "plan_123"
            try:
                meal_plan_id = int("".join(filter(str.isdigit, meal_plan_id)) or "0")
            except ValueError:
                meal_plan_id = 0

    # Generate markdown content
    markdown_content = format_meal_plan_as_markdown(meal_plan, meal_plan_id)

    # Create output directory if needed
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    start_date = meal_plan.get("start_date", "unknown")
    filename = f"meal_plan_{start_date}_{timestamp}.md"

    # Write file
    file_path = output_path / filename
    file_path.write_text(markdown_content, encoding="utf-8")

    logger.info(f"Saved meal plan document to: {file_path}")

    return str(file_path)
