from typing import List, Dict, Any, Optional
import os
import json
import traceback
from dotenv import load_dotenv
from supabase import create_client, Client
import base64
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from text_processor import (
    chunk_text,
    create_embeddings,
    is_tabular_file,
    extract_schema_from_csv,
    extract_rows_from_csv,
)

# Load environment variables from the project root .env file
# Get the path to the project root (4_Pydantic_AI_Agent directory)
project_root = Path(__file__).resolve().parent.parent.parent
dotenv_path = project_root / ".env"

# Force override of existing environment variables
load_dotenv(dotenv_path, override=True)

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)


def delete_document_by_file_id(file_id: str) -> None:
    """
    Delete all records related to a specific file ID (documents, document_rows, and document_metadata).

    Args:
        file_id: The Google Drive file ID
    """
    try:
        # Delete all documents with the specified file_id in metadata
        response = (
            supabase.table("documents")
            .delete()
            .eq("metadata->>file_id", file_id)
            .execute()
        )
        print(f"Deleted {len(response.data)} document chunks for file ID: {file_id}")

        # Delete all document_rows with the specified dataset_id
        try:
            rows_response = (
                supabase.table("document_rows")
                .delete()
                .eq("dataset_id", file_id)
                .execute()
            )
            print(
                f"Deleted {len(rows_response.data)} document rows for file ID: {file_id}"
            )
        except Exception as e:
            print(f"Error deleting document rows: {e}")

        # Delete the document_metadata record
        try:
            metadata_response = (
                supabase.table("document_metadata").delete().eq("id", file_id).execute()
            )
            print(f"Deleted metadata for file ID: {file_id}")
        except Exception as e:
            print(f"Error deleting document metadata: {e}")

    except Exception as e:
        print(f"Error deleting documents: {e}")


def insert_document_chunks(
    chunks: List[str],
    embeddings: List[List[float]],
    file_id: str,
    file_url: str,
    file_title: str,
    mime_type: str,
    file_contents: bytes | None = None,
) -> None:
    """
    Insert document chunks with their embeddings into the Supabase database.

    Args:
        chunks: List of text chunks
        embeddings: List of embedding vectors for each chunk
        file_id: The Google Drive file ID
        file_url: The URL to access the file
        file_title: The title of the file
        mime_type: The mime type of the file
        file_contents: Optional binary of the file to store as metadata
    """
    try:
        # Ensure we have the same number of chunks and embeddings
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks and embeddings must match")

        # Prepare the data for insertion
        data = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            file_bytes_str = (
                base64.b64encode(file_contents).decode("utf-8")
                if file_contents
                else None
            )
            data.append(
                {
                    "content": chunk,
                    "metadata": {
                        "file_id": file_id,
                        "file_url": file_url,
                        "file_title": file_title,
                        "mime_type": mime_type,
                        "chunk_index": i,
                        **({"file_contents": file_bytes_str} if file_bytes_str else {}),
                    },
                    "embedding": embedding,
                }
            )

        # Insert the data into the documents table
        for item in data:
            supabase.table("documents").insert(item).execute()
    except Exception as e:
        print(f"Error inserting/updating document chunks: {e}")


def insert_or_update_document_metadata(
    file_id: str, file_title: str, file_url: str, schema: Optional[List[str]] = None
) -> None:
    """
    Insert or update a record in the document_metadata table.

    Args:
        file_id: The Google Drive file ID (used as primary key)
        file_title: The title of the file
        file_url: The URL to access the file
        schema: Optional schema for tabular files (column names)
    """
    try:
        # Check if the record already exists
        response = (
            supabase.table("document_metadata").select("*").eq("id", file_id).execute()
        )

        # Prepare the data
        data = {"id": file_id, "title": file_title, "url": file_url}

        # Add schema if provided
        if schema:
            data["schema"] = json.dumps(schema)

        if response.data and len(response.data) > 0:
            # Update existing record
            supabase.table("document_metadata").update(data).eq("id", file_id).execute()
            print(f"Updated metadata for file '{file_title}' (ID: {file_id})")
        else:
            # Insert new record
            supabase.table("document_metadata").insert(data).execute()
            print(f"Inserted metadata for file '{file_title}' (ID: {file_id})")
    except Exception as e:
        print(f"Error inserting/updating document metadata: {e}")


def insert_document_rows(file_id: str, rows: List[Dict[str, Any]]) -> None:
    """
    Insert rows from a tabular file into the document_rows table.

    Args:
        file_id: The Google Drive file ID (references document_metadata.id)
        rows: List of row data as dictionaries
    """
    try:
        # First, delete any existing rows for this file
        supabase.table("document_rows").delete().eq("dataset_id", file_id).execute()
        print(f"Deleted existing rows for file ID: {file_id}")

        # Insert new rows
        for row in rows:
            supabase.table("document_rows").insert(
                {"dataset_id": file_id, "row_data": row}
            ).execute()
        print(f"Inserted {len(rows)} rows for file ID: {file_id}")
    except Exception as e:
        print(f"Error inserting document rows: {e}")


def process_file_for_rag(
    file_content: bytes,
    text: str,
    file_id: str,
    file_url: str,
    file_title: str,
    mime_type: str = None,
    config: Dict[str, Any] = None,
) -> None:
    """
    Process a file for the RAG pipeline - delete existing records and insert new ones.

    Args:
        file_content: The binary content of the file
        text: The text content extracted from the file
        file_id: The Google Drive file ID
        file_url: The URL to access the file
        file_title: The title of the file
        mime_type: Mime type of the file
        config: Configuration for things like the chunk size and overlap
    """
    try:
        # First, delete any existing records for this file
        delete_document_by_file_id(file_id)

        # Check if this is a tabular file
        is_tabular = False
        schema = None

        if mime_type:
            is_tabular = is_tabular_file(mime_type, config)

        if is_tabular:
            # Extract schema (column names) from CSV
            schema = extract_schema_from_csv(file_content)

        # First, insert or update document metadata (needed for foreign key constraint)
        insert_or_update_document_metadata(file_id, file_title, file_url, schema)

        # Then, if it's a tabular file, insert the rows
        if is_tabular:
            # Extract and insert rows for tabular files
            rows = extract_rows_from_csv(file_content)
            if rows:
                insert_document_rows(file_id, rows)

        # Get text processing settings from config
        text_processing = config.get("text_processing", {})
        chunk_size = text_processing.get("default_chunk_size", 400)
        chunk_overlap = text_processing.get("default_chunk_overlap", 0)

        # Chunk the text
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=chunk_overlap)
        if not chunks:
            print(f"No chunks were created for file '{file_name}' (Path: {file_path})")
            return

        # Create embeddings for the chunks
        embeddings = create_embeddings(chunks)

        # For images, don't chunk the image, just store the title for RAG and include the binary in the metadata
        if mime_type.startswith("image"):
            insert_document_chunks(
                chunks,
                embeddings,
                file_id,
                file_url,
                file_title,
                mime_type,
                file_content,
            )
            return True

        # Insert the chunks with their embeddings
        insert_document_chunks(
            chunks, embeddings, file_id, file_url, file_title, mime_type
        )

        return True
    except Exception as e:
        traceback.print_exc()
        print(f"Error processing file for RAG: {e}")
        return False
