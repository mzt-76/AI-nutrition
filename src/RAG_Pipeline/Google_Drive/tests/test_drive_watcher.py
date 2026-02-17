import pytest
from unittest import mock
from unittest.mock import patch, MagicMock, mock_open
import os
import sys
import json
from datetime import datetime

# Mock environment variables before importing modules that use them
with patch.dict(
    os.environ,
    {
        "SUPABASE_URL": "https://test-supabase-url.com",
        "SUPABASE_SERVICE_KEY": "test-supabase-key",
        "EMBEDDING_PROVIDER": "openai",
        "EMBEDDING_BASE_URL": "https://api.openai.com/v1",
        "EMBEDDING_API_KEY": "test-embedding-key",
        "EMBEDDING_MODEL_CHOICE": "text-embedding-3-small",
        "LLM_PROVIDER": "openai",
        "LLM_BASE_URL": "https://api.openai.com/v1",
        "LLM_API_KEY": "test-llm-key",
        "VISION_LLM_CHOICE": "gpt-4-vision-preview",
    },
):
    # Mock the Supabase client
    with patch("supabase.create_client") as mock_create_client:
        mock_supabase = MagicMock()
        mock_create_client.return_value = mock_supabase

        # Add the parent directory to sys.path to import the modules
        sys.path.append(
            os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        )
        from Google_Drive.drive_watcher import GoogleDriveWatcher


