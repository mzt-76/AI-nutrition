import pytest
from unittest.mock import patch, MagicMock, call
import os
import sys
import json

# Mock environment variables before importing modules that use them
with patch.dict(
    os.environ,
    {
        "SUPABASE_URL": "https://test-supabase-url.com",
        "SUPABASE_SERVICE_KEY": "test-supabase-key",
    },
):
    # Mock the create_client function before it's used in db_handler
    with patch("supabase.create_client") as mock_create_client:
        # Configure the mock to return a MagicMock
        mock_supabase = MagicMock()
        mock_create_client.return_value = mock_supabase

        # Add the parent directory to sys.path to import the modules
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        from common.db_handler import (
            delete_document_by_file_id,
            insert_document_chunks,
            insert_or_update_document_metadata,
            insert_document_rows,
            process_file_for_rag,
        )


# Create a mock for supabase client
@pytest.fixture
def mock_supabase():
    return MagicMock()


class TestDeleteDocumentByFileId:
    @patch("common.db_handler.supabase")
    def test_successful_deletion(self, mock_supabase):
        """Test deleting document by file ID"""
        # Setup mocks
        mock_documents_delete = MagicMock()
        mock_documents_delete.eq.return_value.execute.return_value.data = [
            {"id": 1},
            {"id": 2},
        ]

        mock_rows_delete = MagicMock()
        mock_rows_delete.eq.return_value.execute.return_value.data = [
            {"id": 3},
            {"id": 4},
            {"id": 5},
        ]

        mock_metadata_delete = MagicMock()
        mock_metadata_delete.eq.return_value.execute.return_value.data = [
            {"id": "file123"}
        ]

        mock_supabase.table.side_effect = [
            mock_documents_delete,
            mock_rows_delete,
            mock_metadata_delete,
        ]

        # Call the function
        delete_document_by_file_id("file123")

        # Assertions
        mock_supabase.table.assert_has_calls(
            [call("documents"), call("document_rows"), call("document_metadata")]
        )

        mock_documents_delete.delete.assert_called_once()
        mock_documents_delete.delete.return_value.eq.assert_called_once_with(
            "metadata->>file_id", "file123"
        )

        mock_rows_delete.delete.assert_called_once()
        mock_rows_delete.delete.return_value.eq.assert_called_once_with(
            "dataset_id", "file123"
        )

        mock_metadata_delete.delete.assert_called_once()
        mock_metadata_delete.delete.return_value.eq.assert_called_once_with(
            "id", "file123"
        )

    @patch("common.db_handler.supabase")
    def test_with_error(self, mock_supabase, capfd):
        """Test handling errors when deleting document"""
        # Setup mocks to raise exceptions
        mock_documents_delete = MagicMock()
        mock_documents_delete.delete.return_value.eq.return_value.execute.side_effect = Exception(
            "DB error"
        )

        mock_supabase.table.return_value = mock_documents_delete

        # Call the function with error handling
        delete_document_by_file_id("file123")

        # Verify error was logged
        captured = capfd.readouterr()
        assert "Error deleting documents: DB error" in captured.out


class TestInsertDocumentChunks:
    @patch("common.db_handler.supabase")
    def test_successful_insertion(self, mock_supabase):
        """Test inserting document chunks with embeddings"""
        # Setup test data
        chunks = ["Chunk 1", "Chunk 2"]
        embeddings = [[0.1, 0.2], [0.3, 0.4]]
        file_id = "file123"
        file_url = "https://example.com/file123"
        file_title = "Test File"

        # Setup mock
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table

        # Call the function
        insert_document_chunks(
            chunks, embeddings, file_id, file_url, file_title, "text/plain"
        )

        # Assertions
        mock_supabase.table.assert_called_with("documents")
        assert mock_table.insert.call_count == 2

        # Check first chunk insertion
        first_call_args = mock_table.insert.call_args_list[0][0][0]
        assert first_call_args["content"] == "Chunk 1"
        assert first_call_args["embedding"] == [0.1, 0.2]
        assert first_call_args["metadata"]["file_id"] == "file123"
        assert first_call_args["metadata"]["file_url"] == "https://example.com/file123"
        assert first_call_args["metadata"]["file_title"] == "Test File"
        assert first_call_args["metadata"]["chunk_index"] == 0

        # Check second chunk insertion
        second_call_args = mock_table.insert.call_args_list[1][0][0]
        assert second_call_args["content"] == "Chunk 2"
        assert second_call_args["embedding"] == [0.3, 0.4]
        assert second_call_args["metadata"]["chunk_index"] == 1

    def test_mismatch_error(self, capfd):
        """Test error when chunks and embeddings counts don't match"""
        chunks = ["Chunk 1", "Chunk 2"]
        embeddings = [[0.1, 0.2]]  # Only one embedding
        file_id = "file123"
        file_url = "https://example.com/file123"
        file_title = "Test File"
        mime_type = "text/plain"

        # Mock the supabase client to avoid actual API calls
        with patch("common.db_handler.supabase"):
            # The function catches the ValueError and prints an error message
            insert_document_chunks(
                chunks, embeddings, file_id, file_url, file_title, mime_type
            )

            # Capture the printed output
            captured = capfd.readouterr()
            assert (
                "Error inserting/updating document chunks: Number of chunks and embeddings must match"
                in captured.out
            )


