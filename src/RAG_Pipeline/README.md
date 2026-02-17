# RAG Pipeline (Google Drive & Local Files)

This RAG (Retrieval Augmented Generation) pipeline processes files from either Google Drive or a local directory. It automatically extracts text content, generates embeddings, and stores this information in a Supabase database with PGVector support, enabling semantic search and retrieval for your applications.

## Features

- **Dual Data Source Support:**
    - Monitors Google Drive for file changes (creation, updates, deletion) in a specified folder or entire drive.
    - Monitors a local directory for file changes (creation, updates, deletion).
- **Versatile File Processing:** Processes various document types including PDFs, text documents, HTML, CSVs, and more (see Supported File Types).
- **Automated Text Extraction & Chunking:** Extracts text content and intelligently splits it into manageable chunks (default: 400 characters, configurable).
- **Embedding Generation:** Creates embeddings using OpenAI's embedding model (configurable via `LLM_API_KEY`).
- **Vector Storage:** Stores content chunks and their embeddings in a Supabase database with PGVector for efficient similarity search.
- **Automatic Sync:** Ensures the database reflects file deletions from the source.

## Requirements

- Python 3.11+
- Supabase account with a PGVector-enabled database.
- Tables created from the `sql/` files (alongside the `RAG_Pipeline` folder)
- OpenAI API key.
- **For Google Drive Pipeline:** Google Drive API credentials.

## Installation

1.  **Clone the repository** (if not already done).

2.  **Navigate to the RAG Pipeline directory:**
    ```bash
    cd RAG_Pipeline
    ```

3.  **Create and activate a virtual environment:**
    It's highly recommended to use a virtual environment to manage dependencies.
    ```bash
    # Create the virtual environment (e.g., named 'venv')
    python -m venv venv

    # Activate the virtual environment
    # On Windows (PowerShell/CMD):
    # venv\Scripts\activate
    # On macOS/Linux (bash/zsh):
    # source venv/bin/activate
    ```

4.  **Install dependencies:**
    With the virtual environment activated, install the required packages:
    ```bash
    pip install -r requirements.txt
    ```

5.  **Set up environment variables:**
    Create a `.env` file in the **project root directory** (i.e., one level above the `RAG_Pipeline` directory, so `../.env` from your current location if you are inside `RAG_Pipeline`). The scripts are configured to look for it there.
    ```env
    # ../.env
    EMBEDDING_MODEL_NAME=your_embedding_model_choice
    EMBEDDING_BASE_URL=your_provider_base_url
    EMBEDDING_API_KEY=your_provider_api_key
    SUPABASE_URL=your_supabase_url
    SUPABASE_SERVICE_KEY=your_supabase_service_key
    ```