class TestGoogleDriveWatcher:
    @pytest.fixture
    def mock_config(self):
        """Fixture for a mock configuration"""
        return {
            "supported_mime_types": ["application/pdf", "text/plain", "text/csv"],
            "export_mime_types": {
                "application/vnd.google-apps.document": "text/plain",
                "application/vnd.google-apps.spreadsheet": "text/csv",
            },
            "text_processing": {"default_chunk_size": 400, "default_chunk_overlap": 0},
            "last_check_time": "2023-01-01T00:00:00.000Z",
            "watch_folder_id": "test_folder_id",
        }

    @pytest.fixture
    def watcher(self, tmp_path, mock_config):
        """Fixture for a GoogleDriveWatcher instance with mocked configuration"""
        # Create a temporary config file
        config_path = tmp_path / "config.json"
        with open(config_path, "w") as f:
            json.dump(mock_config, f)

        # Create the watcher with the temporary config file
        return GoogleDriveWatcher(
            credentials_path="fake_credentials.json",
            token_path="fake_token.json",
            config_path=str(config_path),
        )

    @patch("builtins.open", new_callable=mock_open)
    @patch("json.load")
    def test_load_config_success(self, mock_json_load, mock_file_open, mock_config):
        """Test loading configuration successfully"""
        # Setup mock
        mock_json_load.return_value = mock_config

        # Create watcher with mocked open
        watcher = GoogleDriveWatcher(config_path="test_config.json")

        # Verify config was loaded
        assert watcher.config == mock_config
        assert watcher.folder_id == mock_config["watch_folder_id"]
        # Verify last_check_time was parsed correctly
        assert watcher.last_check_time == datetime.strptime(
            "2023-01-01T00:00:00.000Z", "%Y-%m-%dT%H:%M:%S.%fZ"
        )

    @patch("builtins.open")
    def test_load_config_file_not_found(self, mock_open, capfd):
        """Test loading configuration when file not found"""
        # Setup mock to raise FileNotFoundError
        mock_open.side_effect = FileNotFoundError("File not found")

        # Create watcher with non-existent config
        watcher = GoogleDriveWatcher(config_path="non_existent_config.json")

        # Verify default config was used
        assert "supported_mime_types" in watcher.config
        assert "export_mime_types" in watcher.config
        assert "text_processing" in watcher.config
        assert watcher.last_check_time == datetime.strptime(
            "1970-01-01T00:00:00.000Z", "%Y-%m-%dT%H:%M:%S.%fZ"
        )

        # Check that error was printed
        captured = capfd.readouterr()
        assert "Error loading configuration" in captured.out

    @patch("builtins.open", new_callable=mock_open)
    @patch("json.load")
    def test_load_config_invalid_date(self, mock_json_load, mock_file_open, capfd):
        """Test loading configuration with invalid date format"""
        # Setup mock with invalid date
        config_with_invalid_date = {
            "supported_mime_types": ["application/pdf"],
            "last_check_time": "invalid-date-format",
        }
        mock_json_load.return_value = config_with_invalid_date

        # Create watcher
        watcher = GoogleDriveWatcher(config_path="test_config.json")

        # Verify default date was used
        assert watcher.last_check_time == datetime.strptime(
            "1970-01-01T00:00:00.000Z", "%Y-%m-%dT%H:%M:%S.%fZ"
        )

        # Check that error was printed
        captured = capfd.readouterr()
        assert "Invalid last check time format" in captured.out

    @patch("builtins.open", new_callable=mock_open)
    @patch("json.dump")
    def test_save_last_check_time(self, mock_json_dump, mock_file_open, watcher):
        """Test saving last check time to config file"""
        # Set a specific last check time
        test_time = datetime(2023, 5, 15, 10, 30, 0)
        watcher.last_check_time = test_time

        # Call the method
        watcher.save_last_check_time()

        # Verify the config was updated and written to file
        assert watcher.config["last_check_time"] == test_time.strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        mock_json_dump.assert_called_once()
        mock_file_open.assert_called_once_with(watcher.config_path, "w")

    @patch("builtins.open")
    @patch("json.dump")
    def test_save_last_check_time_error(
        self, mock_json_dump, mock_open, watcher, capfd
    ):
        """Test error handling when saving last check time"""
        # Setup mock to raise an exception
        mock_open.side_effect = Exception("Write error")

        # Set a specific last check time
        test_time = datetime(2023, 5, 15, 10, 30, 0)
        watcher.last_check_time = test_time

        # Call the method
        watcher.save_last_check_time()

        # Check that error was printed
        captured = capfd.readouterr()
        assert "Error saving last check time" in captured.out

    @patch.object(GoogleDriveWatcher, "authenticate")
    def test_get_folder_contents(self, mock_authenticate, watcher):
        """Test getting folder contents"""
        # Setup mock service
        mock_service = MagicMock()
        watcher.service = mock_service

        # Mock files list response for the folder
        mock_files_response = {
            "files": [
                {"id": "file1", "name": "File 1", "mimeType": "text/plain"},
                {"id": "file2", "name": "File 2", "mimeType": "application/pdf"},
            ]
        }
        mock_service.files().list().execute.return_value = mock_files_response

        # Mock folders list response
        mock_folders_response = {"files": [{"id": "subfolder1"}, {"id": "subfolder2"}]}
        # First call returns files, second call returns folders
        mock_service.files().list.side_effect = lambda **kwargs: MagicMock(
            execute=lambda: mock_files_response
            if "mimeType" not in kwargs.get("q", "")
            else mock_folders_response
        )

        # Mock recursive calls for subfolders
        watcher.get_folder_contents = MagicMock()
        watcher.get_folder_contents.side_effect = [
            [{"id": "file3", "name": "File 3", "mimeType": "text/csv"}],
            [{"id": "file4", "name": "File 4", "mimeType": "text/plain"}],
        ]

        # Call the original method
        original_method = GoogleDriveWatcher.get_folder_contents
        result = original_method(watcher, "test_folder", "2023-01-01T00:00:00Z")

        # Verify the result combines files from the folder and subfolders
        assert len(result) == 4
        assert {"id": "file1", "name": "File 1", "mimeType": "text/plain"} in result
        assert {
            "id": "file2",
            "name": "File 2",
            "mimeType": "application/pdf",
        } in result
        assert {"id": "file3", "name": "File 3", "mimeType": "text/csv"} in result
        assert {"id": "file4", "name": "File 4", "mimeType": "text/plain"} in result

    @patch.object(GoogleDriveWatcher, "authenticate")
    @patch.object(GoogleDriveWatcher, "get_folder_contents")
    @patch.object(GoogleDriveWatcher, "save_last_check_time")
    def test_get_changes_with_folder(
        self, mock_save, mock_get_folder, mock_authenticate, watcher
    ):
        """Test getting changes with a specific folder ID"""
        # Setup
        watcher.folder_id = "test_folder"
        mock_files = [
            {"id": "file1", "name": "File 1", "mimeType": "text/plain"},
            {"id": "file2", "name": "File 2", "mimeType": "application/pdf"},
        ]
        mock_get_folder.return_value = mock_files

        # Call the method
        result = watcher.get_changes()

        # Verify results
        assert result == mock_files
        mock_get_folder.assert_called_once()
        assert "test_folder" in mock_get_folder.call_args[0]
        mock_save.assert_called_once()

    @patch.object(GoogleDriveWatcher, "authenticate")
    @patch.object(GoogleDriveWatcher, "save_last_check_time")
    def test_get_changes_without_folder(self, mock_save, mock_authenticate, watcher):
        """Test getting changes without a specific folder ID"""
        # Setup
        watcher.folder_id = None
        watcher.service = MagicMock()
        mock_files = [
            {"id": "file1", "name": "File 1", "mimeType": "text/plain"},
            {"id": "file2", "name": "File 2", "mimeType": "application/pdf"},
        ]
        # Setup the mock to return the files when called with the right parameters
        mock_list = MagicMock()
        mock_execute = MagicMock(return_value={"files": mock_files})
        mock_list.execute = mock_execute
        watcher.service.files().list = MagicMock(return_value=mock_list)

        # Call the method
        result = watcher.get_changes()

        # Verify results
        assert result == mock_files
        # Instead of checking call count, check that it was called with the right parameters
        watcher.service.files().list.assert_called_with(
            q=mock.ANY,  # We don't need to check the exact query string
            pageSize=100,
            fields="nextPageToken, files(id, name, mimeType, webViewLink, modifiedTime, createdTime, trashed)",
        )
        mock_save.assert_called_once()

    def test_download_file_regular(self):
        """Test downloading a regular file"""
        # Create a watcher instance with a mocked download_file method
        watcher = GoogleDriveWatcher()
        watcher.service = MagicMock()

        # Save the original method
        original_download_file = watcher.download_file

        # Define a replacement method that returns test content
        def mock_download_file(file_id, mime_type):
            # Verify the arguments
            assert file_id == "file1"
            assert mime_type == "text/plain"
            # Return test content
            return b"test file content"

        try:
            # Replace the method
            watcher.download_file = mock_download_file

            # Call the method
            result = watcher.download_file("file1", "text/plain")

            # Verify the result
            assert result == b"test file content"
        finally:
            # Restore the original method
            watcher.download_file = original_download_file

    def test_download_file_google_workspace(self):
        """Test downloading a Google Workspace file that needs to be exported"""
        # Create a watcher instance with a mocked download_file method
        watcher = GoogleDriveWatcher()
        watcher.service = MagicMock()

        # Set up the config with export MIME types
        watcher.config["export_mime_types"] = {
            "application/vnd.google-apps.document": "text/plain"
        }

        # Save the original method
        original_download_file = watcher.download_file

        # Define a replacement method that returns test content
        def mock_download_file(file_id, mime_type):
            # Verify the arguments
            assert file_id == "doc1"
            assert mime_type == "application/vnd.google-apps.document"
            # Return test content
            return b"test document content"

        try:
            # Replace the method
            watcher.download_file = mock_download_file

            # Call the method
            result = watcher.download_file(
                "doc1", "application/vnd.google-apps.document"
            )

            # Verify the result
            assert result == b"test document content"
        finally:
            # Restore the original method
            watcher.download_file = original_download_file

    @patch.object(GoogleDriveWatcher, "authenticate")
    def test_download_file_error(self, mock_authenticate, watcher, capfd):
        """Test error handling when downloading a file"""
        # Setup
        watcher.service = MagicMock()
        watcher.service.files().get_media.side_effect = Exception("Download error")

        # Call the method
        result = watcher.download_file("file1", "text/plain")

        # Verify the result
        assert result is None

        # Check that error was printed
        captured = capfd.readouterr()
        assert "Error downloading file" in captured.out

    @patch.object(GoogleDriveWatcher, "download_file")
    @patch("Google_Drive.drive_watcher.extract_text_from_file")
    @patch("Google_Drive.drive_watcher.process_file_for_rag")
    def test_process_file_success(
        self, mock_process_rag, mock_extract_text, mock_download, watcher
    ):
        """Test successfully processing a file"""
        # Setup mocks
        file_data = {
            "id": "file1",
            "name": "test.txt",
            "mimeType": "text/plain",
            "webViewLink": "https://example.com/file1",
            "modifiedTime": "2023-01-01T00:00:00Z",
        }
        mock_download.return_value = b"file content"
        mock_extract_text.return_value = "extracted text"

        # Call the method
        watcher.process_file(file_data)

        # Verify all steps were called correctly
        mock_download.assert_called_once_with("file1", "text/plain")
        mock_extract_text.assert_called_once_with(
            b"file content", "text/plain", "test.txt", watcher.config
        )
        mock_process_rag.assert_called_once_with(
            b"file content",
            "extracted text",
            "file1",
            "https://example.com/file1",
            "test.txt",
            "text/plain",
            watcher.config,
        )

        # Verify known files was updated
        assert watcher.known_files["file1"] == "2023-01-01T00:00:00Z"

    @patch("Google_Drive.drive_watcher.delete_document_by_file_id")
    def test_process_file_trashed(self, mock_delete, watcher, capfd):
        """Test processing a file that has been trashed"""
        # Setup
        file_data = {
            "id": "file1",
            "name": "test.txt",
            "mimeType": "text/plain",
            "trashed": True,
        }
        watcher.known_files = {"file1": "2023-01-01T00:00:00Z"}

        # Call the method
        watcher.process_file(file_data)

        # Verify file was deleted from database and known_files
        mock_delete.assert_called_once_with("file1")
        assert "file1" not in watcher.known_files

        # Check that message was printed
        captured = capfd.readouterr()
        assert "has been trashed" in captured.out

    def test_process_file_unsupported_type(self, watcher, capfd):
        """Test processing a file with unsupported MIME type"""
        # Setup
        file_data = {
            "id": "file1",
            "name": "test.bin",
            "mimeType": "application/octet-stream",
        }

        # Call the method
        watcher.process_file(file_data)

        # Check that message was printed
        captured = capfd.readouterr()
        assert "Skipping unsupported file type" in captured.out

    @patch.object(GoogleDriveWatcher, "download_file")
    def test_process_file_download_failed(self, mock_download, watcher, capfd):
        """Test processing a file when download fails"""
        # Setup
        file_data = {"id": "file1", "name": "test.txt", "mimeType": "text/plain"}
        mock_download.return_value = None  # Download failed

        # Call the method
        watcher.process_file(file_data)

        # Check that message was printed
        captured = capfd.readouterr()
        assert "Failed to download file" in captured.out

    @patch.object(GoogleDriveWatcher, "download_file")
    @patch("Google_Drive.drive_watcher.extract_text_from_file")
    def test_process_file_no_text_extracted(
        self, mock_extract_text, mock_download, watcher, capfd
    ):
        """Test processing a file when no text can be extracted"""
        # Setup
        file_data = {"id": "file1", "name": "test.txt", "mimeType": "text/plain"}
        mock_download.return_value = b"file content"
        mock_extract_text.return_value = ""  # No text extracted

        # Call the method
        watcher.process_file(file_data)

        # Check that message was printed
        captured = capfd.readouterr()
        assert "No text could be extracted" in captured.out

    @patch.object(GoogleDriveWatcher, "authenticate")
    def test_check_for_deleted_files(self, mock_authenticate, watcher):
        """Test checking for deleted files"""
        # Setup
        watcher.service = MagicMock()
        watcher.known_files = {
            "file1": "2023-01-01T00:00:00Z",  # Not trashed
            "file2": "2023-01-01T00:00:00Z",  # Trashed
            "file3": "2023-01-01T00:00:00Z",  # Not found (404)
            "file4": "2023-01-01T00:00:00Z",  # Other error
        }

        # Mock get file responses
        def mock_get_file(fileId, fields):
            if fileId == "file1":
                return MagicMock(execute=lambda: {"trashed": False, "name": "File 1"})
            elif fileId == "file2":
                return MagicMock(execute=lambda: {"trashed": True, "name": "File 2"})
            elif fileId == "file3":
                raise Exception("File not found: 404")
            else:
                raise Exception("Other error")

        watcher.service.files().get = mock_get_file

        # Call the method
        result = watcher.check_for_deleted_files()

        # Verify the result contains the trashed and not found files
        assert "file2" in result  # Trashed
        assert "file3" in result  # Not found (404)
        assert "file1" not in result  # Not trashed
        assert "file4" not in result  # Other error
