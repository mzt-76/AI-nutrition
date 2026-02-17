import pytest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys

# Mock environment variables before importing modules that use them
with patch.dict(
    os.environ,
    {
        "EMBEDDING_PROVIDER": "openai",
        "EMBEDDING_BASE_URL": "https://api.openai.com/v1",
        "EMBEDDING_API_KEY": "test-api-key",
        "EMBEDDING_MODEL_CHOICE": "text-embedding-3-small",
    },
):
    # Mock the AsyncOpenAI client before it's used in text_processor
    with patch("openai.AsyncOpenAI") as mock_openai_client:
        # Configure the mock to return a MagicMock
        mock_client = MagicMock()
        mock_openai_client.return_value = mock_client

        # Add the parent directory to sys.path to import the modules
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        from common.text_processor import (
            chunk_text,
            extract_text_from_pdf,
            extract_text_from_file,
            create_embeddings,
            is_tabular_file,
            extract_schema_from_csv,
            extract_rows_from_csv,
        )


class TestChunkText:
    def test_empty_text(self):
        """Test chunking with empty text returns empty list"""
        result = chunk_text("")
        assert result == []

    def test_smaller_than_chunk_size(self):
        """Test chunking text smaller than chunk size"""
        text = "This is a short text"
        result = chunk_text(text, chunk_size=400)
        assert result == [text]

    def test_exact_chunk_size(self):
        """Test chunking text exactly chunk size"""
        text = "A" * 400
        result = chunk_text(text, chunk_size=400)
        assert result == [text]

    def test_multiple_chunks(self):
        """Test chunking text into multiple chunks"""
        text = "A" * 1000
        result = chunk_text(text, chunk_size=400)
        assert len(result) == 3
        assert result[0] == "A" * 400
        assert result[1] == "A" * 400
        assert result[2] == "A" * 200

    def test_with_overlap(self):
        """Test chunking text with overlap"""
        text = "A" * 1000
        result = chunk_text(text, chunk_size=400, overlap=100)
        assert len(result) == 4
        assert result[0] == "A" * 400
        assert result[1] == "A" * 400
        assert result[2] == "A" * 400
        # Last chunk might be shorter
        assert len(result[3]) <= 400


class TestExtractTextFromPdf:
    @patch("tempfile.NamedTemporaryFile")
    @patch("pypdf.PdfReader")
    @patch("os.path.exists")
    @patch("os.remove")
    @patch("builtins.open", new_callable=mock_open)
    def test_extract_text(
        self, mock_file_open, mock_remove, mock_exists, mock_pdf_reader, mock_temp_file
    ):
        """Test extracting text from PDF"""
        # Setup mocks
        mock_temp = MagicMock()
        mock_temp.name = "temp.pdf"
        mock_temp_file.return_value.__enter__.return_value = mock_temp

        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Page 1 content"
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Page 2 content"

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page1, mock_page2]
        mock_pdf_reader.return_value = mock_reader

        mock_exists.return_value = True

        # Call the function
        result = extract_text_from_pdf(b"fake pdf content")

        # Assertions
        assert result == "Page 1 content\n\nPage 2 content\n\n"
        mock_temp.write.assert_called_once_with(b"fake pdf content")
        mock_remove.assert_called_once_with("temp.pdf")


class TestExtractTextFromFile:
    @patch("common.text_processor.extract_text_from_pdf")
    def test_pdf_file(self, mock_extract_pdf):
        """Test extracting text from PDF file"""
        mock_extract_pdf.return_value = "PDF content"

        result = extract_text_from_file(
            b"fake pdf content", "application/pdf", "test.pdf"
        )

        mock_extract_pdf.assert_called_once_with(b"fake pdf content")
        assert result == "PDF content"

    def test_text_file(self):
        """Test extracting text from text file"""
        content = b"Text file content"
        mime_type = "text/plain"
        file_name = "test.txt"
        config = {"supported_mime_types": ["text/plain"]}

        result = extract_text_from_file(content, mime_type, file_name, config)

        assert result == "Text file content"

    def test_unsupported_file(self):
        """Test extracting text from unsupported file type"""
        content = b"Some content"
        mime_type = "application/octet-stream"
        file_name = "test.bin"

        result = extract_text_from_file(content, mime_type, file_name)

        assert result == "Some content"


