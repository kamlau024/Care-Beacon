"""Report chunk-quality problems across the local corpus, without embedding anything.

Parses and chunks every article under scraped_data/<source>/articles and counts:
  * lead-in only chunks: text ends with ":" (a list intro cut off from its list)
  * chunks still holding markdown links: text contains "](http"
  * chunks still holding raw URLs: text contains "http"

Run it before a re-ingest to confirm the parser and chunker produce what you
expect: `cd api && python scripts/check_chunks.py`.
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.embeddings.chunking import DocumentChunker  # noqa: E402
from src.ingestion.markdown_parser import MedicalArticleParser  # noqa: E402

SCRAPED = Path(__file__).resolve().parents[2] / "scraped_data"


def main() -> None:
    parser = MedicalArticleParser()
    chunker = DocumentChunker()
    totals: Counter = Counter()
    per_source: dict = {}

    for path in sorted(SCRAPED.glob("*/articles/**/*.md")):
        source = path.relative_to(SCRAPED).parts[0]
        try:
            article = parser.parse_file(path)
        except Exception:
            totals["parse_errors"] += 1
            continue
        counts = per_source.setdefault(source, Counter())
        for chunk in chunker.chunk_article(article):
            text = chunk.text.strip()
            for key, hit in (
                ("chunks", True),
                ("lead_in_only", text.endswith(":")),
                ("markdown_links", "](http" in text),
                ("raw_urls", "http" in text),
            ):
                if hit:
                    counts[key] += 1
                    totals[key] += 1

    def row(name: str, c: Counter) -> str:
        n = c["chunks"] or 1
        return (
            f"{name:<26}{c['chunks']:>9,}  lead-in only {c['lead_in_only']:>7,} ({c['lead_in_only'] / n:5.1%})"
            f"  md links {c['markdown_links']:>7,}  urls {c['raw_urls']:>7,}"
        )

    for source, counts in sorted(per_source.items()):
        print(row(source, counts))
    print(row("TOTAL", totals))
    if totals["parse_errors"]:
        print(f"parse errors: {totals['parse_errors']}")


if __name__ == "__main__":
    main()
