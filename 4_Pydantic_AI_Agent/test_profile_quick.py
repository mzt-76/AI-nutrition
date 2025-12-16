"""Quick test of profile tool without full agent."""
import asyncio
import json
from clients import get_supabase_client
from tools import fetch_my_profile_tool

async def main():
    print("Testing fetch_my_profile_tool with incomplete profile...")
    print("=" * 60)
    
    supabase = get_supabase_client()
    result = await fetch_my_profile_tool(supabase)
    
    data = json.loads(result)
    
    if data.get("code") == "PROFILE_INCOMPLETE":
        print("✅ Tool correctly detected incomplete profile")
        print(f"\nMessage: {data['message']}")
        print(f"Profile name: {data.get('name')}")
        print(f"Existing data: {data.get('existing_data')}")
    elif "error" in data:
        print(f"❌ Unexpected error: {data}")
    else:
        print("✅ Profile loaded successfully:")
        print(json.dumps(data, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