# Global reference to the mocked OpenAI client
openai_client_mock = mock_client


class TestCreateEmbeddings:
    def test_empty_list(self):
        """Test creating embeddings with empty text list"""
        result = create_embeddings([])
        assert result == []

    @pytest.fixture
    def openai_client_mock(self):
        return MagicMock()

    def test_with_text(self, openai_client_mock):
        """Test creating embeddings"""
        # Patch the openai_client in text_processor
        with patch("common.text_processor.openai_client", openai_client_mock):
            # Setup mock response
            mock_response = MagicMock()
            mock_item1 = MagicMock()
            mock_item1.embedding = [0.1, 0.2, 0.3]
            mock_item2 = MagicMock()
            mock_item2.embedding = [0.4, 0.5, 0.6]
            mock_response.data = [mock_item1, mock_item2]

            openai_client_mock.embeddings.create.return_value = mock_response

            # Call the function
            result = create_embeddings(["Text 1", "Text 2"])

            # Assertions
            openai_client_mock.embeddings.create.assert_called_once_with(
                model=None,  # This matches the actual call when EMBEDDING_MODEL_CHOICE is not set
                input=["Text 1", "Text 2"],
            )
            assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]


class TestIsTabularFile:
    @pytest.mark.parametrize(
        "mime_type,expected",
        [
            ("text/csv", True),
            ("csv", True),
            ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", True),
            ("xlsx", True),
            ("application/vnd.google-apps.spreadsheet", True),
            ("application/pdf", False),
            ("text/plain", False),
        ],
    )
    def test_various_mime_types(self, mime_type, expected):
        """Test identifying various file types as tabular or not"""
        assert is_tabular_file(mime_type) == expected

    def test_with_custom_config(self):
        """Test identifying tabular file with custom config"""
        config = {"tabular_mime_types": ["custom/tabular"]}
        assert is_tabular_file("custom/tabular", config) == True
        assert is_tabular_file("text/csv", config) == False


class TestExtractSchemaFromCsv:
    def test_valid_csv(self):
        """Test extracting schema (column names) from CSV"""
        csv_content = b"Name,Age,Email\nJohn,30,john@example.com"

        result = extract_schema_from_csv(csv_content)

        assert result == ["Name", "Age", "Email"]

    @patch("csv.reader")
    def test_invalid_csv(self, mock_csv_reader, capfd):
        """Test extracting schema from invalid CSV"""
        # Make csv.reader raise an exception
        mock_csv_reader.side_effect = Exception("CSV parsing error")

        result = extract_schema_from_csv(b"\x80invalid")

        assert result == []
        # Check that error was printed
        captured = capfd.readouterr()
        assert "Error extracting schema from CSV" in captured.out


class TestExtractRowsFromCsv:
    def test_valid_csv(self):
        """Test extracting rows from CSV"""
        csv_content = (
            b"Name,Age,Email\nJohn,30,john@example.com\nJane,25,jane@example.com"
        )

        result = extract_rows_from_csv(csv_content)

        expected = [
            {"Name": "John", "Age": "30", "Email": "john@example.com"},
            {"Name": "Jane", "Age": "25", "Email": "jane@example.com"},
        ]
        assert result == expected

    @patch("csv.DictReader")
    def test_invalid_csv(self, mock_dict_reader, capfd):
        """Test extracting rows from invalid CSV"""
        # Make csv.DictReader raise an exception
        mock_dict_reader.side_effect = Exception("CSV parsing error")

        result = extract_rows_from_csv(b"\x80invalid")

        assert result == []
        # Check that error was printed
        captured = capfd.readouterr()
        assert "Error extracting rows from CSV" in captured.out
