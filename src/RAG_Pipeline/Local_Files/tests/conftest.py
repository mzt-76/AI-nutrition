import pytest
import os
import sys

# Add the parent directory to sys.path to import the modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


# Fixtures that can be used across multiple test files
@pytest.fixture
def sample_text_content():
    """Sample text content for testing"""
    return "This is sample text content for testing purposes."


@pytest.fixture
def sample_pdf_content():
    """Sample PDF content for testing (binary)"""
    # This is just a placeholder - not actual PDF content
    return b"%PDF-1.5\nSample PDF content for testing"


@pytest.fixture
def sample_csv_content():
    """Sample CSV content for testing"""
    return "header1,header2,header3\nvalue1,value2,value3\nvalue4,value5,value6"


@pytest.fixture
def tmp_test_dir(tmp_path):
    """Create a temporary test directory with some sample files"""
    # Create test directory
    test_dir = tmp_path / "test_data"
    test_dir.mkdir()

    # Create some sample files
    (test_dir / "sample.txt").write_text("This is a sample text file.")
    (test_dir / "sample.csv").write_text("a,b,c\n1,2,3")

    return test_dir
