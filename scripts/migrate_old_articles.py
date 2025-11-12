"""Migrate articles from old location to new multi-source structure.

This script moves BC Cancer articles from:
  scraped_data/articles/
to:
  scraped_data/bc-cancer/articles/
"""

import argparse
import shutil
from pathlib import Path

def migrate_articles(skip_confirmation: bool = False):
    """Migrate old articles to new structure.

    Args:
        skip_confirmation: If True, skip the confirmation prompt
    """

    # Define paths
    old_location = Path("scraped_data/articles")
    new_location = Path("scraped_data/bc-cancer/articles")

    print("=" * 70)
    print("BC CANCER ARTICLES MIGRATION")
    print("=" * 70)
    print()

    # Check if old location exists
    if not old_location.exists():
        print(f"❌ Old location not found: {old_location}")
        print(f"   Nothing to migrate.")
        return

    # Count files in old location
    old_files = list(old_location.rglob("*.md"))
    old_files = [f for f in old_files if f.name.lower() not in ["readme.md", "index.md"]]

    if not old_files:
        print(f"✅ No articles found in old location: {old_location}")
        print(f"   Migration not needed.")
        return

    print(f"📂 Found {len(old_files)} articles in old location")
    print(f"   From: {old_location}")
    print(f"   To:   {new_location}")
    print()

    # Ask for confirmation unless skipped
    if not skip_confirmation:
        response = input("Do you want to proceed with migration? (yes/no): ").strip().lower()
        if response not in ["yes", "y"]:
            print("❌ Migration cancelled.")
            return

    print()
    print("🔄 Starting migration...")
    print()

    # Create new location if it doesn't exist
    new_location.mkdir(parents=True, exist_ok=True)

    # Migrate files
    migrated = 0
    skipped = 0

    for old_file in old_files:
        # Get relative path from old_location
        relative_path = old_file.relative_to(old_location)
        new_file = new_location / relative_path

        # Create parent directories
        new_file.parent.mkdir(parents=True, exist_ok=True)

        # Check if file already exists
        if new_file.exists():
            print(f"⏭️  Skipped (exists): {relative_path}")
            skipped += 1
        else:
            # Copy file (don't move yet, in case something goes wrong)
            shutil.copy2(old_file, new_file)
            print(f"✅ Migrated: {relative_path}")
            migrated += 1

    print()
    print("=" * 70)
    print("MIGRATION COMPLETE")
    print("=" * 70)
    print(f"✅ Migrated: {migrated} files")
    print(f"⏭️  Skipped:  {skipped} files (already exist)")
    print()

    if migrated > 0:
        print("📝 NEXT STEPS:")
        print()
        print("1. Verify the migration:")
        print(f"   ls -la {new_location}")
        print()
        print("2. Re-ingest the data locally:")
        print("   python scripts/ingest_all_articles_low_memory.py")
        print()
        print("3. OR force re-ingest on Render:")
        print("   - Set FORCE_REINGEST=true in Render environment")
        print("   - Trigger deployment")
        print("   - Set FORCE_REINGEST back to false")
        print()
        print("4. (Optional) After verifying, delete old location:")
        print(f"   rm -rf {old_location}")
        print()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate BC Cancer articles from old to new structure"
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt and proceed automatically"
    )
    args = parser.parse_args()

    migrate_articles(skip_confirmation=args.yes)
