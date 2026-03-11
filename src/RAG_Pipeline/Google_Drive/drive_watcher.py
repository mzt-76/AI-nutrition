from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
import random
import time
import json
import sys
import os
import io
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.text_processor import extract_text_from_file, chunk_text, create_embeddings
from common.db_handler import process_file_for_rag, delete_document_by_file_id
from common.state_manager import get_state_manager, load_state_from_config, save_state_to_config

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly',
          'https://www.googleapis.com/auth/drive.readonly']

class GoogleDriveWatcher:
    def __init__(self, credentials_path: str = 'credentials.json', token_path: str = 'token.json', folder_id: str = None, config_path: str = None):
        """
        Initialize the Google Drive watcher.

        Args:
            credentials_path: Path to the credentials.json file
            token_path: Path to the token.json file
            folder_id: ID of the specific Google Drive folder to watch (None to watch all files)
            config_path: Path to the configuration file
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.folder_id = folder_id
        self.service = None
        self.known_files = {}  # Store file IDs and their last modified time
        self.initialized = False  # Flag to track if we've done the initial scan

        # Initialize state manager (database-backed state if RAG_PIPELINE_ID is set)
        self.state_manager = get_state_manager('google_drive')

        # Load configuration
        self.config = {}
        if config_path:
            self.config_path = config_path
        else:
            # Default to config.json in the same directory as this script
            self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
        self.load_config()

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
                    "text/html",
                    "text/csv",
                    "application/vnd.google-apps.document",
                    "application/vnd.google-apps.spreadsheet",
                    "application/vnd.google-apps.presentation"
                ],
                "export_mime_types": {
                    "application/vnd.google-apps.document": "text/plain",
                    "application/vnd.google-apps.spreadsheet": "text/csv",
                    "application/vnd.google-apps.presentation": "text/plain"
                },
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
        env_folder_id = os.getenv('RAG_WATCH_FOLDER_ID')
        if env_folder_id:
            self.folder_id = env_folder_id
            print(f"Override folder ID from environment: {self.folder_id}")
        elif not self.folder_id:
            self.folder_id = self.config.get('watch_folder_id', None)

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

    def authenticate(self) -> None:
        """
        Authenticate with Google Drive API.
        Supports both service account (for cloud deployment) and OAuth2 (for local development).
        """
        creds = None

        # Priority 1: Check for service account credentials in environment variable
        service_account_json = os.getenv('GOOGLE_DRIVE_CREDENTIALS_JSON')
        if service_account_json:
            try:
                # Parse the service account credentials from environment variable
                service_account_info = json.loads(service_account_json)
                creds = ServiceAccountCredentials.from_service_account_info(
                    service_account_info, scopes=SCOPES)
                # Service account creds are always valid (they self-refresh on first request)
                print("Using service account authentication for Google Drive")
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error parsing service account credentials: {e}")
                print("Falling back to OAuth2 authentication")

        # Priority 2: Check for existing OAuth2 token (backward compatibility)
        if not creds and os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_info(
                    json.loads(open(self.token_path).read()), SCOPES)
                print("Using existing OAuth2 token for Google Drive")
            except Exception as e:
                print(f"Error loading OAuth2 token: {e}")

        # Priority 3: OAuth2 flow for interactive authentication (local development)
        # Skip this for service account credentials (they self-refresh)
        if creds and isinstance(creds, ServiceAccountCredentials):
            pass  # Service account creds handle refresh automatically
        elif not creds or not creds.valid:
            if creds and hasattr(creds, 'expired') and creds.expired and hasattr(creds, 'refresh_token') and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    print("Refreshed OAuth2 token for Google Drive")
                except RefreshError:
                    print("OAuth2 token refresh failed, re-authenticating...")
                    creds = self._oauth2_authenticate()
            else:
                print("No valid credentials found, starting OAuth2 authentication...")
                creds = self._oauth2_authenticate()

        # Build the Drive API service
        self.service = build('drive', 'v3', credentials=creds)
        print("Google Drive API service initialized successfully")

    def _oauth2_authenticate(self) -> Credentials:
        """
        Perform OAuth2 authentication flow.

        Returns:
            Authenticated credentials
        """
        if not os.path.exists(self.credentials_path):
            raise FileNotFoundError(
                f"Google Drive credentials file not found: {self.credentials_path}. "
                f"Either provide OAuth2 credentials file or set GOOGLE_DRIVE_CREDENTIALS_JSON environment variable."
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            self.credentials_path, SCOPES)
        creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        try:
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
            print(f"OAuth2 token saved to {self.token_path}")
        except Exception as e:
            print(f"Warning: Could not save OAuth2 token: {e}")

        return creds

    def get_folder_contents(self, folder_id: str, time_str: str) -> List[Dict[str, Any]]:
        """
        Get all files and subfolders in a folder that have been modified or created after the specified time.

        Args:
            folder_id: The ID of the folder to check
            time_str: The time string in RFC 3339 format

        Returns:
            List of files and folders with their metadata
        """
        # Query for files in this folder that were modified OR created after the specified time
        query = f"(modifiedTime > '{time_str}' or createdTime > '{time_str}') and '{folder_id}' in parents"

        results = self.service.files().list(
            q=query,
            pageSize=100,
            fields="nextPageToken, files(id, name, mimeType, webViewLink, modifiedTime, createdTime, trashed)"
        ).execute()

        items = results.get('files', [])

        # Find all subfolders in this folder (regardless of modification time)
        folder_query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder'"
        folder_results = self.service.files().list(
            q=folder_query,
            pageSize=100,
            fields="files(id)"
        ).execute()

        subfolders = folder_results.get('files', [])

        # Recursively get contents of each subfolder
        for subfolder in subfolders:
            subfolder_items = self.get_folder_contents(subfolder['id'], time_str)
            items.extend(subfolder_items)

        return items

    def get_changes(self) -> List[Dict[str, Any]]:
        """
        Get changes in Google Drive since the last check.

        Returns:
            List of changed files with their metadata
        """
        if not self.service:
            self.authenticate()

        # Convert last_check_time to RFC 3339 format
        time_str = self.last_check_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

        files = []

        # If a specific folder is specified, recursively get all files in that folder and its subfolders
        if self.folder_id:
            files = self.get_folder_contents(self.folder_id, time_str)
        else:
            # If no folder is specified, get all files in the drive that were modified OR created after the specified time
            query = f"modifiedTime > '{time_str}' or createdTime > '{time_str}'"
            results = self.service.files().list(
                q=query,
                pageSize=100,
                fields="nextPageToken, files(id, name, mimeType, webViewLink, modifiedTime, createdTime, trashed)"
            ).execute()

            files = results.get('files', [])

        # Update the last check time
        self.last_check_time = datetime.now(timezone.utc)

        # Save the updated last check time to config
        self.save_last_check_time()

        return files

    def download_file(self, file_id: str, mime_type: str) -> Optional[bytes]:
        """
        Download a file from Google Drive.

        Args:
            file_id: The ID of the file to download
            mime_type: The MIME type of the file

        Returns:
            The file content as bytes, or None if download failed
        """
        if not self.service:
            self.authenticate()

        try:
            file_content = io.BytesIO()

            # Check if this is a Google Workspace file that needs to be exported
            export_mime_types = self.config.get('export_mime_types', {})
            if mime_type in export_mime_types:
                # Export the file in the appropriate format
                request = self.service.files().export_media(
                    fileId=file_id,
                    mimeType=export_mime_types[mime_type]
                )
            else:
                # For regular files, download directly
                request = self.service.files().get_media(fileId=file_id)

            # Download the file
            downloader = MediaIoBaseDownload(file_content, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()

            # Reset the pointer to the beginning of the file
            file_content.seek(0)
            return file_content.read()

        except Exception as e:
            print(f"Error downloading file {file_id}: {e}")
            return None

    def process_file(self, file: Dict[str, Any]) -> None:
        """
        Process a file for the RAG pipeline.

        Args:
            file: The file metadata from Google Drive
        """
        file_id = file['id']
        file_name = file['name']
        mime_type = file['mimeType']
        web_view_link = file.get('webViewLink', '')
        is_trashed = file.get('trashed', False)

        # Check if the file is in the trash
        if is_trashed:
            print(f"File '{file_name}' (ID: {file_id}) has been trashed. Removing from database...")
            delete_document_by_file_id(file_id)
            if file_id in self.known_files:
                del self.known_files[file_id]
            return

        # Skip unsupported file types
        supported_mime_types = self.config.get('supported_mime_types', [])
        if not any(mime_type.startswith(t) for t in supported_mime_types):
            print(f"Skipping unsupported file type: {mime_type}")
            return

        # Download the file
        file_content = self.download_file(file_id, mime_type)
        if not file_content:
            print(f"Failed to download file '{file_name}' (ID: {file_id})")
            return

        # Extract text from the file
        text = extract_text_from_file(file_content, mime_type, file_name, self.config)
        if not text:
            print(f"No text could be extracted from file '{file_name}' (ID: {file_id})")
            return

        # Process the file for RAG
        success = process_file_for_rag(file_content, text, file_id, web_view_link, file_name, mime_type, self.config)

        # Update the known files dictionary
        self.known_files[file_id] = file.get('modifiedTime')

        if success:
            print(f"Successfully processed file '{file_name}' (ID: {file_id})")
        else:
            print(f"Failed to process file '{file_name}' (ID: {file_id})")

    def check_for_deleted_files(self) -> List[str]:
        """
        Check for files that have been deleted from Google Drive.

        Returns:
            List of IDs of deleted files
        """
        if not self.service:
            self.authenticate()

        # We'll only check files we know about
        deleted_files = []

        # Only check if we have known files
        if not self.known_files:
            return deleted_files

        # Check each known file to see if it still exists or has been trashed
        for file_id in list(self.known_files.keys()):
            try:
                # Get the file metadata
                file = self.service.files().get(
                    fileId=file_id,
                    fields="trashed,name"
                ).execute()

                # If the file is in the trash, consider it deleted
                if file.get('trashed', False):
                    print(f"File '{file.get('name', 'Unknown')}' (ID: {file_id}) is in trash")
                    deleted_files.append(file_id)
            except Exception as e:
                # If we get an error (like file not found), the file is deleted
                if 'File not found' in str(e) or '404' in str(e):
                    deleted_files.append(file_id)
                else:
                    print(f"Error checking file {file_id}: {e}")

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
            # Authenticate if needed
            if not self.service:
                self.authenticate()

            # Initial scan to build the known_files dictionary and process any changes since last check
            if not self.initialized:
                print("Performing initial scan of files...")
                # Get all files in the watched folder that have changed since last check
                time_str = self.last_check_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
                if self.folder_id:
                    changed_files = self.get_folder_contents(self.folder_id, time_str)
                else:
                    # If watching all of Drive, get files changed since last check
                    query = f"modifiedTime > '{time_str}' or createdTime > '{time_str}'"
                    results = self.service.files().list(
                        q=query,
                        pageSize=1000,
                        fields="nextPageToken, files(id, name, mimeType, webViewLink, modifiedTime, createdTime, trashed)"
                    ).execute()
                    changed_files = results.get('files', [])

                # Process files that have changed since last check
                print(f"Found {len(changed_files)} files modified since last check during initialization.")
                for file in changed_files:
                    if not file.get('trashed', False):  # Skip files in trash
                        try:
                            print(f"Processing file from initialization: {file.get('name', 'Unknown')}")
                            self.process_file(file)
                            # Update known_files with just the modifiedTime
                            self.known_files[file['id']] = file.get('modifiedTime')
                            stats['files_processed'] += 1
                        except Exception as e:
                            print(f"Error processing file {file.get('name', 'Unknown')} during initialization: {e}")
                            stats['errors'] += 1

                # Update last_check_time to now (same as get_changes() would do)
                self.last_check_time = datetime.now(timezone.utc)

                print(f"Processed {stats['files_processed']} files during initialization.")
                self.initialized = True
                stats['initialized'] = True

            # Get changes since the last check
            changed_files = self.get_changes()

            # Check for deleted files
            deleted_file_ids = self.check_for_deleted_files()

            # Process changed files
            if changed_files:
                print(f"Found {len(changed_files)} changed files.")
                for file in changed_files:
                    try:
                        print(file)
                        self.process_file(file)
                        # Update known_files with just the modifiedTime
                        self.known_files[file['id']] = file.get('modifiedTime')
                        stats['files_processed'] += 1
                    except Exception as e:
                        print(f"Error processing file {file.get('name', 'Unknown')}: {e}")
                        stats['errors'] += 1

            # Process deleted files
            if deleted_file_ids:
                print(f"Found {len(deleted_file_ids)} deleted files.")
                for file_id in deleted_file_ids:
                    try:
                        print(f"File with ID: {file_id} has been deleted. Removing from database...")
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

    def watch_for_changes(self, interval_seconds: int = 60) -> None:
        """
        Watch for changes in Google Drive at regular intervals.
        This method runs continuously, calling check_for_changes() in a loop.

        Args:
            interval_seconds: The interval in seconds between checks
        """
        folder_msg = f" in folder ID: {self.folder_id}" if self.folder_id else ""
        print(f"Starting Google Drive watcher{folder_msg}. Checking for changes every {interval_seconds} seconds...")

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
            print("Watcher stopped by user.")
        except Exception as e:
            print(f"Error in watcher: {e}")
            raise
