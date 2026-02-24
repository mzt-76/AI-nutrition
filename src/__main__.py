"""Entry point for running the app as a module.

Usage:
    python -m src        # CLI chat interface
    python -m src api    # FastAPI server on port 8001
"""

import sys

if len(sys.argv) > 1 and sys.argv[1] == "api":
    import uvicorn

    # Remove 'api' from argv so uvicorn doesn't see it
    sys.argv.pop(1)
    uvicorn.run("src.api:app", host="0.0.0.0", port=8001, reload=True)  # noqa: S104
else:
    import asyncio

    from src.cli import main

    asyncio.run(main())
