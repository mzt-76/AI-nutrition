#!/usr/bin/env python
"""Test meal plan generation through the agent."""

import asyncio
from agent import agent, create_agent_deps


async def test_meal_plan_via_agent():
    """Test meal plan generation by calling the agent directly."""
    print("🧪 Testing Meal Plan Generation via Agent")
    print("=" * 70)

    # Create agent deps
    deps = create_agent_deps()

    # Test prompt
    prompt = """Génère-moi un plan alimentaire hebdomadaire pour la prise de muscle.

Utilise mon profil avec:
- Calories: 2474 kcal/jour
- Protéines: 156g
- Glucides: 231g
- Lipides: 51g
- ALLERGIES: arachides, fruits à coque (ÉVITE ABSOLUMENT le lait d'amande!)
- Aliments détestés: brocoli
"""

    print("\n📝 Prompt:")
    print(prompt)
    print("\n⏳ Running agent...\n")

    try:
        result = await agent.run(prompt, deps=deps)

        output = result.data

        print("\n" + "=" * 70)
        print("✅ AGENT RESPONSE:")
        print("=" * 70)
        print(output[:1000])  # Print first 1000 chars

        # Check for success indicators
        if "jour 1" in output.lower() or "lundi" in output.lower() or "monday" in output.lower():
            print("\n✅ Meal plan seems to have been generated")

            # Check for allergens
            if "amande" in output.lower():
                print("⚠️ WARNING: 'amande' found in response - possible allergen violation!")
                return False
            else:
                print("✅ No 'amande' found in response")

            if "arachide" in output.lower() or "cacahuète" in output.lower():
                print("⚠️ WARNING: Peanuts found in response!")
                return False
            else:
                print("✅ No peanuts found in response")

            return True

        elif "erreur" in output.lower() or "error" in output.lower():
            print("❌ Error in response")
            return False

        elif "problème" in output.lower():
            print("❌ Problem reported in response")
            return False

        else:
            print("⚠️ Unclear if meal plan was generated - response may be conversational")
            return False

    except Exception as e:
        print(f"\n❌ EXCEPTION: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_meal_plan_via_agent())
    print("\n" + "=" * 70)
    if success:
        print("✅ TEST PASSED")
    else:
        print("❌ TEST FAILED")
    print("=" * 70)
