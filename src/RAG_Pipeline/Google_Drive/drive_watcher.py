import logging
from datetime import datetime, timezone
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
import time
import json
import sys
import os
import io
from typing import Any

logger = logging.getLogger(__name__)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.text_processor import extract_text_from_file
from common.db_handler import process_file_for_rag, delete_document_by_file_id

# If modifying these scopes, delete the file token.json.
SCOPES = [
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


class GoogleDriveWatcher:
    def __init__(
        self,
        credentials_path: str = "credentials.json",
        token_path: str = "token.json",
        folder_id: str | None = None,
        config_path: str | None = None,
    ):
        """
        Initialize the Google Drive watcher.

        Args:
            credentials_path: Path to the credentials.json file
            token_path: Path to the token.json file
            folder_id: ID of the specific Google Drive folder to watch (None to watch all files)
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.folder_id = folder_id
        self.service = None
        self.known_files = {}  # Store file IDs and their last modified time
        self.initialized = False  # Flag to track if we've done the initial scan

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

    def load_config(self) -> None:
        """
        Load configuration from JSON file.
        """
        try:
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
            logger.info(f"Loaded configuration from {self.config_path}")

            # Load the last check time from config
            last_check_time_str = self.config.get(
                "last_check_time", "1970-01-01T00:00:00.000Z"
            )
            try:
                self.last_check_time = datetime.strptime(
                    last_check_time_str, "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                logger.info(f"Resuming from last check time: {self.last_check_time}")
            except ValueError:
                # If the date format is invalid, use the default
                self.last_check_time = datetime.strptime(
                    "1970-01-01T00:00:00.000Z", "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                logger.warning(
                    "Invalid last check time format in config, using default"
                )

            if not self.folder_id:
                self.folder_id = self.config.get("watch_folder_id", None)

        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            self.config = {
                "supported_mime_types": [
                    "application/pdf",
                    "text/plain",
                    "text/html",
                    "text/csv",
                    "application/vnd.google-apps.document",
                    "application/vnd.google-apps.spreadsheet",
                    "application/vnd.google-apps.presentation",
                ],
                "export_mime_types": {
                    "application/vnd.google-apps.document": "text/plain",
                    "application/vnd.google-apps.spreadsheet": "text/csv",
                    "application/vnd.google-apps.presentation": "text/plain",
                },
                "text_processing": {
                    "default_chunk_size": 400,
                    "default_chunk_overlap": 0,
                },
                "last_check_time": "1970-01-01T00:00:00.000Z",
            }
            self.last_check_time = datetime.strptime(
                "1970-01-01T00:00:00.000Z", "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            logger.info("Using default configuration")

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

            logger.info(f"Saved last check time: {self.last_check_time}")
        except Exception as e:
            logger.error(f"Error saving last check time: {e}")

    def authenticate(self) -> None:
        """
        Authenticate with Google Drive API.
        """
        creds = None

        # Check if token.json exists
        if os.path.exists(self.token_path):
            try:
                with open(self.token_path) as f:
                    creds = Credentials.from_authorized_user_info(
                        json.loads(f.read()), SCOPES
                    )
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Error reading token file: {e}")
                creds = None

        # If there are no valid credentials, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except RefreshError:
                    # If refresh fails, re-authenticate
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, SCOPES
                    )
                    creds = flow.run_local_server(port=0)
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())

        # Build the Drive API service
        self.service = build("drive", "v3", credentials=creds)

    def get_folder_contents(
        self, folder_id: str, time_str: str
    ) -> list[dict[str, Any]]:
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

        results = (
            self.service.files()
            .list(
                q=query,
                pageSize=100,
                fields="nextPageToken, files(id, name, mimeType, webViewLink, modifiedTime, createdTime, trashed)",
            )
            .execute()
        )

        items = results.get("files", [])

        # Find all subfolders in this folder (regardless of modification time)
        folder_query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder'"
        folder_results = (
            self.service.files()
            .list(q=folder_query, pageSize=100, fields="files(id)")
            .execute()
        )

        subfolders = folder_results.get("files", [])

        # Recursively get contents of each subfolder
        for subfolder in subfolders:
            subfolder_items = self.get_folder_contents(subfolder["id"], time_str)
            items.extend(subfolder_items)

        return items

    def get_changes(self) -> list[dict[str, Any]]:
        """
        Get changes in Google Drive since the last check.

        Returns:
            List of changed files with their metadata
        """
        if not self.service:
            self.authenticate()

        # Convert last_check_time to RFC 3339 format
        time_str = self.last_check_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        files = []

        # If a specific folder is specified, recursively get all files in that folder and its subfolders
        if self.folder_id:
            files = self.get_folder_contents(self.folder_id, time_str)
        else:
            # If no folder is specified, get all files in the drive that were modified OR created after the specified time
            query = f"modifiedTime > '{time_str}' or createdTime > '{time_str}'"
            results = (
                self.service.files()
                .list(
                    q=query,
                    pageSize=100,
                    fields="nextPageToken, files(id, name, mimeType, webViewLink, modifiedTime, createdTime, trashed)",
                )
                .execute()
            )

            files = results.get("files", [])

        # Update the last check time
        self.last_check_time = datetime.now(timezone.utc)

        # Save the updated last check time to config
        self.save_last_check_time()

        return files

    def download_file(self, file_id: str, mime_type: str) -> bytes | None:
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
            export_mime_types = self.config.get("export_mime_types", {})
            if mime_type in export_mime_types:
                # Export the file in the appropriate format
                request = self.service.files().export_media(
                    fileId=file_id, mimeType=export_mime_types[mime_type]
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
            logger.error(f"Error downloading file {file_id}: {e}")
            return None

    def process_file(self, file: dict[str, Any]) -> None:
        """
        Process a file for the RAG pipeline.

        Args:
            file: The file metadata from Google Drive
        """
        file_id = file["id"]
        file_name = file["name"]
        mime_type = file["mimeType"]
        web_view_link = file.get("webViewLink", "")
        is_trashed = file.get("trashed", False)

        # Check if the file is in the trash
        if is_trashed:
            logger.info(
                f"File '{file_name}' (ID: {file_id}) has been trashed. Removing from database..."
            )
            delete_document_by_file_id(file_id)
            if file_id in self.known_files:
                del self.known_files[file_id]
            return

        # Skip unsupported file types
        supported_mime_types = self.config.get("supported_mime_types", [])
        if not any(mime_type.startswith(t) for t in supported_mime_types):
            logger.info(f"Skipping unsupported file type: {mime_type}")
            return

        # Download the file
        file_content = self.download_file(file_id, mime_type)
        if not file_content:
            logger.warning(f"Failed to download file '{file_name}' (ID: {file_id})")
            return

        # Extract text from the file
        text = extract_text_from_file(file_content, mime_type, file_name, self.config)
        if not text:
            logger.warning(
                f"No text could be extracted from file '{file_name}' (ID: {file_id})"
            )
            return

        # Process the file for RAG
        success = process_file_for_rag(
            file_content,
            text,
            file_id,
            web_view_link,
            file_name,
            mime_type,
            self.config,
        )

        # Update the known files dictionary
        self.known_files[file_id] = file.get("modifiedTime")

        if success:
            logger.info(f"Successfully processed file '{file_name}' (ID: {file_id})")
        else:
            logger.error(f"Failed to process file '{file_name}' (ID: {file_id})")

    def check_for_deleted_files(self) -> list[str]:
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
                file = (
                    self.service.files()
                    .get(fileId=file_id, fields="trashed,name")
                    .execute()
                )

                # If the file is in the trash, consider it deleted
                if file.get("trashed", False):
                    logger.info(
                        f"File '{file.get('name', 'Unknown')}' (ID: {file_id}) is in trash"
                    )
                    deleted_files.append(file_id)
            except Exception as e:
                # If we get an error (like file not found), the file is deleted
                if "File not found" in str(e) or "404" in str(e):
                    deleted_files.append(file_id)
                else:
                    logger.error(f"Error checking file {file_id}: {e}")

        return deleted_files

    def watch_for_changes(self, interval_seconds: int = 60) -> None:
        """
        Watch for changes in Google Drive at regular intervals.

        Args:
            interval_seconds: The interval in seconds between checks
        """
        folder_msg = f" in folder ID: {self.folder_id}" if self.folder_id else ""
        logger.info(
            f"Starting Google Drive watcher{folder_msg}. Checking for changes every {interval_seconds} seconds..."
        )

        try:
            # Authenticate if needed
            if not self.service:
                self.authenticate()

            # Initial scan to build the known_files dictionary
            if not self.initialized:
                logger.info("Performing initial scan of files...")
                # Get all files in the watched folder
                # Use the last check time from config or default to 1970-01-01
                time_str = self.last_check_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                if self.folder_id:
                    files = self.get_folder_contents(
                        self.folder_id, time_str
                    )  # Get all files
                else:
                    # If watching all of Drive, get all files
                    results = (
                        self.service.files()
                        .list(
                            pageSize=1000,
                            fields="nextPageToken, files(id, name, mimeType, webViewLink, modifiedTime, trashed)",
                        )
                        .execute()
                    )
                    files = results.get("files", [])

                # Build the known_files dictionary - only store the modifiedTime
                for file in files:
                    if not file.get("trashed", False):  # Skip files in trash
                        # Only store the modifiedTime to avoid processing all files
                        self.known_files[file["id"]] = file.get("modifiedTime")

                logger.info(f"Found {len(self.known_files)} files in initial scan.")
                self.initialized = True

            while True:
                # Get changes since the last check
                changed_files = self.get_changes()

                # Check for deleted files (every 5 cycles to reduce API calls)
                deleted_file_ids = []

                # Uncomment this code and delete the line below it if you want to check for deleted files less often (for performance gains with many files)
                # if random.random() < 0.2:  # ~20% chance each cycle, or about once every 5 cycles
                #    print("Checking for deleted files...")
                #     deleted_file_ids = self.check_for_deleted_files()
                deleted_file_ids = self.check_for_deleted_files()

                # Process changed files
                if changed_files:
                    logger.info(f"Found {len(changed_files)} changed files.")
                    for file in changed_files:
                        logger.info(file)
                        self.process_file(file)
                        # Update known_files with just the modifiedTime
                        self.known_files[file["id"]] = file.get("modifiedTime")

                # Process deleted files
                if deleted_file_ids:
                    logger.info(f"Found {len(deleted_file_ids)} deleted files.")
                    for file_id in deleted_file_ids:
                        logger.info(
                            f"File with ID: {file_id} has been deleted. Removing from database..."
                        )
                        delete_document_by_file_id(file_id)
                        # Remove from known_files
                        del self.known_files[file_id]

                # Wait for the next check
                logger.info(f"Waiting {interval_seconds} seconds until next check...")
                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            logger.info("Watcher stopped by user.")
        except Exception as e:
            logger.error(f"Error in watcher: {e}")
            raise
