"""
Database State Manager for RAG Pipeline

Handles persistence of pipeline state (last_check_time, known_files) in Supabase database
for both continuous and single-run execution modes.
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Union
from supabase import create_client, Client


class StateManager:
    """
    Manages pipeline state persistence in Supabase database.

    Supports storing runtime state like last_check_time and known_files
    while keeping configuration in source-controlled files.
    """

    def __init__(self, pipeline_id: str, pipeline_type: str):
        """
        Initialize the state manager.

        Args:
            pipeline_id: Unique identifier for this pipeline instance (from RAG_PIPELINE_ID)
            pipeline_type: Type of pipeline ('google_drive' or 'local_files')
        """
        self.pipeline_id = pipeline_id
        self.pipeline_type = pipeline_type

        # Initialize Supabase client
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_KEY')

        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables are required")

        self.supabase: Client = create_client(supabase_url, supabase_key)

        # Setup logging
        self.logger = logging.getLogger(__name__)

    def load_state(self) -> Dict[str, Any]:
        """
        Load pipeline state from database.

        Returns:
            Dictionary containing pipeline state:
            {
                'last_check_time': datetime or None,
                'known_files': dict,
                'exists': bool  # Whether record exists in database
            }
        """
        try:
            # Query the database for this pipeline
            response = self.supabase.table('rag_pipeline_state').select('*').eq('pipeline_id', self.pipeline_id).execute()

            if response.data and len(response.data) > 0:
                record = response.data[0]

                # Parse last_check_time
                last_check_time = None
                if record.get('last_check_time'):
                    try:
                        last_check_time = datetime.fromisoformat(record['last_check_time'].replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        self.logger.warning(f"Invalid last_check_time format in database: {record.get('last_check_time')}")

                return {
                    'last_check_time': last_check_time,
                    'known_files': record.get('known_files') or {},
                    'exists': True
                }
            else:
                # No record exists, return defaults
                return {
                    'last_check_time': None,
                    'known_files': {},
                    'exists': False
                }

        except Exception as e:
            self.logger.error(f"Error loading state from database: {e}")
            # Return defaults on error
            return {
                'last_check_time': None,
                'known_files': {},
                'exists': False
            }

    def save_state(self, last_check_time: Optional[datetime] = None,
                   known_files: Optional[Dict[str, str]] = None) -> bool:
        """
        Save pipeline state to database.

        Args:
            last_check_time: Last check timestamp (will be converted to UTC)
            known_files: Dictionary of file_id -> timestamp mappings

        Returns:
            True if save was successful, False otherwise
        """
        try:
            # Prepare the data to save
            data = {
                'pipeline_id': self.pipeline_id,
                'pipeline_type': self.pipeline_type,
                'last_run': datetime.now(timezone.utc).isoformat()
            }

            # Add last_check_time if provided
            if last_check_time is not None:
                # Ensure timezone-aware datetime
                if last_check_time.tzinfo is None:
                    last_check_time = last_check_time.replace(tzinfo=timezone.utc)
                data['last_check_time'] = last_check_time.isoformat()

            # Add known_files if provided
            if known_files is not None:
                data['known_files'] = known_files

            # Check if record exists
            state = self.load_state()

            if state['exists']:
                # Update existing record
                response = self.supabase.table('rag_pipeline_state').update(data).eq('pipeline_id', self.pipeline_id).execute()
            else:
                # Insert new record
                response = self.supabase.table('rag_pipeline_state').insert(data).execute()

            if response.data:
                self.logger.debug(f"Successfully saved state for pipeline {self.pipeline_id}")
                return True
            else:
                self.logger.error(f"Failed to save state: {response}")
                return False

        except Exception as e:
            self.logger.error(f"Error saving state to database: {e}")
            return False

    def update_known_files(self, known_files: Dict[str, str]) -> bool:
        """
        Update only the known_files field in the database.

        Args:
            known_files: Dictionary of file_id -> timestamp mappings

        Returns:
            True if update was successful, False otherwise
        """
        return self.save_state(known_files=known_files)

    def update_last_check_time(self, last_check_time: datetime) -> bool:
        """
        Update only the last_check_time field in the database.

        Args:
            last_check_time: Last check timestamp

        Returns:
            True if update was successful, False otherwise
        """
        return self.save_state(last_check_time=last_check_time)

    def get_pipeline_info(self) -> Dict[str, Any]:
        """
        Get basic pipeline information from database.

        Returns:
            Dictionary with pipeline metadata
        """
        try:
            response = self.supabase.table('rag_pipeline_state').select('pipeline_id, pipeline_type, created_at, last_run').eq('pipeline_id', self.pipeline_id).execute()

            if response.data and len(response.data) > 0:
                return response.data[0]
            else:
                return {
                    'pipeline_id': self.pipeline_id,
                    'pipeline_type': self.pipeline_type,
                    'created_at': None,
                    'last_run': None
                }

        except Exception as e:
            self.logger.error(f"Error getting pipeline info: {e}")
            return {
                'pipeline_id': self.pipeline_id,
                'pipeline_type': self.pipeline_type,
                'created_at': None,
                'last_run': None
            }

    def delete_pipeline_state(self) -> bool:
        """
        Delete pipeline state from database.

        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            response = self.supabase.table('rag_pipeline_state').delete().eq('pipeline_id', self.pipeline_id).execute()
            self.logger.info(f"Deleted state for pipeline {self.pipeline_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error deleting pipeline state: {e}")
            return False


def get_state_manager(pipeline_type: str) -> Optional[StateManager]:
    """
    Factory function to create a StateManager instance.

    Args:
        pipeline_type: Type of pipeline ('google_drive' or 'local_files')

    Returns:
        StateManager instance if RAG_PIPELINE_ID is set, None otherwise
    """
    pipeline_id = os.getenv('RAG_PIPELINE_ID')

    if not pipeline_id:
        # No pipeline ID set, use file-based state (backward compatibility)
        return None

    try:
        return StateManager(pipeline_id, pipeline_type)
    except Exception as e:
        logging.error(f"Failed to create StateManager: {e}")
        return None


# Utility functions for backward compatibility
def load_state_from_config(config_path: str) -> Dict[str, Any]:
    """
    Load state from traditional config.json file (fallback/backward compatibility).

    Args:
        config_path: Path to config.json file

    Returns:
        Dictionary with state information
    """
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)

        # Parse last_check_time from config
        last_check_time = None
        last_check_time_str = config.get('last_check_time', '1970-01-01T00:00:00.000Z')
        try:
            last_check_time = datetime.strptime(last_check_time_str, '%Y-%m-%dT%H:%M:%S.%fZ')
        except ValueError:
            last_check_time = datetime.strptime('1970-01-01T00:00:00.000Z', '%Y-%m-%dT%H:%M:%S.%fZ')

        return {
            'last_check_time': last_check_time,
            'known_files': {},  # File-based config doesn't store known_files
            'exists': True
        }
    except Exception:
        return {
            'last_check_time': datetime.strptime('1970-01-01T00:00:00.000Z', '%Y-%m-%dT%H:%M:%S.%fZ'),
            'known_files': {},
            'exists': False
        }


def save_state_to_config(config_path: str, last_check_time: datetime, config: Dict[str, Any]) -> bool:
    """
    Save state to traditional config.json file (fallback/backward compatibility).

    Args:
        config_path: Path to config.json file
        last_check_time: Last check timestamp
        config: Configuration dictionary to update

    Returns:
        True if save was successful, False otherwise
    """
    try:
        config['last_check_time'] = last_check_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)

        return True
    except Exception as e:
        logging.error(f"Error saving state to config: {e}")
        return False