6.  **For Google Drive Pipeline - Google Drive API Setup:**
    - Go to the [Google Cloud Console](https://console.cloud.google.com/).
    - Create a new project or select an existing one.
    - Enable the Google Drive API.
    - Create OAuth 2.0 credentials (Desktop application).
    - Download the credentials JSON file. By default, the pipeline expects this file to be named `credentials.json` and located in the `Google_Drive/` directory (relative to `RAG_Pipeline`, i.e., `RAG_Pipeline/Google_Drive/credentials.json`). You can specify a different path using the `--credentials` argument.
    - The first time you run the Google Drive pipeline, it will prompt you to authorize access via a web browser. A `token.json` file will be created in the `Google_Drive/` directory (or the path specified by `--token`) to store your authorization.

## Usage

Ensure your virtual environment is activated and you are in the `RAG_Pipeline` directory.

The pipeline can be run in two modes: for Google Drive or for Local Files.

### 1. Google Drive Pipeline

This mode watches a Google Drive folder (or your entire Drive) for changes.

**Command (run from the `RAG_Pipeline` directory):**
```bash
python Google_Drive/main.py [OPTIONS]
```

**Arguments:**
-   `--credentials FILE_PATH`: Path to Google Drive API credentials file.
    (Default: `Google_Drive/credentials.json`)
-   `--token FILE_PATH`: Path to Google Drive API token file.
    (Default: `Google_Drive/token.json`)
-   `--config FILE_PATH`: Path to the configuration JSON file for the Google Drive pipeline.
    (Default: `Google_Drive/config.json`)
-   `--interval SECONDS`: Interval in seconds between checks for changes.
    (Default: 60)
-   `--folder-id FOLDER_ID`: ID of the specific Google Drive folder to watch (and its subfolders). If not provided, it watches the entire Drive.
    (Default: None)

**Examples (run from the `RAG_Pipeline` directory):**
```bash
# Watch all of Google Drive with 30-second intervals, using default paths
python Google_Drive/main.py --interval 30

# Watch a specific Google Drive folder
python Google_Drive/main.py --folder-id "your_google_drive_folder_id"

# Use custom paths for credentials and config (paths relative to RAG_Pipeline)
python Google_Drive/main.py --credentials "./custom_creds/gdrive_creds.json" --config "./configs/drive_settings.json"
```

### 2. Local Files Pipeline

This mode watches a specified local directory for changes.

**Command (run from the `RAG_Pipeline` directory):**
```bash
python Local_Files/main.py [OPTIONS]
```

**Arguments:**
-   `--config FILE_PATH`: Path to the configuration JSON file for the Local Files pipeline.
    (Default: `Local_Files/config.json`)
-   `--directory DIR_PATH`: Path to the local directory to watch for files. This path can be absolute or relative to the `RAG_Pipeline` directory.
    (Default: None - **This argument is required**)
-   `--interval SECONDS`: Interval in seconds between checks for changes.
    (Default: 60)

**Examples (run from the `RAG_Pipeline` directory):**
```bash
# Watch the 'data/my_documents' directory (relative to RAG_Pipeline, e.g., RAG_Pipeline/data/my_documents)
python Local_Files/main.py --directory "data/my_documents"

# Watch a specific absolute local directory with a 120-second interval
python Local_Files/main.py --directory "/mnt/shared_data/project_files" --interval 120

# Use a custom config file (path relative to RAG_Pipeline)
python Local_Files/main.py --directory "./docs_to_process" --config "./configs/local_settings.json"
```

## Configuration Files (`config.json`)

Each pipeline (`Google_Drive` and `Local_Files`) has its own `config.json` file located within its respective subdirectory inside `RAG_Pipeline` (e.g., `RAG_Pipeline/Google_Drive/config.json`, `RAG_Pipeline/Local_Files/config.json`). When running scripts from within `RAG_Pipeline`, these paths become `Google_Drive/config.json` and `Local_Files/config.json` respectively. These files allow you to customize:
-   `supported_mime_types`: A list of MIME types the pipeline will attempt to process.
-   `text_processing`:
    -   `default_chunk_size`: The target size for text chunks.
    -   `default_chunk_overlap`: The overlap between text chunks.
-   Module-specific settings:
    -   For Google Drive: `export_mime_types` (how Google Workspace files are converted), `watch_folder_id` (can be overridden by CLI, default in `Google_Drive/config.json`), `last_check_time` (managed by the script).
    -   For Local Files: `watch_directory` (can be overridden by CLI, default in `Local_Files/config.json`), `last_check_time` (managed by the script).

## Database Schema

The pipeline uses a `documents` table in your Supabase database with the following (expected) columns:
-   `id` (UUID PRIMARY KEY or SERIAL PRIMARY KEY): Unique identifier for the chunk.
-   `content` (TEXT): The text content of the processed chunk.
-   `metadata` (JSONB): Contains information about the source file, such as `file_id` (for Google Drive), `file_path` (for local files), `file_name`, `source_type` ('google_drive' or 'local_file'), etc. *(Verify exact fields based on `common/db_handler.py`)*
-   `embedding` (VECTOR): The OpenAI embedding vector for the content chunk.

## How It Works

1.  **Initialization & Authentication:**
    -   **Google Drive:** Authenticates with the Google Drive API using provided/stored credentials and token.
    -   **Local Files:** Sets up a watcher for the specified local directory.
    -   Both connect to the Supabase database using environment variables (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`).
2.  **Periodic Monitoring:** The pipeline periodically checks the source (Google Drive or local directory) for new, updated, or deleted files based on the `interval` setting.
3.  **File Processing (for new/updated files):**
    -   The file is downloaded (from Google Drive) or read (from the local disk).
    -   Text content is extracted. For Google Workspace files, they are typically exported to a plain text or CSV format first, as defined in `Google_Drive/config.json`.
    -   The extracted text is split into smaller, manageable chunks based on the `text_processing` settings in the respective `config.json` file.
    -   OpenAI embeddings are generated for each text chunk using the model specified by `LLM_API_KEY` (and optionally `EMBEDDING_MODEL_NAME`).
    -   Any existing records for the file (if it was updated) are removed from the Supabase `documents` table to prevent duplicates.
    -   The new text chunks, their metadata, and embeddings are inserted into the `documents` table.
4.  **Deletion Handling (for deleted files):**
    -   When a file is detected as deleted from the source, all corresponding records (chunks and embeddings) for that file are removed from the Supabase `documents` table.

## Supported File Types

The pipeline supports a variety of file types. The exact list can be found and configured in the `supported_mime_types` section of the respective `config.json` files (e.g., `Google_Drive/config.json`, `Local_Files/config.json` when viewed from within the `RAG_Pipeline` directory).

Commonly supported types include:
-   PDF (`application/pdf`)
-   Plain Text (`text/plain`)
-   HTML (`text/html`)
-   CSV (`text/csv`)
-   Microsoft Excel (`application/vnd.ms-excel`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`)
-   Microsoft Word (`application/msword`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`) (More relevant for Local Files pipeline)
-   Google Docs, Sheets, Presentations (for Google Drive, converted as per `export_mime_types`)
-   Images (`image/png`, `image/jpg`, `image/jpeg`, `image/svg`) 
    *Note: Text extraction from images (OCR) depends on the capabilities of the underlying `common/text_processor.py`. Review its implementation for details on image handling.*
