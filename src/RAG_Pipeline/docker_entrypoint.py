#!/usr/bin/env python3
"""
Docker entrypoint for RAG Pipeline that supports both continuous and single-run modes.
"""
import os
import sys
import argparse
import json
import time
from typing import Dict, Any

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_single_check(pipeline_type: str, **kwargs) -> Dict[str, Any]:
    """
    Run a single check cycle for the specified pipeline.

    Args:
        pipeline_type: 'local' or 'google_drive'
        **kwargs: Additional arguments for watcher initialization

    Returns:
        Dict containing run statistics
    """
    start_time = time.time()

    try:
        if pipeline_type == "local":
            # Change to Local_Files directory for proper imports
            local_files_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "Local_Files"
            )
            os.chdir(local_files_dir)
            sys.path.insert(0, local_files_dir)

            from file_watcher import LocalFileWatcher

            watcher = LocalFileWatcher(
                watch_directory=kwargs.get("directory"),
                config_path=kwargs.get("config", "config.json"),
            )

            # Perform single check
            stats = watcher.check_for_changes()

        elif pipeline_type == "google_drive":
            # Change to Google_Drive directory for proper imports
            google_drive_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "Google_Drive"
            )
            os.chdir(google_drive_dir)
            sys.path.insert(0, google_drive_dir)

            from drive_watcher import GoogleDriveWatcher

            watcher = GoogleDriveWatcher(
                config_path=kwargs.get("config", "config.json")
            )

            # Perform single check
            stats = watcher.check_for_changes()

        else:
            raise ValueError(f"Unknown pipeline type: {pipeline_type}")

        # Add pipeline metadata to stats
        stats["pipeline_type"] = pipeline_type
        stats["run_mode"] = "single"
        stats["total_duration"] = time.time() - start_time

        return stats

    except Exception as e:
        return {
            "pipeline_type": pipeline_type,
            "run_mode": "single",
            "files_processed": 0,
            "files_deleted": 0,
            "errors": 1,
            "duration": 0.0,
            "total_duration": time.time() - start_time,
            "error_message": str(e),
        }


def main():
    parser = argparse.ArgumentParser(description="RAG Pipeline Docker Entrypoint")
    parser.add_argument(
        "--pipeline",
        type=str,
        choices=["local", "google_drive"],
        default=os.getenv("RAG_PIPELINE_TYPE", "local"),
        help="Which pipeline to run (can be overridden with RAG_PIPELINE_TYPE env var)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["continuous", "single"],
        default=os.getenv("RUN_MODE", "continuous"),
        help="Run mode: continuous or single check (can be overridden with RUN_MODE env var)",
    )
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument(
        "--directory",
        type=str,
        default=os.getenv("RAG_WATCH_DIRECTORY"),
        help="Directory to watch (for local pipeline, can be overridden with RAG_WATCH_DIRECTORY env var)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Interval in seconds between checks (continuous mode only)",
    )

    args = parser.parse_args()

    # Set default config paths if not provided
    if not args.config:
        if args.pipeline == "local":
            args.config = "config.json"
        elif args.pipeline == "google_drive":
            args.config = "config.json"

    # Import the appropriate pipeline
    if args.pipeline == "local":
        local_files_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "Local_Files"
        )
        os.chdir(local_files_dir)
        sys.path.insert(0, local_files_dir)

        import main as local_main_module

        if args.mode == "single":
            print(f"Running {args.pipeline} pipeline in single-run mode...")

            stats = run_single_check(
                "local", directory=args.directory, config=args.config
            )

            print("\nRun Statistics:")
            print(json.dumps(stats, indent=2))

            # Exit with appropriate code
            if stats["errors"] > 0:
                if "error_message" in stats and (
                    "auth" in stats["error_message"].lower()
                    or "credential" in stats["error_message"].lower()
                ):
                    print("\nExiting with code 3: Authentication error")
                    sys.exit(3)
                elif "config" in stats.get("error_message", "").lower():
                    print("\nExiting with code 2: Configuration error")
                    sys.exit(2)
                else:
                    print("\nExiting with code 1: Runtime error (retry recommended)")
                    sys.exit(1)
            else:
                print("\nExiting with code 0: Success")
                sys.exit(0)
        else:
            # Continuous mode - use the existing main function
            sys.argv = ["main.py"]
            sys.argv.extend(["--config", args.config])
            if args.directory:
                sys.argv.extend(["--directory", args.directory])
            sys.argv.extend(["--interval", str(args.interval)])
            local_main_module.main()

    elif args.pipeline == "google_drive":
        google_drive_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "Google_Drive"
        )
        os.chdir(google_drive_dir)
        sys.path.insert(0, google_drive_dir)

        import main as drive_main_module

        if args.mode == "single":
            print(f"Running {args.pipeline} pipeline in single-run mode...")

            stats = run_single_check("google_drive", config=args.config)

            print("\nRun Statistics:")
            print(json.dumps(stats, indent=2))

            if stats["errors"] > 0:
                if "error_message" in stats and (
                    "auth" in stats["error_message"].lower()
                    or "credential" in stats["error_message"].lower()
                ):
                    print("\nExiting with code 3: Authentication error")
                    sys.exit(3)
                elif "config" in stats.get("error_message", "").lower():
                    print("\nExiting with code 2: Configuration error")
                    sys.exit(2)
                else:
                    print("\nExiting with code 1: Runtime error (retry recommended)")
                    sys.exit(1)
            else:
                print("\nExiting with code 0: Success")
                sys.exit(0)
        else:
            sys.argv = ["main.py"]
            if args.config:
                sys.argv.extend(["--config", args.config])
            sys.argv.extend(["--interval", str(args.interval)])
            drive_main_module.main()


if __name__ == "__main__":
    main()
