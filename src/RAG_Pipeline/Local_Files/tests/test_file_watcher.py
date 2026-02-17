import pytest
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
        from Local_Files.file_watcher import LocalFileWatcher


class TestLocalFileWatcher:
    @pytest.fixture
    def mock_config(self):
        """Fixture for a mock configuration"""
        return {
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
            "text_processing": {"default_chunk_size": 400, "default_chunk_overlap": 0},
            "last_check_time": "2023-01-01T00:00:00.000Z",
            "watch_directory": "test_data",
        }

    @pytest.fixture
    def watcher(self, tmp_path, mock_config):
        """Fixture for a LocalFileWatcher instance with mocked configuration"""
        # Create a temporary config file
        config_path = tmp_path / "config.json"
        with open(config_path, "w") as f:
            json.dump(mock_config, f)

        # Create a temporary watch directory
        watch_dir = tmp_path / "test_data"
        watch_dir.mkdir()

        # Create the watcher with the temporary config file and watch directory
        return LocalFileWatcher(
            watch_directory=str(watch_dir), config_path=str(config_path)
        )

    @patch("builtins.open", new_callable=mock_open)
    @patch("json.load")
    def test_load_config_success(self, mock_json_load, mock_file_open, mock_config):
        """Test loading configuration successfully"""
        # Setup mock
        mock_json_load.return_value = mock_config

        # Create watcher with mocked open
        watcher = LocalFileWatcher(config_path="test_config.json")

        # Verify config was loaded
        assert watcher.config == mock_config
        assert watcher.watch_directory.endswith(mock_config["watch_directory"])
        # Verify last_check_time was parsed correctly
        assert watcher.last_check_time == datetime.strptime(
            "2023-01-01T00:00:00.000Z", "%Y-%m-%dT%H:%M:%S.%fZ"
        )

    def test_load_config_file_not_found(self, capfd):
        """Test loading configuration when file not found"""
        # Instead of patching all open calls, we'll use a non-existent path
        # and let the actual FileNotFoundError be raised and caught by the class

        # Create a temporary unique path that definitely doesn't exist
        import uuid

        non_existent_path = f"non_existent_config_{uuid.uuid4()}.json"

        # Create watcher with non-existent config
        watcher = LocalFileWatcher(config_path=non_existent_path)

        # Verify default config was used
        assert "supported_mime_types" in watcher.config
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
        watcher = LocalFileWatcher(config_path="test_config.json")

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

    def test_get_mime_type(self, watcher):
        """Test getting MIME type for different file extensions"""
        # Test common file extensions
        assert watcher.get_mime_type("test.pdf") == "application/pdf"
        assert watcher.get_mime_type("test.txt") == "text/plain"
        assert watcher.get_mime_type("test.csv") == "text/csv"
        assert (
            watcher.get_mime_type("test.xlsx")
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Test unknown extension
        assert watcher.get_mime_type("test.unknown") == "text/plain"

    def test_get_file_content_success(self, watcher, tmp_path):
        """Test successfully reading file content"""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_content = b"This is test content"
        with open(test_file, "wb") as f:
            f.write(test_content)

        # Call the method
        result = watcher.get_file_content(str(test_file))

        # Verify the result
        assert result == test_content

    def test_get_file_content_error(self, watcher, capfd):
        """Test error handling when reading file content"""
        # Call the method with a non-existent file
        result = watcher.get_file_content("non_existent_file.txt")

        # Verify the result
        assert result is None

        # Check that error was printed
        captured = capfd.readouterr()
        assert "Error reading file" in captured.out

    @patch("os.walk")
    @patch("os.stat")
    @patch.object(LocalFileWatcher, "get_mime_type")
    @patch.object(LocalFileWatcher, "save_last_check_time")
    def test_get_changes(self, mock_save, mock_get_mime, mock_stat, mock_walk, watcher):
        """Test getting changes in watched directory"""
        # Setup mocks
        mock_walk.return_value = [("/test_dir", [], ["file1.txt", "file2.pdf"])]

        # Create mock stat results
        class MockStat:
            def __init__(self, mtime, ctime):
                self.st_mtime = mtime
                self.st_ctime = ctime

        # Set file modification and creation times
        now_timestamp = datetime.now().timestamp()
        mock_stat.side_effect = [
            MockStat(now_timestamp, now_timestamp),  # file1.txt
            MockStat(now_timestamp, now_timestamp),  # file2.pdf
        ]

        # Set MIME types
        mock_get_mime.side_effect = ["text/plain", "application/pdf"]

        # Call the method
        result = watcher.get_changes()

        # Verify results
        assert len(result) == 2
        assert result[0]["name"] == "file1.txt"
        assert result[0]["mimeType"] == "text/plain"
        assert result[1]["name"] == "file2.pdf"
        assert result[1]["mimeType"] == "application/pdf"
        mock_save.assert_called_once()

    @patch("os.path.exists")
    def test_check_for_deleted_files(self, mock_exists, watcher):
        """Test checking for deleted files"""
        # Setup
        watcher.known_files = {
            "/test_dir/file1.txt": "2023-01-01T00:00:00Z",  # Not deleted
            "/test_dir/file2.pdf": "2023-01-01T00:00:00Z",  # Deleted
            "/test_dir/file3.csv": "2023-01-01T00:00:00Z",  # Deleted
        }

        # Mock exists to return True for file1 and False for file2 and file3
        mock_exists.side_effect = lambda path: path == "/test_dir/file1.txt"

        # Call the method
        result = watcher.check_for_deleted_files()

        # Verify results
        assert len(result) == 2
        assert "/test_dir/file2.pdf" in result
        assert "/test_dir/file3.csv" in result

    def test_process_file(self, watcher):
        """Test processing a file for the RAG pipeline"""
        # Create a mock file
        file_data = {
            "id": "/test_dir/test.txt",
            "name": "test.txt",
            "mimeType": "text/plain",
            "webViewLink": "file:///test_dir/test.txt",
            "modifiedTime": "2023-01-01T00:00:00Z",
        }

        # Mock the methods that process_file calls
        watcher.get_file_content = MagicMock(return_value=b"test content")

        with patch(
            "Local_Files.file_watcher.extract_text_from_file",
            return_value="test content",
        ), patch(
            "Local_Files.file_watcher.chunk_text", return_value=["chunk1", "chunk2"]
        ), patch(
            "Local_Files.file_watcher.create_embeddings",
            return_value=[[0.1, 0.2], [0.3, 0.4]],
        ), patch("Local_Files.file_watcher.process_file_for_rag"):
            # Call the method
            watcher.process_file(file_data)

            # Verify the known_files was updated
            assert watcher.known_files["/test_dir/test.txt"] == "2023-01-01T00:00:00Z"

    def test_process_file_unsupported_type(self, watcher, capfd):
        """Test processing a file with unsupported MIME type"""
        # Create a mock file with unsupported MIME type
        file_data = {
            "id": "/test_dir/test.bin",
            "name": "test.bin",
            "mimeType": "application/octet-stream",
            "webViewLink": "file:///test_dir/test.bin",
        }

        # Call the method
        watcher.process_file(file_data)

        # Check that message was printed
        captured = capfd.readouterr()
        assert "Skipping unsupported file type" in captured.out

    def test_process_file_read_error(self, watcher, capfd):
        """Test processing a file when reading fails"""
        # Create a mock file
        file_data = {
            "id": "/test_dir/test.txt",
            "name": "test.txt",
            "mimeType": "text/plain",
            "webViewLink": "file:///test_dir/test.txt",
        }

        # Mock get_file_content to return None (simulating read failure)
        watcher.get_file_content = MagicMock(return_value=None)

        # Call the method
        watcher.process_file(file_data)

        # Check that message was printed
        captured = capfd.readouterr()
        assert "Failed to read file" in captured.out

    def test_process_file_no_text_extracted(self, watcher, capfd):
        """Test processing a file when no text can be extracted"""
        # Create a mock file
        file_data = {
            "id": "/test_dir/test.txt",
            "name": "test.txt",
            "mimeType": "text/plain",
            "webViewLink": "file:///test_dir/test.txt",
        }

        # Mock get_file_content to return some content
        watcher.get_file_content = MagicMock(return_value=b"test content")

        # Mock extract_text_from_file to return None (simulating extraction failure)
        with patch(
            "Local_Files.file_watcher.extract_text_from_file", return_value=None
        ):
            # Call the method
            watcher.process_file(file_data)

        # Check that message was printed
        captured = capfd.readouterr()
        assert "No text could be extracted" in captured.out

    @patch.object(LocalFileWatcher, "get_changes")
    @patch.object(LocalFileWatcher, "check_for_deleted_files")
    @patch.object(LocalFileWatcher, "process_file")
    @patch("Local_Files.file_watcher.delete_document_by_file_id")
    @patch("time.sleep")
    def test_watch_for_changes(
        self,
        mock_sleep,
        mock_delete,
        mock_process,
        mock_check_deleted,
        mock_get_changes,
        watcher,
    ):
        """Test watching for changes in the local directory"""
        # Setup mocks
        # First call is for initial scan, second call is for the first check
        mock_get_changes.side_effect = [
            # Initial scan
            [
                {
                    "id": "/test_dir/file1.txt",
                    "modifiedTime": "2023-01-01T00:00:00Z",
                    "webViewLink": "file:///test_dir/file1.txt",
                },
                {
                    "id": "/test_dir/file2.pdf",
                    "modifiedTime": "2023-01-01T00:00:00Z",
                    "webViewLink": "file:///test_dir/file2.pdf",
                },
            ],
            # First check - one new file
            [
                {
                    "id": "/test_dir/file3.csv",
                    "modifiedTime": "2023-01-02T00:00:00Z",
                    "webViewLink": "file:///test_dir/file3.csv",
                }
            ],
        ]

        # Mock check_for_deleted_files to return one deleted file
        mock_check_deleted.return_value = ["/test_dir/file1.txt"]

        # We need to make sure process_file is called before check_for_deleted_files
        # to ensure both files are added to known_files before one is deleted
        def side_effect_process_file(file):
            watcher.known_files[file["id"]] = file.get("modifiedTime")

        mock_process.side_effect = side_effect_process_file

        # Mock sleep to raise KeyboardInterrupt after first iteration
        mock_sleep.side_effect = KeyboardInterrupt()

        # Call the method
        watcher.watch_for_changes(interval_seconds=1)

        # Verify file2 and file3 are in known_files (file1 was deleted)
        assert len(watcher.known_files) == 2
        assert watcher.known_files["/test_dir/file2.pdf"] == "2023-01-01T00:00:00Z"
        assert watcher.known_files["/test_dir/file3.csv"] == "2023-01-02T00:00:00Z"
        assert "/test_dir/file1.txt" not in watcher.known_files

        # Verify process_file was called for the new file
        mock_process.assert_called_once()

        # Verify delete_document_by_file_id was called for the deleted file
        mock_delete.assert_called_once_with("/test_dir/file1.txt")

        # Verify the deleted file was removed from known_files
        assert "/test_dir/file1.txt" not in watcher.known_files
