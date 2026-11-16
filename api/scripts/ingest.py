"""Ingest the scraped corpus into a NEW Qdrant collection (local only).

The app reads through the alias in ``vector_db.collection_name`` (e.g.
``care-beacon-live``). This script never writes to that alias or to the
collection behind it: it builds a separate collection, which you check and then
switch the alias to with ``scripts/qdrant_alias.py``.

    python scripts/ingest.py --collection care-beacon-medical-v2 [--quantize]
    python scripts/qdrant_alias.py show
    python scripts/qdrant_alias.py point care-beacon-live care-beacon-medical-v2

``--target local`` builds into a local Qdrant (``make qdrant-local``) instead,
for when the cloud cluster has no disk for a second collection; copy it up
afterwards with ``scripts/qdrant_copy.py``.

Articles are processed in small batches. Point ids are a hash of the chunk id,
so upserts are idempotent: an interrupted run can be continued with
``--resume --start-batch N`` (N = the first batch that did not finish).
"""

import argparse
import gc
import sys
import time
from pathlib import Path
from typing import List, Tuple

# Add the api/ service root to path so `src.*` imports resolve.
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# scraped_data/ lives at the repository root, outside api/, so it stays out of
# the Vercel bundle.
repo_root = Path(__file__).resolve().parents[2]

from src.config_loader import get_config  # noqa: E402
from src.embeddings.chunking import DocumentChunker  # noqa: E402
from src.embeddings.embedding_generator import EmbeddingGenerator  # noqa: E402
from src.ingestion.markdown_parser import MedicalArticleParser  # noqa: E402
from src.storage.qdrant_admin import (  # noqa: E402
    TARGETS,
    UnsafeTargetError,
    alias_map,
    check_ingest_target,
    collection_counts,
    endpoint,
)
from src.storage.qdrant_db import QdrantVectorDatabase  # noqa: E402

# scraped_data/<dir>/articles -> source name stored on every chunk
SOURCES = {
    "bc-cancer": "BC Cancer",
    "canadian-cancer-society": "Canadian Cancer Society",
    "cleveland-clinic": "Cleveland Clinic",
}


def find_all_articles(base_path: Path, source_name: str) -> List[Tuple[Path, str]]:
    """Every article markdown file under base_path, in a stable order."""
    articles = [
        (md_file, source_name)
        for md_file in base_path.rglob("*.md")
        if md_file.name.lower() not in ["readme.md", "index.md"]
    ]
    articles.sort(key=lambda x: x[0])
    return articles


