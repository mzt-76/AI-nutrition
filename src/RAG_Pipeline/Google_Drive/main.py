import argparse
from pathlib import Path

from drive_watcher import GoogleDriveWatcher


def main():
    """
    Main entry point for the RAG pipeline.
    """
    # Get the directory where the script is located
    script_dir = Path(__file__).resolve().parent

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Google Drive RAG Pipeline")
    parser.add_argument(
        "--credentials",
        type=str,
        default=str(script_dir / "credentials.json"),
        help="Path to Google Drive API credentials file",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=str(script_dir / "token.json"),
        help="Path to Google Drive API token file",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=str(script_dir / "config.json"),
        help="Path to configuration JSON file",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Interval in seconds between checks for changes",
    )
    parser.add_argument(
        "--folder-id",
        type=str,
        default=None,
        help="ID of the specific Google Drive folder to watch (and its subfolders)",
    )

    args = parser.parse_args()

    # Start the Google Drive watcher
    watcher = GoogleDriveWatcher(
        credentials_path=args.credentials,
        token_path=args.token,
        folder_id=args.folder_id,
        config_path=args.config,
    )

    # Watch for changes
    watcher.watch_for_changes(interval_seconds=args.interval)


if __name__ == "__main__":
    main()
