from typing import Dict, Any, List, Optional
from datetime import datetime
import mimetypes
import time
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.text_processor import extract_text_from_file
from common.db_handler import process_file_for_rag, delete_document_by_file_id


class LocalFileWatcher:
    def __init__(self, watch_directory: str = None, config_path: str = None):
        """
        Initialize the Local File watcher.

        Args:
            watch_directory: Directory to watch for files (relative to this script)
            config_path: Path to the configuration file
        """
        # Load configuration
        self.config = {}
        if config_path:
            self.config_path = config_path
        else:
            # Default to config.json in the same directory as this script
            self.config_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "config.json"
            )
        self.load_config()

        # Set up the watch directory
        if watch_directory:
            self.watch_directory = watch_directory
        else:
            self.watch_directory = self.config.get("watch_directory", "data")

        # Make the watch directory absolute
        self.watch_directory = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), self.watch_directory
        )

        # Create the watch directory if it doesn't exist
        os.makedirs(self.watch_directory, exist_ok=True)

        self.known_files = {}  # Store file paths and their last modified time
        self.initialized = False  # Flag to track if we've done the initial scan

        # Initialize mimetypes
        mimetypes.init()

        print(
            f"Local File Watcher initialized. Watching directory: {self.watch_directory}"
        )

    def load_config(self) -> None:
        """
        Load configuration from JSON file.
        """
        try:
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
            print(f"Loaded configuration from {self.config_path}")

            # Load the last check time from config
            last_check_time_str = self.config.get(
                "last_check_time", "1970-01-01T00:00:00.000Z"
            )
            try:
                self.last_check_time = datetime.strptime(
                    last_check_time_str, "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                print(f"Resuming from last check time: {self.last_check_time}")
            except ValueError:
                # If the date format is invalid, use the default
                self.last_check_time = datetime.strptime(
                    "1970-01-01T00:00:00.000Z", "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                print("Invalid last check time format in config, using default")

        except Exception as e:
            print(f"Error loading configuration: {e}")
            self.config = {
                "supported_mime_types": [
                    "application/pdf",
                    "text/plain",
                    "text/csv",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ],
                "tabular_mime_types": [
                    "text/csv",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ],
                "text_processing": {
                    "default_chunk_size": 400,
                    "default_chunk_overlap": 0,
                },
                "last_check_time": "1970-01-01T00:00:00.000Z",
            }
            self.last_check_time = datetime.strptime(
                "1970-01-01T00:00:00.000Z", "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            print("Using default configuration")

    def save_last_check_time(self) -> None:
        """
        Save the last check time to the config file.
        """
        try:
            # Update the last_check_time in the config
            self.config["last_check_time"] = self.last_check_time.strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            )

            # Write the updated config back to the file
            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=2)

            print(f"Saved last check time: {self.last_check_time}")
        except Exception as e:
            print(f"Error saving last check time: {e}")

    def get_mime_type(self, file_path: str) -> str:
        """
        Get the MIME type of a file.

        Args:
            file_path: Path to the file

        Returns:
            str: MIME type of the file
        """
        # Custom mappings for common file extensions
        extension_mappings = {
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xls": "application/vnd.ms-excel",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".doc": "application/msword",
            ".csv": "text/csv",
            ".pdf": "application/pdf",
            ".txt": "text/plain",
        }

        # Get file extension
        _, ext = os.path.splitext(file_path.lower())

        # Check if extension is in our custom mappings
        if ext in extension_mappings:
            return extension_mappings[ext]

        # Fall back to mimetypes module
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            # Default to plain text if can't determine
            mime_type = "text/plain"

        return mime_type

    def get_file_content(self, file_path: str) -> Optional[bytes]:
        """
        Read the content of a file.

        Args:
            file_path: Path to the file

        Returns:
            bytes: Content of the file, or None if reading fails
        """
        try:
            with open(file_path, "rb") as f:
                return f.read()
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return None

    def get_changes(self) -> List[Dict[str, Any]]:
        """
        Get files that have been created or modified since the last check.

        Returns:
            List[Dict[str, Any]]: List of file information dictionaries
        """
        changed_files = []

        # Walk through the watch directory
        for root, _, files in os.walk(self.watch_directory):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                file_stat = os.stat(file_path)

                # Convert to datetime for comparison
                mod_time = datetime.fromtimestamp(file_stat.st_mtime)
                create_time = datetime.fromtimestamp(file_stat.st_ctime)

                # Check if the file is new or modified
                if (
                    file_path not in self.known_files
                    or mod_time > self.last_check_time
                    or create_time > self.last_check_time
                ):
                    # Get relative path for display
                    rel_path = os.path.relpath(file_path, self.watch_directory)

                    # Get MIME type
                    mime_type = self.get_mime_type(file_path)

                    # Create a file info dictionary similar to Google Drive
                    file_info = {
                        "id": file_path,  # Use file path as ID
                        "name": file_name,
                        "mimeType": mime_type,
                        "webViewLink": f"file://{file_path}",  # Local file URL
                        "modifiedTime": mod_time.isoformat(),
                        "createdTime": create_time.isoformat(),
                        "trashed": False,
                    }

                    changed_files.append(file_info)

        # Update the last check time
        self.last_check_time = datetime.now()

        # Save the updated last check time to config
        self.save_last_check_time()

        return changed_files

    def check_for_deleted_files(self) -> List[str]:
        """
        Check for files that have been deleted since the last check.

        Returns:
            List[str]: List of deleted file IDs (paths)
        """
        deleted_files = []

        # Check each known file to see if it still exists
        for file_path in list(self.known_files.keys()):
            if not os.path.exists(file_path):
                deleted_files.append(file_path)

        return deleted_files

    def process_file(self, file: Dict[str, Any]) -> None:
        """
        Process a single file for the RAG pipeline.

        Args:
            file: File information dictionary
        """
        file_path = file["id"]
        file_name, extension = os.path.splitext(file["name"])
        mime_type = file["mimeType"]
        web_view_link = file["webViewLink"]

        print(f"Processing file: {file_name}.{extension} (Path: {file_path})")

        # Skip unsupported file types
        supported_mime_types = self.config.get("supported_mime_types", [])
        if not any(mime_type.startswith(t) for t in supported_mime_types):
            print(f"Skipping unsupported file type: {mime_type}")
            return

        # Get the file content
        file_content = self.get_file_content(file_path)
        if not file_content:
            print(f"Failed to read file '{file_name}' (Path: {file_path})")
            return

        # Extract text from the file
        text = extract_text_from_file(
            file_content, mime_type, file["name"], self.config
        )
        if not text:
            print(
                f"No text could be extracted from file '{file_name}' (Path: {file_path})"
            )
            return

        # Process the file for RAG
        success = process_file_for_rag(
            file_content,
            text,
            file_path,
            web_view_link,
            file_name,
            mime_type,
            self.config,
        )

        # Update the known files dictionary
        self.known_files[file_path] = file.get("modifiedTime")

        if success:
            print(f"Successfully processed file '{file_name}' (Path: {file_path})")
        else:
            print(f"Failed to process file '{file_name}' (Path: {file_path})")

    def watch_for_changes(self, interval_seconds: int = 60) -> None:
        """
        Watch for changes in the local directory at regular intervals.

        Args:
            interval_seconds: The interval in seconds between checks
        """
        print(
            f"Starting Local File watcher in {self.watch_directory}. Checking for changes every {interval_seconds} seconds..."
        )

        try:
            # Initial scan to build the known_files dictionary
            if not self.initialized:
                print("Performing initial scan of files...")
                # Get all files in the watched directory
                initial_files = self.get_changes()

                # Build the known_files dictionary - only store the modifiedTime
                for file in initial_files:
                    # Only store the modifiedTime to avoid processing all files
                    self.known_files[file["id"]] = file.get("modifiedTime")

                print(f"Found {len(self.known_files)} files in initial scan.")
                self.initialized = True

            while True:
                # Get changes since the last check
                changed_files = self.get_changes()

                # Check for deleted files
                deleted_file_ids = self.check_for_deleted_files()

                # Process changed files
                if changed_files:
                    print(f"Found {len(changed_files)} new or modified files.")
                    for file in changed_files:
                        self.process_file(file)
                else:
                    print("No new or modified files found.")

                # Process deleted files
                if deleted_file_ids:
                    print(f"Found {len(deleted_file_ids)} deleted files.")
                    for file_id in deleted_file_ids:
                        print(f"Processing deleted file: {file_id}")
                        # Delete from database
                        delete_document_by_file_id(file_id)
                        # Remove from known_files
                        del self.known_files[file_id]

                # Wait for the next check
                print(f"Waiting {interval_seconds} seconds until next check...")
                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            print("Stopping Local File watcher...")
        except Exception as e:
            print(f"Error in Local File watcher: {e}")