class TestInsertOrUpdateDocumentMetadata:
    @patch("common.db_handler.supabase")
    def test_insert_new_record(self, mock_supabase, capfd):
        """Test inserting new document metadata"""
        # Setup mocks
        mock_select = MagicMock()
        mock_select.execute.return_value.data = []  # No existing record

        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value = mock_select

        mock_supabase.table.return_value = mock_table

        # Call the function
        insert_or_update_document_metadata(
            "file123", "Test File", "https://example.com"
        )

        # Assertions
        mock_table.select.assert_called_once_with("*")
        mock_table.select.return_value.eq.assert_called_once_with("id", "file123")

        # Should insert new record
        mock_table.insert.assert_called_once()
        insert_args = mock_table.insert.call_args[0][0]
        assert insert_args["id"] == "file123"
        assert insert_args["title"] == "Test File"
        assert insert_args["url"] == "https://example.com"

        # Should print success message
        captured = capfd.readouterr()
        assert "Inserted metadata for file 'Test File' (ID: file123)" in captured.out

    @patch("common.db_handler.supabase")
    def test_update_existing_record(self, mock_supabase, capfd):
        """Test updating existing document metadata"""
        # Setup mocks
        mock_select = MagicMock()
        mock_select.execute.return_value.data = [{"id": "file123"}]  # Existing record

        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value = mock_select

        mock_supabase.table.return_value = mock_table

        # Call the function
        insert_or_update_document_metadata(
            "file123", "Test File", "https://example.com", ["col1", "col2"]
        )

        # Assertions
        # Should update existing record
        mock_table.update.assert_called_once()
        update_args = mock_table.update.call_args[0][0]
        assert update_args["id"] == "file123"
        assert update_args["title"] == "Test File"
        assert update_args["url"] == "https://example.com"
        assert update_args["schema"] == json.dumps(["col1", "col2"])

        mock_table.update.return_value.eq.assert_called_once_with("id", "file123")

        # Should print success message
        captured = capfd.readouterr()
        assert "Updated metadata for file 'Test File' (ID: file123)" in captured.out

    @patch("common.db_handler.supabase")
    def test_error_handling(self, mock_supabase, capfd):
        """Test error handling in metadata insertion/update"""
        # Setup mock to raise exception
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.execute.side_effect = Exception(
            "DB error"
        )

        mock_supabase.table.return_value = mock_table

        # Call the function
        insert_or_update_document_metadata(
            "file123", "Test File", "https://example.com"
        )

        # Verify error was logged
        captured = capfd.readouterr()
        assert "Error inserting/updating document metadata: DB error" in captured.out


class TestInsertDocumentRows:
    @patch("common.db_handler.supabase")
    def test_successful_insertion(self, mock_supabase, capfd):
        """Test inserting document rows"""
        # Setup test data
        file_id = "file123"
        rows = [{"name": "John", "age": 30}, {"name": "Jane", "age": 25}]

        # Setup mock
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table

        # Call the function
        insert_document_rows(file_id, rows)

        # Assertions
        # Should delete existing rows first
        mock_table.delete.assert_called_once()
        mock_table.delete.return_value.eq.assert_called_once_with(
            "dataset_id", "file123"
        )

        # Should insert new rows
        assert mock_table.insert.call_count == 2

        # Check first row insertion
        first_call_args = mock_table.insert.call_args_list[0][0][0]
        assert first_call_args["dataset_id"] == "file123"
        assert first_call_args["row_data"] == {"name": "John", "age": 30}

        # Check second row insertion
        second_call_args = mock_table.insert.call_args_list[1][0][0]
        assert second_call_args["dataset_id"] == "file123"
        assert second_call_args["row_data"] == {"name": "Jane", "age": 25}

        # Should print success message
        captured = capfd.readouterr()
        assert "Inserted 2 rows for file ID: file123" in captured.out

    @patch("common.db_handler.supabase")
    def test_error_handling(self, mock_supabase, capfd):
        """Test error handling in document rows insertion"""
        # Setup mock to raise exception
        mock_table = MagicMock()
        mock_table.delete.return_value.eq.return_value.execute.side_effect = Exception(
            "DB error"
        )

        mock_supabase.table.return_value = mock_table

        # Call the function
        insert_document_rows("file123", [{"name": "John"}])

        # Verify error was logged
        captured = capfd.readouterr()
        assert "Error inserting document rows: DB error" in captured.out


