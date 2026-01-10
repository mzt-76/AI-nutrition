#!/usr/bin/env python3
"""Test full meal plan generation with OpenFoodFacts integration."""

import asyncio
import json
from datetime import datetime, timedelta

from agent import agent, create_agent_deps
from clients import get_supabase_client


async def test_full_meal_plan():
    """Generate and validate a full 7-day meal plan."""
    print("🧪 FULL MEAL PLAN GENERATION TEST")
    print("=" * 60)

    # Calculate next Monday
    today = datetime.now()
    days_until_monday = (7 - today.weekday()) % 7
    next_monday = today + timedelta(days=days_until_monday if days_until_monday > 0 else 7)
    start_date = next_monday.strftime("%Y-%m-%d")

    print(f"\n📅 Generating plan for week starting: {start_date}")
    print(f"⏱️  Starting at: {datetime.now().strftime('%H:%M:%S')}")

    # Create agent dependencies
    deps = create_agent_deps()

    # Generate meal plan
    print("\n🤖 Calling agent to generate meal plan...")
    print("   (This may take 2-4 minutes with OpenFoodFacts database lookups)")

    try:
        result = await agent.run(
            f"Génère-moi un plan de repas pour la semaine du {start_date}",
            deps=deps
        )

        print(f"\n⏱️  Completed at: {datetime.now().strftime('%H:%M:%S')}")
        print("\n" + "=" * 60)
        print("✅ MEAL PLAN GENERATED SUCCESSFULLY")
        print("=" * 60)

        # Get the most recent meal plan from database
        supabase = get_supabase_client()
        meal_plan_result = supabase.table('meal_plans').select('*').order('created_at', desc=True).limit(1).execute()

        if not meal_plan_result.data:
            print("❌ No meal plan found in database")
            return False

        plan = meal_plan_result.data[0]
        plan_data = plan['plan_data']

        print(f"\n📊 MEAL PLAN VALIDATION")
        print("=" * 60)
        print(f"Week Start: {plan['week_start']}")
        print(f"Target Calories: {plan['target_calories_daily']} kcal/day")
        print(f"Target Protein: {plan['target_protein_g']}g/day")

        # Analyze each day
        print(f"\n📅 DAILY BREAKDOWN:")
        print("-" * 60)

        days_within_tolerance = 0
        total_complements = 0
        has_openfoodfacts_data = False

        for day in plan_data.get('days', []):
            day_name = day.get('day', 'Unknown')
            daily_totals = day.get('daily_totals', {})

            actual_cal = daily_totals.get('calories', 0)
            actual_prot = daily_totals.get('protein_g', 0)
            target_cal = plan['target_calories_daily']
            target_prot = plan['target_protein_g']

            # Calculate tolerance
            cal_diff = actual_cal - target_cal
            cal_tolerance = abs(cal_diff) / target_cal * 100 if target_cal else 0
            prot_diff = actual_prot - target_prot
            prot_tolerance = abs(prot_diff) / target_prot * 100 if target_prot else 0

            # Check if within tolerance (±5% calories, ±15% protein)
            # Different tolerances reflect nutritional priorities
            within_tolerance = cal_tolerance <= 5 and prot_tolerance <= 15
            if within_tolerance:
                days_within_tolerance += 1

            # Count complements
            complements = sum(1 for meal in day.get('meals', []) if 'complement' in meal.get('tags', []))
            total_complements += complements

            # Check for OpenFoodFacts data
            for meal in day.get('meals', []):
                for ing in meal.get('ingredients', []):
                    if 'openfoodfacts_code' in ing or 'openfoodfacts_name' in ing:
                        has_openfoodfacts_data = True

            # Print day summary
            status = "✅" if within_tolerance else "⚠️"
            print(f"{status} {day_name[:6]:7} | {actual_cal:4.0f} kcal ({cal_diff:+4.0f}, {cal_tolerance:4.1f}%) | "
                  f"{actual_prot:4.1f}g prot ({prot_diff:+4.1f}g, {prot_tolerance:4.1f}%) | "
                  f"{complements} compl")

        print("-" * 60)

        # Summary statistics
        accuracy_rate = days_within_tolerance / 7 * 100 if plan_data.get('days') else 0
        avg_complements = total_complements / 7 if plan_data.get('days') else 0

        print(f"\n📈 SUMMARY STATISTICS")
        print("=" * 60)
        print(f"Days within ±5% tolerance: {days_within_tolerance}/7 ({accuracy_rate:.0f}%)")
        print(f"Average complements/day: {avg_complements:.1f}")
        print(f"OpenFoodFacts data present: {'✅ YES' if has_openfoodfacts_data else '❌ NO'}")

        # Success criteria
        print(f"\n🎯 SUCCESS CRITERIA")
        print("=" * 60)

        success_checks = [
            (days_within_tolerance >= 7, f"All 7 days within tolerance: {days_within_tolerance}/7", "7/7 days (±5% cal, ±15% prot)"),
            (avg_complements <= 1, f"≤1 complement/day: {avg_complements:.1f}", "0-1 complement/day"),
            (has_openfoodfacts_data, f"OpenFoodFacts integration: {'✅' if has_openfoodfacts_data else '❌'}", "OpenFoodFacts data present"),
        ]

        all_passed = True
        for passed, message, criteria in success_checks:
            status = "✅" if passed else "❌"
            print(f"{status} {criteria:25} | {message}")
            if not passed:
                all_passed = False

        print("=" * 60)

        if all_passed:
            print("\n🎉 SUCCESS: All criteria met!")
            print("✅ OpenFoodFacts integration working perfectly")
            print("✅ Macro accuracy at 100%")
            print("✅ Minimal complements used")
            return True
        else:
            print("\n⚠️  PARTIAL SUCCESS: Some criteria not met")
            print("ℹ️  Check individual day breakdowns above")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_full_meal_plan())
    exit(0 if success else 1)
