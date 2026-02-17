import argparse
import sys
from pathlib import Path

from file_watcher import LocalFileWatcher


def main():
    """
    Main entry point for the Local Files RAG Pipeline.
    """
    # Get the directory where the script is located
    script_dir = Path(__file__).resolve().parent

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Local Files RAG Pipeline")
    parser.add_argument(
        "--config",
        type=str,
        default=str(script_dir / "config.json"),
        help="Path to configuration JSON file",
    )
    parser.add_argument(
        "--directory",
        type=str,
        default=None,
        help="Directory to watch for files (relative to script location)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Interval in seconds between checks for changes",
    )

    args = parser.parse_args()

    try:
        # Start the Local File watcher
        watcher = LocalFileWatcher(
            watch_directory=args.directory, config_path=args.config
        )

        # Watch for changes
        watcher.watch_for_changes(interval_seconds=args.interval)

    except KeyboardInterrupt:
        print("Local Files RAG Pipeline stopped by user.")
    except Exception as e:
        print(f"Error running Local Files RAG Pipeline: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
