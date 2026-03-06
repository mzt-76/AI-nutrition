"""
Quick verification script to check if everything is set up correctly.

Run this before starting the agent to verify:
- Dependencies are installed
- Environment variables are configured
- Core modules import correctly
- Database connections work
"""

import sys
import os
from pathlib import Path

# Setup path - add project root (parent of src/) to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

print("🔍 AI Nutrition Assistant - Setup Verification\n")
print("=" * 60)

# 1. Check Python version
print("\n1. Python Version:")
import platform

python_version = platform.python_version()
print(f"   ✅ Python {python_version}")
if python_version < "3.11":
    print(f"   ⚠️  Warning: Python 3.11+ recommended, you have {python_version}")

# 2. Check dependencies
print("\n2. Core Dependencies:")
try:
    import pydantic_ai  # noqa: F401

    print("   ✅ pydantic-ai installed")
except ImportError as e:
    print(f"   ❌ pydantic-ai missing: {e}")

try:
    import supabase

    print("   ✅ supabase installed")
except ImportError as e:
    print(f"   ❌ supabase missing: {e}")

try:
    import openai  # noqa: F401

    print("   ✅ openai installed")
except ImportError as e:
    print(f"   ❌ openai missing: {e}")

try:
    import streamlit  # noqa: F401

    print("   ✅ streamlit installed")
except ImportError as e:
    print(f"   ❌ streamlit missing: {e}")

try:
    import mem0  # noqa: F401

    print("   ✅ mem0 installed")
except ImportError as e:
    print(f"   ❌ mem0 missing: {e}")

# 3. Check environment variables
print("\n3. Environment Variables:")
from dotenv import load_dotenv

load_dotenv()

required_vars = {
    "LLM_API_KEY": "OpenAI/LLM API Key",
    "EMBEDDING_API_KEY": "Embedding API Key",
    "SUPABASE_URL": "Supabase URL",
    "SUPABASE_SERVICE_KEY": "Supabase Service Key",
}

all_vars_present = True
for var, description in required_vars.items():
    value = os.getenv(var)
    if value:
        masked = value[:10] + "..." if len(value) > 10 else value
        print(f"   ✅ {var}: {masked}")
    else:
        print(f"   ❌ {var}: Not set")
        all_vars_present = False

optional_vars = {
    "BRAVE_API_KEY": "Brave Search API Key (optional)",
    "SEARXNG_BASE_URL": "SearXNG URL (optional)",
}

for var, description in optional_vars.items():
    value = os.getenv(var)
    if value:
        masked = value[:10] + "..." if len(value) > 10 else value
        print(f"   ℹ️  {var}: {masked}")
    else:
        print(f"   ⚪ {var}: Not set ({description})")

# 4. Test core modules
print("\n4. Core Modules:")
try:
    from src.nutrition.calculations import mifflin_st_jeor_bmr, calculate_tdee

    bmr = mifflin_st_jeor_bmr(35, "male", 87, 178)
    tdee = calculate_tdee(bmr, "moderate")
    print(f"   ✅ nutrition.calculations works (BMR: {bmr}, TDEE: {tdee})")
except Exception as e:
    print(f"   ❌ nutrition.calculations error: {e}")

try:
    from src.clients import get_supabase_client

    print("   ✅ clients module imports correctly")
except Exception as e:
    print(f"   ❌ clients module error: {e}")

try:
    from src.prompt import AGENT_SYSTEM_PROMPT

    print(f"   ✅ prompt module loaded ({len(AGENT_SYSTEM_PROMPT)} chars)")
except Exception as e:
    print(f"   ❌ prompt module error: {e}")

# 5. Test Supabase connection (if credentials present)
print("\n5. Database Connection:")
if all_vars_present:
    try:
        from src.clients import get_supabase_client

        supabase = get_supabase_client()
        # Try a simple query
        result = supabase.table("my_profile").select("*").limit(1).execute()
        if result.data:
            print("   ✅ Supabase connected (profile found)")
        else:
            print("   ⚠️  Supabase connected but no profile found")
            print("      → You'll need to create a profile in Supabase")
    except Exception as e:
        print(f"   ⚠️  Supabase connection issue: {e}")
        print("      → Check your SUPABASE_URL and SUPABASE_SERVICE_KEY")
else:
    print("   ⏭️  Skipped (missing environment variables)")

# 6. Summary
print("\n" + "=" * 60)
print("\n📊 Summary:")

if all_vars_present:
    print("   ✅ All required environment variables are set")
else:
    print("   ❌ Some environment variables are missing - check .env file")

print("\n🚀 Next Steps:")
print("   1. If all checks passed, run: streamlit run src/streamlit_ui.py")
print("   2. If any errors, fix them and run this script again")
print("   3. Read QUICKSTART.md for detailed instructions")
print("\n" + "=" * 60)