def process_batch(
    batch: List[Tuple[Path, str]],
    parser: MedicalArticleParser,
    chunker: DocumentChunker,
    generator: EmbeddingGenerator,
    db: QdrantVectorDatabase,
    chunk_batch_size: int,
) -> int:
    """Parse, chunk, embed and store one batch of articles. Returns chunks stored."""
    chunks = []
    for article_path, source_name in batch:
        try:
            article = parser.parse_file(article_path)
        except Exception as e:
            print(f"  ⚠️  Failed to parse {article_path}: {e}")
            continue
        article.source = source_name
        chunks.extend(chunker.chunk_article(article))

    if not chunks:
        return 0

    embedded = generator.embed_chunks(chunks, show_progress=False)
    db.add_chunks(embedded, batch_size=chunk_batch_size, show_progress=False)
    return len(embedded)


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--collection", required=True, help="New collection to build (never the served alias)")
    ap.add_argument("--target", choices=TARGETS, default="cloud", help="Qdrant to write to (local = make qdrant-local)")
    ap.add_argument("--quantize", action="store_true", help="Create the collection with int8 scalar quantization (~4x less RAM)")
    ap.add_argument("--reset", action="store_true", help="Delete and recreate --collection first if it has points")
    ap.add_argument("--resume", action="store_true", help="Write into a non-empty --collection (continue an interrupted run)")
    ap.add_argument("--start-batch", type=int, default=1, help="First batch to process (1-based), for --resume")
    ap.add_argument("--sources", nargs="+", choices=sorted(SOURCES), default=sorted(SOURCES), help="Source directories to ingest")
    ap.add_argument("--limit", type=int, default=None, help="Only ingest the first N articles (trial runs)")
    ap.add_argument("--yes", action="store_true", help="Don't ask for confirmation")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    config = get_config()
    article_batch_size = config.get("ingestion.article_batch_size", 10)
    chunk_batch_size = config.get("ingestion.chunk_batch_size", 25)
    serving_name = config.get("vector_db.collection_name")

    # Safety check before anything is created, written or deleted.
    url, api_key = endpoint(args.target)
    probe = QdrantVectorDatabase(url=url, api_key=api_key, collection_name=args.collection, create_if_missing=False)
    aliases = alias_map(probe.client)
    counts = collection_counts(probe.client)
    try:
        # A local Qdrant serves nothing, so it needs no served alias.
        check_ingest_target(args.collection, serving_name, aliases, counts, reset=args.reset,
                            resume=args.resume, require_serving=args.target == "cloud")
    except UnsafeTargetError as e:
        print(f"❌ {e}")
        return 2

    all_paths: List[Tuple[Path, str]] = []
    for source_dir in args.sources:
        articles_dir = repo_root / "scraped_data" / source_dir / "articles"
        if not articles_dir.exists():
            print(f"❌ Directory not found: {articles_dir}")
            return 1
        found = find_all_articles(articles_dir, SOURCES[source_dir])
        print(f"  {SOURCES[source_dir]}: {len(found):,} articles")
        all_paths.extend(found)
    if args.limit:
        all_paths = all_paths[: args.limit]
    total_batches = (len(all_paths) + article_batch_size - 1) // article_batch_size

    print()
    print(f"Target collection : {args.target} {args.collection} ({counts.get(args.collection, 0):,} points now)")
    if args.target == "cloud":
        print(f"App serves        : {serving_name} -> {aliases.get(serving_name, serving_name)} (untouched)")
    print(f"Articles          : {len(all_paths):,} in {total_batches:,} batches, starting at batch {args.start_batch}")
    print(f"Quantization      : {'int8' if args.quantize else 'none'} (applies only when creating)")
    if args.reset and counts.get(args.collection, 0):
        print(f"⚠️  --reset will DELETE the {counts[args.collection]:,} points in {args.collection}")
    if not args.yes and input("Proceed? [y/N] ").strip().lower() != "y":
        print("Aborted.")
        return 1

    db = QdrantVectorDatabase(url=url, api_key=api_key, collection_name=args.collection,
                              create_if_missing=True, quantize=args.quantize)
    if args.reset and counts.get(args.collection, 0):
        db.reset()

    parser = MedicalArticleParser()
    chunker = DocumentChunker()
    generator = EmbeddingGenerator()

    start = time.time()
    stored = 0
    for batch_num in range(args.start_batch, total_batches + 1):
        i = (batch_num - 1) * article_batch_size
        batch = all_paths[i : i + article_batch_size]
        try:
            stored += process_batch(batch, parser, chunker, generator, db, chunk_batch_size)
        except Exception as e:
            print(f"\n❌ Batch {batch_num} failed: {e}")
            print(f"   Continue with: --resume --start-batch {batch_num}")
            return 1
        if batch_num % 50 == 0 or batch_num == total_batches:
            elapsed = time.time() - start
            done = batch_num - args.start_batch + 1
            eta = elapsed / done * (total_batches - batch_num)
            print(f"  batch {batch_num:,}/{total_batches:,}  chunks {stored:,}  "
                  f"elapsed {elapsed / 60:.1f} min  eta {eta / 60:.1f} min", flush=True)
        gc.collect()

    stats = generator.get_embedding_stats()
    print()
    print(f"✅ Stored {stored:,} chunks; {args.collection} now holds {db.count():,} points")
    print(f"   Embedding tokens {stats['total_tokens_used']:,}, cost ${stats['total_cost']:.4f}")
    print(f"   Time {(time.time() - start) / 60:.1f} min")
    print()
    if args.target == "local":
        print("Next: copy it to the cloud (see scripts/qdrant_copy.py), then switch the alias.")
    else:
        print("Next: check it on a preview, then switch the alias:")
        print(f"   python scripts/qdrant_alias.py point {serving_name} {args.collection}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
