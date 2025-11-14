"""API endpoints for downloading pre-built vector database from remote storage."""

import os
import json
import shutil
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import urllib.request
import urllib.error

from fastapi import HTTPException

# Paths
VECTOR_DB_PATH = Path("data/vector_db")
MANIFEST_FILENAME = "vector_db/vector_db_manifest.json"  # Inside vector_db folder


class VectorDBDownloader:
    """Handle downloading vector database from remote storage."""

    def __init__(self, base_url: Optional[str] = None):
        """Initialize downloader.

        Args:
            base_url: Base URL for remote storage (e.g., https://storage.example.com/data/)
                     If None, reads from VECTOR_DB_REMOTE_URL environment variable
        """
        self.base_url = base_url or os.getenv("VECTOR_DB_REMOTE_URL")
        if not self.base_url:
            raise ValueError("VECTOR_DB_REMOTE_URL not configured")

        # Ensure base URL ends with /
        if not self.base_url.endswith('/'):
            self.base_url += '/'

        self.manifest_url = f"{self.base_url}{MANIFEST_FILENAME}"
        self.backup_path: Optional[Path] = None
        self.downloaded_files = []

    async def download_file(self, url: str, destination: Path) -> bool:
        """Download a single file from URL.

        Args:
            url: URL to download from
            destination: Local file path

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create parent directories
            destination.parent.mkdir(parents=True, exist_ok=True)

            # Download file
            def _download():
                with urllib.request.urlopen(url) as response:
                    with open(destination, 'wb') as f:
                        f.write(response.read())

            # Run in thread pool to avoid blocking
            await asyncio.to_thread(_download)

            self.downloaded_files.append(destination)
            return True

        except Exception as e:
            print(f"❌ Failed to download {url}: {e}")
            return False

    async def fetch_manifest(self) -> Dict[str, Any]:
        """Fetch and parse the manifest file.

        Returns:
            Manifest dictionary

        Raises:
            Exception if manifest cannot be fetched or parsed
        """
        try:
            def _fetch():
                with urllib.request.urlopen(self.manifest_url) as response:
                    return json.loads(response.read().decode('utf-8'))

            manifest = await asyncio.to_thread(_fetch)
            return manifest

        except urllib.error.URLError as e:
            raise Exception(f"Failed to fetch manifest from {self.manifest_url}: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse manifest JSON: {e}")

    def backup_existing_database(self) -> Optional[Path]:
        """Backup existing vector database by renaming.

        Returns:
            Path to backup directory, or None if no database exists
        """
        if not VECTOR_DB_PATH.exists():
            print("No existing database to backup")
            return None

        # Create backup directory name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = VECTOR_DB_PATH.parent / f"vector_db_backup_{timestamp}"

        print(f"📦 Backing up existing database to: {backup_path}")

        try:
            shutil.move(str(VECTOR_DB_PATH), str(backup_path))
            print(f"✅ Backup created: {backup_path}")
            self.backup_path = backup_path
            return backup_path

        except Exception as e:
            print(f"❌ Backup failed: {e}")
            raise

    def restore_backup(self):
        """Restore database from backup if download failed."""
        if not self.backup_path or not self.backup_path.exists():
            print("No backup to restore")
            return

        print(f"🔄 Restoring backup from: {self.backup_path}")

        try:
            # Remove partial download
            if VECTOR_DB_PATH.exists():
                shutil.rmtree(VECTOR_DB_PATH)

            # Restore backup
            shutil.move(str(self.backup_path), str(VECTOR_DB_PATH))
            print("✅ Backup restored successfully")

        except Exception as e:
            print(f"❌ Failed to restore backup: {e}")
            raise

    def cleanup_old_backups(self, keep_count: int = 2):
        """Remove old backup directories, keeping only the most recent ones.

        Args:
            keep_count: Number of backups to keep
        """
        backup_pattern = "vector_db_backup_*"
        backups = sorted(
            VECTOR_DB_PATH.parent.glob(backup_pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        # Remove old backups
        for backup in backups[keep_count:]:
            print(f"🗑️  Removing old backup: {backup}")
            try:
                shutil.rmtree(backup)
            except Exception as e:
                print(f"   ⚠️  Failed to remove: {e}")

    async def download_database(self, progress_callback=None) -> Dict[str, Any]:
        """Download complete vector database from remote storage.

        Args:
            progress_callback: Optional async function to call with progress updates
                              Signature: async def callback(current: int, total: int, message: str)

        Returns:
            Dictionary with download statistics

        Raises:
            Exception if download fails
        """
        stats = {
            "started_at": datetime.now().isoformat(),
            "total_files": 0,
            "downloaded_files": 0,
            "failed_files": 0,
            "total_size": 0,
            "backup_created": None,
            "success": False
        }

        try:
            # Step 1: Fetch manifest
            if progress_callback:
                await progress_callback(0, 100, "Fetching manifest...")

            manifest = await self.fetch_manifest()
            stats["total_files"] = manifest["total_files"]
            stats["total_size"] = manifest["total_size"]

            if progress_callback:
                await progress_callback(5, 100, f"Found {manifest['total_files']} files to download")

            # Step 2: Backup existing database
            if progress_callback:
                await progress_callback(10, 100, "Backing up existing database...")

            backup_path = self.backup_existing_database()
            stats["backup_created"] = str(backup_path) if backup_path else None

            # Step 3: Download files
            files = manifest["files"]
            for i, file_info in enumerate(files):
                file_path = file_info["path"]
                file_url = f"{self.base_url}vector_db/{file_path}"
                destination = VECTOR_DB_PATH / file_path

                # Calculate progress (10% for setup, 90% for downloads)
                progress = int(10 + (i / len(files)) * 90)

                if progress_callback:
                    await progress_callback(
                        progress,
                        100,
                        f"Downloading {i + 1}/{len(files)}: {file_path}"
                    )

                success = await self.download_file(file_url, destination)

                if success:
                    stats["downloaded_files"] += 1
                else:
                    stats["failed_files"] += 1

            # Step 4: Verify download
            if stats["failed_files"] > 0:
                raise Exception(f"Failed to download {stats['failed_files']} files")

            # Success!
            stats["success"] = True
            stats["completed_at"] = datetime.now().isoformat()

            if progress_callback:
                await progress_callback(100, 100, "✅ Database download complete!")

            # Cleanup old backups
            self.cleanup_old_backups(keep_count=2)

            return stats

        except Exception as e:
            # Download failed - restore backup
            print(f"\n❌ Download failed: {e}")

            if progress_callback:
                await progress_callback(0, 100, f"Error: {str(e)}. Restoring backup...")

            self.restore_backup()
            stats["success"] = False
            stats["error"] = str(e)
            stats["completed_at"] = datetime.now().isoformat()

            raise Exception(f"Vector database download failed: {e}")


async def download_vector_database_from_remote(base_url: Optional[str] = None) -> Dict[str, Any]:
    """Download vector database from remote storage.

    Args:
        base_url: Base URL for remote storage (optional, defaults to env var)

    Returns:
        Download statistics

    Raises:
        HTTPException if download fails
    """
    try:
        downloader = VectorDBDownloader(base_url)
        stats = await downloader.download_database()
        return stats

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download vector database: {str(e)}"
        )
