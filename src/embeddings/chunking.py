"""Document chunking for embedding generation."""

import re
from typing import List
from src.storage.models import Article, Chunk


class DocumentChunker:
    """Chunks articles into paragraph-level pieces for embedding."""

    def __init__(self, min_chunk_length: int = 20, max_chunk_length: int = 2000):
        """Initialize the chunker.

        Args:
            min_chunk_length: Minimum character length for a chunk (default: 20)
            max_chunk_length: Maximum character length for a chunk (default: 2000)
        """
        self.min_chunk_length = min_chunk_length
        self.max_chunk_length = max_chunk_length

    def chunk_article(self, article: Article) -> List[Chunk]:
        """Chunk an article into paragraph-level chunks.

        Args:
            article: Article object to chunk

        Returns:
            List of Chunk objects
        """
        chunks = []
        global_paragraph_index = 0

        for section in article.sections:
            for para_text in section.paragraphs:
                # Skip empty or too-short paragraphs
                if not para_text or len(para_text.strip()) < self.min_chunk_length:
                    continue

                # Split long paragraphs if needed
                if len(para_text) > self.max_chunk_length:
                    # Split into sentences and recombine
                    sub_chunks = self._split_long_paragraph(para_text)
                    for sub_idx, sub_text in enumerate(sub_chunks):
                        chunk = self._create_chunk(
                            article=article,
                            section_name=section.name,
                            paragraph_text=sub_text,
                            paragraph_index=global_paragraph_index,
                            sub_index=sub_idx if len(sub_chunks) > 1 else None
                        )
                        chunks.append(chunk)
                else:
                    # Create single chunk for paragraph
                    chunk = self._create_chunk(
                        article=article,
                        section_name=section.name,
                        paragraph_text=para_text,
                        paragraph_index=global_paragraph_index
                    )
                    chunks.append(chunk)

                global_paragraph_index += 1

        return chunks

    def _create_chunk(
        self,
        article: Article,
        section_name: str,
        paragraph_text: str,
        paragraph_index: int,
        sub_index: int = None
    ) -> Chunk:
        """Create a Chunk object with metadata.

        Args:
            article: Source article
            section_name: Name of section this paragraph belongs to
            paragraph_text: Text content of the chunk
            paragraph_index: Global paragraph index in article
            sub_index: Sub-index if paragraph was split (optional)

        Returns:
            Chunk object
        """
        # Generate chunk ID
        chunk_id = self._generate_chunk_id(
            article.article_id,
            section_name,
            paragraph_index,
            sub_index
        )

        # Create chunk
        chunk = Chunk(
            chunk_id=chunk_id,
            text=paragraph_text.strip(),
            article_id=article.article_id,
            article_title=article.title,
            url=article.url,
            breadcrumbs=article.breadcrumbs,
            cancer_type=article.cancer_type,
            source=article.source,
            date_scraped=article.date_scraped,
            section=section_name,
            paragraph_index=paragraph_index,
            total_paragraphs=article.get_total_paragraph_count()
        )

        return chunk

    def _generate_chunk_id(
        self,
        article_id: str,
        section_name: str,
        paragraph_index: int,
        sub_index: int = None
    ) -> str:
        """Generate a unique chunk ID.

        Format: article-id_section-slug_pXX or article-id_section-slug_pXX_sYY

        Args:
            article_id: Article identifier
            section_name: Section name
            paragraph_index: Paragraph index
            sub_index: Sub-paragraph index if split

        Returns:
            Unique chunk ID string
        """
        # Create section slug (lowercase, replace spaces with hyphens)
        section_slug = re.sub(r'[^\w\s-]', '', section_name.lower())
        section_slug = re.sub(r'[-\s]+', '-', section_slug).strip('-')
        section_slug = section_slug[:30]  # Limit length

        # Build chunk ID
        chunk_id = f"{article_id}_{section_slug}_p{paragraph_index:03d}"

        if sub_index is not None:
            chunk_id += f"_s{sub_index:02d}"

        return chunk_id

    def _split_long_paragraph(self, text: str) -> List[str]:
        """Split a long paragraph into smaller chunks.

        Splits on sentence boundaries to maintain readability.

        Args:
            text: Long paragraph text

        Returns:
            List of text chunks
        """
        # Split into sentences
        sentences = self._split_into_sentences(text)

        chunks = []
        current_chunk = []
        current_length = 0

        for sentence in sentences:
            sentence_length = len(sentence)

            # If adding this sentence would exceed max length, save current chunk
            if current_length + sentence_length > self.max_chunk_length and current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_length = sentence_length
            else:
                current_chunk.append(sentence)
                current_length += sentence_length

        # Add final chunk
        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences.

        Args:
            text: Text to split

        Returns:
            List of sentences
        """
        # Simple sentence splitter (split on . ! ?)
        # More sophisticated: could use nltk.sent_tokenize
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def chunk_articles(self, articles: List[Article]) -> List[Chunk]:
        """Chunk multiple articles.

        Args:
            articles: List of Article objects

        Returns:
            List of all chunks from all articles
        """
        all_chunks = []
        for article in articles:
            chunks = self.chunk_article(article)
            all_chunks.extend(chunks)
        return all_chunks

    def get_chunking_stats(self, chunks: List[Chunk]) -> dict:
        """Get statistics about chunks.

        Args:
            chunks: List of chunks

        Returns:
            Dictionary with statistics
        """
        if not chunks:
            return {
                'total_chunks': 0,
                'total_characters': 0,
                'total_words': 0,
                'avg_chunk_length': 0,
                'min_chunk_length': 0,
                'max_chunk_length': 0,
                'unique_articles': 0,
                'unique_sections': 0
            }

        chunk_lengths = [len(c.text) for c in chunks]
        word_counts = [len(c.text.split()) for c in chunks]
        unique_articles = len(set(c.article_id for c in chunks))
        unique_sections = len(set(c.section for c in chunks))

        return {
            'total_chunks': len(chunks),
            'total_characters': sum(chunk_lengths),
            'total_words': sum(word_counts),
            'avg_chunk_length': sum(chunk_lengths) / len(chunks),
            'avg_words_per_chunk': sum(word_counts) / len(chunks),
            'min_chunk_length': min(chunk_lengths),
            'max_chunk_length': max(chunk_lengths),
            'unique_articles': unique_articles,
            'unique_sections': unique_sections
        }
