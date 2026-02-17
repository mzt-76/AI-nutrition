import pytest
import os
import sys
from unittest.mock import MagicMock, patch

# Add the parent directory to sys.path to import the modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


@pytest.fixture
def mock_google_service():
    """Fixture for a mock Google Drive service"""
    mock_service = MagicMock()

    # Mock files().list() method
    mock_files_list = MagicMock()
    mock_files_list.execute.return_value = {
        "files": [
            {
                "id": "file1",
                "name": "File 1",
                "mimeType": "text/plain",
                "modifiedTime": "2023-01-01T00:00:00Z",
            },
            {
                "id": "file2",
                "name": "File 2",
                "mimeType": "application/pdf",
                "modifiedTime": "2023-01-02T00:00:00Z",
            },
        ]
    }
    mock_service.files().list.return_value = mock_files_list

    # Mock files().get() method
    mock_get = MagicMock()
    mock_get.execute.return_value = {"id": "file1", "name": "File 1", "trashed": False}
    mock_service.files().get.return_value = mock_get

    # Mock files().get_media() method
    mock_service.files().get_media.return_value = MagicMock()

    # Mock files().export_media() method
    mock_service.files().export_media.return_value = MagicMock()

    return mock_service


@pytest.fixture
def mock_credentials():
    """Fixture for mock Google credentials"""
    mock_creds = MagicMock()
    mock_creds.valid = True
    return mock_creds


@pytest.fixture
def default_config():
    """Fixture for default configuration"""
    return {
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
        "text_processing": {"default_chunk_size": 400, "default_chunk_overlap": 0},
        "last_check_time": "2023-01-01T00:00:00.000Z",
        "watch_folder_id": "test_folder_id",
    }


@pytest.fixture
def mock_file_data():
    """Fixture for mock file data"""
    return {
        "id": "file1",
        "name": "test.txt",
        "mimeType": "text/plain",
        "webViewLink": "https://example.com/file1",
        "modifiedTime": "2023-01-01T00:00:00Z",
        "createdTime": "2023-01-01T00:00:00Z",
        "trashed": False,
    }


@pytest.fixture
def mock_text_processor():
    """Fixture to mock text_processor functions"""
    with patch(
        "Google_Drive.drive_watcher.extract_text_from_file"
    ) as mock_extract, patch(
        "Google_Drive.drive_watcher.chunk_text"
    ) as mock_chunk, patch(
        "Google_Drive.drive_watcher.create_embeddings"
    ) as mock_embeddings:
        mock_extract.return_value = "Extracted text content"
        mock_chunk.return_value = ["Chunk 1", "Chunk 2"]
        mock_embeddings.return_value = [[0.1, 0.2], [0.3, 0.4]]

        yield {
            "extract_text_from_file": mock_extract,
            "chunk_text": mock_chunk,
            "create_embeddings": mock_embeddings,
        }


@pytest.fixture
def mock_db_handler():
    """Fixture to mock db_handler functions"""
    with patch(
        "Google_Drive.drive_watcher.process_file_for_rag"
    ) as mock_process, patch(
        "Google_Drive.drive_watcher.delete_document_by_file_id"
    ) as mock_delete:
        yield {
            "process_file_for_rag": mock_process,
            "delete_document_by_file_id": mock_delete,
        }