class TestProcessFileForRag:
    @pytest.fixture
    def setup_mocks(self):
        """Setup common mocks for process_file_for_rag tests"""
        with patch(
            "common.db_handler.delete_document_by_file_id"
        ) as mock_delete_document, patch(
            "common.db_handler.insert_or_update_document_metadata"
        ) as mock_insert_metadata, patch(
            "common.db_handler.insert_document_rows"
        ) as mock_insert_rows, patch(
            "common.db_handler.insert_document_chunks"
        ) as mock_insert_chunks, patch(
            "common.db_handler.is_tabular_file"
        ) as mock_is_tabular, patch(
            "common.db_handler.extract_schema_from_csv"
        ) as mock_extract_schema, patch(
            "common.db_handler.extract_rows_from_csv"
        ) as mock_extract_rows, patch(
            "common.db_handler.chunk_text"
        ) as mock_chunk_text, patch(
            "common.db_handler.create_embeddings"
        ) as mock_create_embeddings:
            yield {
                "delete_document": mock_delete_document,
                "insert_metadata": mock_insert_metadata,
                "insert_rows": mock_insert_rows,
                "insert_chunks": mock_insert_chunks,
                "is_tabular": mock_is_tabular,
                "extract_schema": mock_extract_schema,
                "extract_rows": mock_extract_rows,
                "chunk_text": mock_chunk_text,
                "create_embeddings": mock_create_embeddings,
            }

    def test_non_tabular_file(self, setup_mocks):
        """Test processing non-tabular file for RAG"""
        mocks = setup_mocks

        # Setup mocks
        mocks["is_tabular"].return_value = False
        mocks["chunk_text"].return_value = ["Chunk 1", "Chunk 2"]
        mocks["create_embeddings"].return_value = [[0.1, 0.2], [0.3, 0.4]]

        # Test data
        file_content = b"file content"
        content = "Text content"
        file_id = "file123"
        file_url = "https://example.com/file123"
        file_title = "Test File"
        mime_type = "text/plain"

        # Call the function
        process_file_for_rag(
            file_content,
            content,
            file_id,
            file_url,
            file_title,
            mime_type,
            config={
                "text_processing": {
                    "default_chunk_size": 400,
                    "default_chunk_overlap": 0,
                }
            },
        )

        # Assertions
        mocks["delete_document"].assert_called_once_with(file_id)
        mocks["is_tabular"].assert_called_once_with(
            mime_type,
            {
                "text_processing": {
                    "default_chunk_size": 400,
                    "default_chunk_overlap": 0,
                }
            },
        )
        mocks["insert_metadata"].assert_called_once_with(
            file_id, file_title, file_url, None
        )
        mocks["extract_rows"].assert_not_called()
        mocks["insert_rows"].assert_not_called()
        mocks["chunk_text"].assert_called_once_with(content, chunk_size=400, overlap=0)
        mocks["create_embeddings"].assert_called_once_with(["Chunk 1", "Chunk 2"])
        mocks["insert_chunks"].assert_called_once_with(
            ["Chunk 1", "Chunk 2"],
            [[0.1, 0.2], [0.3, 0.4]],
            file_id,
            file_url,
            file_title,
            mime_type,
        )

    def test_tabular_file(self, setup_mocks):
        """Test processing tabular file for RAG"""
        mocks = setup_mocks

        # Setup mocks
        mocks["is_tabular"].return_value = True
        mocks["extract_schema"].return_value = ["col1", "col2"]
        mocks["extract_rows"].return_value = [{"col1": "val1", "col2": "val2"}]
        mocks["chunk_text"].return_value = ["Chunk 1", "Chunk 2"]
        mocks["create_embeddings"].return_value = [[0.1, 0.2], [0.3, 0.4]]

        # Test data
        file_content = b"col1,col2\nval1,val2"
        content = "col1,col2\nval1,val2"
        file_id = "file123"
        file_url = "https://example.com/file123"
        file_title = "Test File.csv"
        mime_type = "text/csv"

        # Call the function
        process_file_for_rag(
            file_content,
            content,
            file_id,
            file_url,
            file_title,
            mime_type,
            config={
                "text_processing": {
                    "default_chunk_size": 400,
                    "default_chunk_overlap": 0,
                }
            },
        )

        # Assertions
        mocks["delete_document"].assert_called_once_with(file_id)
        mocks["is_tabular"].assert_called_once_with(
            mime_type,
            {
                "text_processing": {
                    "default_chunk_size": 400,
                    "default_chunk_overlap": 0,
                }
            },
        )
        mocks["extract_schema"].assert_called_once_with(file_content)
        mocks["insert_metadata"].assert_called_once_with(
            file_id, file_title, file_url, ["col1", "col2"]
        )
        mocks["extract_rows"].assert_called_once_with(file_content)
        mocks["insert_rows"].assert_called_once_with(
            file_id, [{"col1": "val1", "col2": "val2"}]
        )
        mocks["chunk_text"].assert_called_once_with(content, chunk_size=400, overlap=0)
        mocks["create_embeddings"].assert_called_once_with(["Chunk 1", "Chunk 2"])
        mocks["insert_chunks"].assert_called_once_with(
            ["Chunk 1", "Chunk 2"],
            [[0.1, 0.2], [0.3, 0.4]],
            file_id,
            file_url,
            file_title,
            mime_type,
        )
