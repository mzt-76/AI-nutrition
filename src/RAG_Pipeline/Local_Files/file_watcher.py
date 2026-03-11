from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import mimetypes
import time
import json
import sys
import os
import io
import shutil

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.text_processor import extract_text_from_file, chunk_text, create_embeddings
from common.db_handler import process_file_for_rag, delete_document_by_file_id
from common.state_manager import get_state_manager, load_state_from_config, save_state_to_config

class LocalFileWatcher:
    def __init__(self, watch_directory: str = None, config_path: str = None):
        """
        Initialize the Local File watcher.

        Args:
            watch_directory: Directory to watch for files (relative to this script)
            config_path: Path to the configuration file
        """
        # Initialize state manager (database-backed state if RAG_PIPELINE_ID is set)
        self.state_manager = get_state_manager('local_files')

        # Initialize state variables before loading config (which will populate them from database)
        self.known_files = {}  # Store file paths and their last modified time
        self.initialized = False  # Flag to track if we've done the initial scan

        # Load configuration
        self.config = {}
        if config_path:
            self.config_path = config_path
        else:
            # Default to config.json in the same directory as this script
            self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
        self.load_config()

        # Set up the watch directory
        if watch_directory:
            self.watch_directory = watch_directory
        else:
            self.watch_directory = self.config.get('watch_directory', 'data')

        # Make the watch directory absolute
        self.watch_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.watch_directory)

        # Initialize mimetypes
        mimetypes.init()

        print(f"Local File Watcher initialized. Watching directory: {self.watch_directory}")

    def load_config(self) -> None:
        """
        Load configuration from JSON file and state from database (if available).

        Configuration (MIME types, processing settings) comes from config.json files.
        Runtime state (last_check_time, known_files) comes from database when RAG_PIPELINE_ID is set.
        """
        # Load configuration from file
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
            print(f"Loaded configuration from {self.config_path}")
        except Exception as e:
            print(f"Error loading configuration: {e}")
            self.config = {
                "supported_mime_types": [
                    "application/pdf",
                    "text/plain",
                    "text/csv",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ],
                "tabular_mime_types": [
                    "text/csv",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ],
                "text_processing": {
                    "default_chunk_size": 400,
                    "default_chunk_overlap": 0
                },
                "last_check_time": "1970-01-01T00:00:00.000Z"
            }
            print("Using default configuration")

        # Load state from database or config file
        if self.state_manager:
            # Use database state management
            state = self.state_manager.load_state()
            self.last_check_time = state.get('last_check_time') or datetime.strptime('1970-01-01T00:00:00.000Z', '%Y-%m-%dT%H:%M:%S.%fZ')
            self.known_files = state.get('known_files', {})
            print(f"Loaded state from database - last check: {self.last_check_time}, known files: {len(self.known_files)}")
        else:
            # Use file-based state management (backward compatibility)
            state = load_state_from_config(self.config_path)
            self.last_check_time = state.get('last_check_time') or datetime.strptime('1970-01-01T00:00:00.000Z', '%Y-%m-%dT%H:%M:%S.%fZ')
            self.known_files = {}  # File-based config doesn't store known_files
            print(f"Loaded state from config file - last check: {self.last_check_time}")

        # Apply environment variable overrides
        env_directory = os.getenv('RAG_WATCH_DIRECTORY')
        if env_directory:
            self.watch_directory = env_directory
            print(f"Override watch directory from environment: {self.watch_directory}")
            # Recreate directory if it doesn't exist
            os.makedirs(self.watch_directory, exist_ok=True)

    def save_last_check_time(self) -> None:
        """
        Save the last check time to database or config file.
        """
        if self.state_manager:
            # Save to database
            success = self.state_manager.update_last_check_time(self.last_check_time)
            if success:
                print(f"Saved last check time to database: {self.last_check_time}")
            else:
                print(f"Failed to save last check time to database")
        else:
            # Save to config file (backward compatibility)
            success = save_state_to_config(self.config_path, self.last_check_time, self.config)
            if success:
                print(f"Saved last check time to config: {self.last_check_time}")
            else:
                print(f"Failed to save last check time to config")

    def save_state(self) -> None:
        """
        Save complete state (last_check_time + known_files) to database or config file.
        """
        if self.state_manager:
            # Save complete state to database
            success = self.state_manager.save_state(
                last_check_time=self.last_check_time,
                known_files=self.known_files
            )
            if success:
                print(f"Saved complete state to database: {len(self.known_files)} known files")
            else:
                print(f"Failed to save complete state to database")
        else:
            # Only save last_check_time to config file (known_files not supported in file-based)
            self.save_last_check_time()

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
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.csv': 'text/csv',
            '.pdf': 'application/pdf',
            '.txt': 'text/plain'
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
            mime_type = 'text/plain'

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
            with open(file_path, 'rb') as f:
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
                if file_path not in self.known_files or \
                   mod_time > self.last_check_time or \
                   create_time > self.last_check_time:

                    # Get relative path for display
                    rel_path = os.path.relpath(file_path, self.watch_directory)

                    # Get MIME type
                    mime_type = self.get_mime_type(file_path)

                    # Create a file info dictionary similar to Google Drive
                    file_info = {
                        'id': file_path,  # Use file path as ID
                        'name': file_name,
                        'mimeType': mime_type,
                        'webViewLink': f"file://{file_path}",  # Local file URL
                        'modifiedTime': mod_time.isoformat(),
                        'createdTime': create_time.isoformat(),
                        'trashed': False
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

    def check_for_changes(self) -> Dict[str, Any]:
        """
        Perform a single check for changes and process them.
        This method supports both continuous and single-run execution modes.

        Returns:
            Dictionary with statistics about the check:
            {
                'files_processed': int,
                'files_deleted': int,
                'errors': int,
                'duration': float,
                'initialized': bool
            }
        """
        start_time = time.time()
        stats = {
            'files_processed': 0,
            'files_deleted': 0,
            'errors': 0,
            'duration': 0.0,
            'initialized': False
        }

        try:
            # Initial scan to process files that changed since last check and check for deletions
            if not self.initialized:
                print("Performing initial scan of files...")

                # First check for deleted files using the existing known_files from database
                deleted_file_ids = self.check_for_deleted_files()
                if deleted_file_ids:
                    print(f"Found {len(deleted_file_ids)} deleted files during initialization.")
                    for file_id in deleted_file_ids:
                        try:
                            print(f"Processing deleted file from initialization: {file_id}")
                            # Delete from database
                            delete_document_by_file_id(file_id)
                            # Remove from known_files
                            if file_id in self.known_files:
                                del self.known_files[file_id]
                            stats['files_deleted'] += 1
                        except Exception as e:
                            print(f"Error deleting file {file_id} during initialization: {e}")
                            stats['errors'] += 1

                # Now scan for changed/new files and rebuild known_files
                changed_files = []
                current_files = {}  # Track current files separately

                # Walk through the watch directory
                for root, _, files in os.walk(self.watch_directory):
                    for file_name in files:
                        file_path = os.path.join(root, file_name)
                        file_stat = os.stat(file_path)

                        # Convert to datetime for comparison
                        mod_time = datetime.fromtimestamp(file_stat.st_mtime)
                        create_time = datetime.fromtimestamp(file_stat.st_ctime)

                        # Track current files
                        current_files[file_path] = mod_time.isoformat()

                        # Check if the file is new or modified since last check
                        if mod_time > self.last_check_time or create_time > self.last_check_time:

                            # Get relative path for display
                            rel_path = os.path.relpath(file_path, self.watch_directory)

                            # Get MIME type
                            mime_type = self.get_mime_type(file_path)

                            # Create a file info dictionary similar to Google Drive
                            file_info = {
                                'id': file_path,  # Use file path as ID
                                'name': file_name,
                                'mimeType': mime_type,
                                'webViewLink': f"file://{file_path}",  # Local file URL
                                'modifiedTime': mod_time.isoformat(),
                                'createdTime': create_time.isoformat(),
                                'trashed': False
                            }

                            changed_files.append(file_info)

                # Update known_files with current files
                self.known_files = current_files

                # Process files that have changed since last check
                print(f"Found {len(changed_files)} files modified since last check during initialization.")
                for file in changed_files:
                    try:
                        print(f"Processing file from initialization: {file.get('name', 'Unknown')}")
                        self.process_file(file)
                        stats['files_processed'] += 1
                    except Exception as e:
                        print(f"Error processing file {file.get('name', 'Unknown')} during initialization: {e}")
                        stats['errors'] += 1

                # Update the last check time to now
                self.last_check_time = datetime.now()

                print(f"Processed {stats['files_processed']} files and {stats['files_deleted']} deletions during initialization.")
                self.initialized = True
                stats['initialized'] = True

            # Get changes since the last check
            changed_files = self.get_changes()

            # Check for deleted files
            deleted_file_ids = self.check_for_deleted_files()

            # Process changed files
            if changed_files:
                print(f"Found {len(changed_files)} new or modified files.")
                for file in changed_files:
                    try:
                        self.process_file(file)
                        stats['files_processed'] += 1
                    except Exception as e:
                        print(f"Error processing file {file.get('name', 'Unknown')}: {e}")
                        stats['errors'] += 1
            else:
                print("No new or modified files found.")

            # Process deleted files
            if deleted_file_ids:
                print(f"Found {len(deleted_file_ids)} deleted files.")
                for file_id in deleted_file_ids:
                    try:
                        print(f"Processing deleted file: {file_id}")
                        # Delete from database
                        delete_document_by_file_id(file_id)
                        # Remove from known_files
                        if file_id in self.known_files:
                            del self.known_files[file_id]
                        stats['files_deleted'] += 1
                    except Exception as e:
                        print(f"Error deleting file {file_id}: {e}")
                        stats['errors'] += 1

            # Calculate duration
            stats['duration'] = time.time() - start_time

            # Save complete state (last_check_time + known_files)
            self.save_state()

            return stats

        except Exception as e:
            stats['duration'] = time.time() - start_time
            stats['errors'] += 1
            print(f"Error in check_for_changes: {e}")
            raise

    def process_file(self, file: Dict[str, Any]) -> None:
        """
        Process a single file for the RAG pipeline.

        Args:
            file: File information dictionary
        """
        file_path = file['id']
        file_name, extension = os.path.splitext(file['name'])
        mime_type = file['mimeType']
        web_view_link = file['webViewLink']

        print(f"Processing file: {file_name}.{extension} (Path: {file_path})")

        # Skip unsupported file types
        supported_mime_types = self.config.get('supported_mime_types', [])
        if not any(mime_type.startswith(t) for t in supported_mime_types):
            print(f"Skipping unsupported file type: {mime_type}")
            return

        # Get the file content
        file_content = self.get_file_content(file_path)
        if not file_content:
            print(f"Failed to read file '{file_name}' (Path: {file_path})")
            return

        # Extract text from the file
        text = extract_text_from_file(file_content, mime_type, file['name'], self.config)
        if not text:
            print(f"No text could be extracted from file '{file_name}' (Path: {file_path})")
            return

        # Process the file for RAG
        success = process_file_for_rag(file_content, text, file_path, web_view_link, file_name, mime_type, self.config)

        # Update the known files dictionary
        self.known_files[file_path] = file.get('modifiedTime')

        if success:
            print(f"Successfully processed file '{file_name}' (Path: {file_path})")
        else:
            print(f"Failed to process file '{file_name}' (Path: {file_path})")

    def watch_for_changes(self, interval_seconds: int = 60) -> None:
        """
        Watch for changes in the local directory at regular intervals.
        This method runs continuously, calling check_for_changes() in a loop.

        Args:
            interval_seconds: The interval in seconds between checks
        """
        print(f"Starting Local File watcher in {self.watch_directory}. Checking for changes every {interval_seconds} seconds...")

        try:
            while True:
                # Perform a single check cycle
                stats = self.check_for_changes()

                # Log statistics
                print(f"Check complete: {stats['files_processed']} processed, {stats['files_deleted']} deleted, "
                      f"{stats['errors']} errors, {stats['duration']:.2f}s duration")

                # Wait for the next check
                print(f"Waiting {interval_seconds} seconds until next check...")
                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            print("Stopping Local File watcher...")
        except Exception as e:
            print(f"Error in Local File watcher: {e}")
