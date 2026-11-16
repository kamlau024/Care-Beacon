"""Copy a Qdrant collection between the cloud cluster and a local Qdrant.

The free-tier cluster has no disk for a second full collection, so a re-ingest
is built locally and copied up (docs/INGESTION_CONFIGURATION.md):

    make qdrant-local                                   # local Qdrant in Docker
    python scripts/qdrant_copy.py --from cloud --to local care-beacon-medical care-beacon-medical-backup
    python scripts/ingest.py --target local --collection care-beacon-medical-v2
    # ...delete the cloud collection to free its disk, then:
    python scripts/qdrant_copy.py --from local --to cloud care-beacon-medical-v2 --quantize --float16 --workers 6
    python scripts/qdrant_alias.py point care-beacon-live care-beacon-medical-v2

Point ids, vectors and payloads are copied as they are, so no embeddings are
recomputed. A new target is created with HNSW indexing off and small
segments, and indexing is switched on once every point is written, so the
upload and the index build don't compete for the cluster's little spare disk.

A failed single-worker copy prints ``--resume-from <offset>``; a failed
``--workers`` copy is rerun with ``--resume`` (it rewrites every point, which
is harmless). The target must be a new (or partly copied) collection that no
alias points at.
"""

import argparse
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.qdrant_admin import (  # noqa: E402
    TARGETS,
    UnsafeTargetError,
    alias_map,
    check_copy_target,
    collection_counts,
    copy_points,
    endpoint,
    partition_offsets,
)
from src.storage.qdrant_db import QdrantVectorDatabase  # noqa: E402


def connect(target: str, collection: str, **kwargs) -> QdrantVectorDatabase:
    url, api_key = endpoint(target)
    return QdrantVectorDatabase(url=url, api_key=api_key, collection_name=collection, **kwargs)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="Collection (or alias) to read")
    ap.add_argument("dest", nargs="?", help="Collection to write (default: same name)")
    ap.add_argument("--from", dest="src", choices=TARGETS, required=True)
    ap.add_argument("--to", dest="dst", choices=TARGETS, required=True)
    ap.add_argument("--quantize", action="store_true", help="Create the target with int8 quantization and on-disk vectors")
    ap.add_argument("--float16", action="store_true", help="Create the target with float16 vectors (half the disk)")
    ap.add_argument("--workers", type=int, default=1, help="Parallel copiers over disjoint id ranges")
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--resume-from", default=None, help="Scroll offset printed by a failed single-worker copy")
    ap.add_argument("--resume", action="store_true", help="Allow a partly copied target and copy everything again")
    ap.add_argument("--yes", action="store_true", help="Don't ask for confirmation")
    args = ap.parse_args(argv)
    dest_name = args.dest or args.source
    if args.src == args.dst and dest_name == args.source:
        print("❌ Source and target are the same collection.")
        return 2

    src = connect(args.src, args.source, create_if_missing=False)
    src_counts = collection_counts(src.client)
    src_aliases = alias_map(src.client)
    src_collection = src_aliases.get(args.source, args.source)
    if src_collection not in src_counts:
        print(f"❌ {args.source!r} does not exist on {args.src}.")
        return 2
    total = src_counts[src_collection]

    probe = connect(args.dst, dest_name, create_if_missing=False)
    dst_counts = collection_counts(probe.client)
    try:
        check_copy_target(dest_name, alias_map(probe.client), dst_counts,
                          resume=args.resume or args.resume_from is not None)
    except UnsafeTargetError as e:
        print(f"❌ {e}")
        return 2

    print(f"From : {args.src} {args.source}" + (f" -> {src_collection}" if src_collection != args.source else "")
          + f" ({total:,} points)")
    print(f"To   : {args.dst} {dest_name} ({dst_counts.get(dest_name, 0):,} points now"
          + (", int8 quantized" if args.quantize else "") + (", float16" if args.float16 else "")
          + f", {args.workers} worker(s))")
    if args.resume_from:
        print(f"Resuming from offset {args.resume_from}")
    if not args.yes and input("Proceed? [y/N] ").strip().lower() != "y":
        print("Aborted.")
        return 1

    dst = connect(args.dst, dest_name, create_if_missing=True, quantize=args.quantize,
                  float16=args.float16, defer_indexing=True)
    start = time.time()
    lock = threading.Lock()
    done = {}  # worker -> points copied
    state = {"next": args.resume_from, "last_print": 0}

    def progress(worker: int, copied: int, next_offset) -> None:
        with lock:
            done[worker] = copied
            if args.workers == 1:
                state["next"] = next_offset
            total_done = sum(done.values())
            if total_done - state["last_print"] >= 10_000:
                state["last_print"] = total_done
                rate = total_done / max(time.time() - start, 1e-6)
                left = max(total - total_done, 0) / rate if rate else 0
                print(f"  {total_done:,}/{total:,} copied  {rate:,.0f}/s  eta {left / 60:.1f} min", flush=True)

    def run(worker: int, offset, stop) -> None:
        # One client per worker: each holds its own HTTP connection.
        source = connect(args.src, src_collection).client if args.workers > 1 else src.client
        dest = connect(args.dst, dest_name).client if args.workers > 1 else dst.client
        copy_points(source, src_collection, dest, dest_name, batch_size=args.batch_size, offset=offset,
                    stop=stop, on_batch=lambda c, o: progress(worker, c, o))

    ranges = (partition_offsets(src.client, src_collection, args.workers) if args.workers > 1
              else [(args.resume_from, None)])
    try:
        with ThreadPoolExecutor(max_workers=len(ranges)) as pool:
            for future in [pool.submit(run, i, a, b) for i, (a, b) in enumerate(ranges)]:
                future.result()
    except Exception as e:
        print(f"\n❌ Copy failed: {e}")
        if args.workers == 1 and state["next"] is not None:
            print(f"   Continue with: --resume-from {state['next']}")
        elif args.workers > 1:
            print("   Rerun the same command with --resume.")
        return 1

    dst.enable_indexing()
    print("Indexing switched on; the cluster builds the HNSW index in the background.")

    final = dst.count()
    print(f"\n{dest_name} on {args.dst}: {final:,} points (source {total:,}), "
          f"{(time.time() - start) / 60:.1f} min")
    if final != total:
        print("❌ Point counts differ.")
        return 3
    print("✅ Counts match.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
