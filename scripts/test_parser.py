"""Test script to verify markdown parser on actual BC Cancer articles."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.ingestion.markdown_parser import MarkdownParser


def main():
    """Test parser on actual articles."""
    parser = MarkdownParser()

    # Test on a few sample articles
    articles_dir = project_root / "scraped_data" / "articles" / "health-info" / "types-of-cancer"

    test_files = [
        articles_dir / "breast-cancer.md",
        articles_dir / "digestive-system" / "pancreas.md",
        articles_dir / "lung" / "lung.md",
    ]

    print("=" * 70)
    print("Testing Markdown Parser on BC Cancer Articles")
    print("=" * 70)
    print()

    for file_path in test_files:
        if not file_path.exists():
            print(f"⚠️  File not found: {file_path}")
            print()
            continue

        print(f"📄 Parsing: {file_path.name}")
        print("-" * 70)

        try:
            # Parse the article
            article = parser.parse_file(file_path)

            # Get statistics
            stats = parser.get_article_stats(article)

            # Display results
            print(f"✅ Successfully parsed!")
            print(f"   Title: {article.title}")
            print(f"   Article ID: {article.article_id}")
            print(f"   Cancer Type: {article.cancer_type}")
            print(f"   URL: {article.url}")
            print(f"   Breadcrumbs: {' > '.join(article.breadcrumbs)}")
            print(f"   Sections: {stats['sections_count']}")
            print(f"   Paragraphs: {stats['total_paragraphs']}")
            print(f"   Words: {stats['word_count']:,}")
            print(f"   Characters: {stats['char_count']:,}")
            print(f"   Avg paragraph length: {stats['avg_paragraph_length']:.1f} words")
            print()

            # Show first few sections
            if article.sections:
                print("   First 3 sections:")
                for i, section in enumerate(article.sections[:3], 1):
                    print(f"     {i}. {section.name} (Level {section.level}, {len(section.paragraphs)} paragraphs)")

            print()

            # Show a sample paragraph
            if article.sections and article.sections[0].paragraphs:
                sample_para = article.sections[0].paragraphs[0]
                if len(sample_para) > 150:
                    sample_para = sample_para[:150] + "..."
                print(f"   Sample paragraph:")
                print(f"   \"{sample_para}\"")
                print()

        except Exception as e:
            print(f"❌ Error parsing file: {e}")
            import traceback
            traceback.print_exc()
            print()

        print()

    # Test directory parsing
    print("=" * 70)
    print("Testing Directory Parsing")
    print("=" * 70)
    print()

    try:
        print(f"📁 Parsing all articles in: {articles_dir}")
        articles = parser.parse_directory(articles_dir)

        print(f"✅ Successfully parsed {len(articles)} articles")
        print()

        # Calculate total statistics
        total_paragraphs = sum(a.get_total_paragraph_count() for a in articles)
        total_sections = sum(len(a.sections) for a in articles)

        print(f"   Total articles: {len(articles)}")
        print(f"   Total sections: {total_sections}")
        print(f"   Total paragraphs: {total_paragraphs}")
        print(f"   Avg paragraphs per article: {total_paragraphs / len(articles):.1f}")
        print()

        # Show distribution of article sizes
        para_counts = [a.get_total_paragraph_count() for a in articles]
        print(f"   Smallest article: {min(para_counts)} paragraphs")
        print(f"   Largest article: {max(para_counts)} paragraphs")
        print()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print("=" * 70)
    print("Parser test complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
