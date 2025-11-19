"""Generate test questions from actual database content.

This script samples content from Cleveland Clinic and Canadian Cancer Society
sources and generates test questions that match the actual content.
"""

import sys
import json
from pathlib import Path
from collections import defaultdict

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.storage.vector_db import create_vector_database
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from project root
load_dotenv(project_root / ".env")

# Initialize OpenAI client for question generation
client = OpenAI()


def sample_chunks_by_source(vector_db, source: str, n_samples: int = 100):
    """Sample chunks from a specific source.

    Args:
        vector_db: Vector database instance
        source: Source to filter by
        n_samples: Number of chunks to sample

    Returns:
        List of chunks from the specified source
    """
    # Get a large sample and filter by source
    all_chunks = vector_db.peek(limit=2000)
    source_chunks = [c for c in all_chunks if c.source == source]

    # Return up to n_samples
    return source_chunks[:n_samples]


def generate_questions_from_chunk(chunk, source: str):
    """Generate test questions from a chunk using GPT-4.

    Args:
        chunk: Chunk to generate questions from
        source: Source name

    Returns:
        List of generated questions
    """
    prompt = f"""Based on the following medical content, generate 2-3 high-quality test questions.

Source: {source}
Article: {chunk.article_title}
Section: {chunk.section}

Content:
{chunk.text}

Generate questions in this JSON format:
[
  {{
    "question": "The question text",
    "ground_truth": "The reference answer based on the content",
    "question_type": "basic_facts|symptoms|diagnosis|screening|treatment|comparison",
    "difficulty": "basic|intermediate|advanced"
  }}
]

CRITICAL REQUIREMENTS:
1. Questions must ONLY ask about information EXPLICITLY stated in the content above
2. Do NOT introduce new medical terms, medications, or conditions not mentioned in the content
3. Ground truth answers must be directly quotable/paraphrasable from the content
4. If the content mentions specific medical terms (like "Botox"), use those EXACT terms - don't substitute similar terms (like "botulinum antitoxin")
5. Questions should be natural sounding (as a patient would ask)
6. Questions should be diverse in type (symptoms, diagnosis, treatment, etc.)

Return ONLY the JSON array, no other text."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a medical education expert creating test questions for a RAG system evaluation."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=800
        )

        # Parse the JSON response
        content = response.choices[0].message.content.strip()
        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:].strip()

        questions = json.loads(content)

        # Add metadata
        for q in questions:
            q["expected_source"] = source
            q["source_article"] = chunk.article_title
            q["source_section"] = chunk.section

        return questions

    except Exception as e:
        print(f"Error generating questions: {e}")
        return []


def main():
    """Generate test questions from database content."""

    print("=" * 70)
    print("GENERATE TEST QUESTIONS FROM DATABASE CONTENT")
    print("=" * 70)
    print()

    # Create vector database
    print("Connecting to vector database...")
    vector_db = create_vector_database()
    print()

    # Sample chunks from each source
    sources_to_sample = {
        "Cleveland Clinic": 50,
        "Canadian Cancer Society": 50
    }

    all_questions = []

    for source, n_chunks in sources_to_sample.items():
        print(f"Sampling {n_chunks} chunks from {source}...")
        chunks = sample_chunks_by_source(vector_db, source, n_chunks)
        print(f"Found {len(chunks)} chunks from {source}")
        print()

        # Generate questions from a subset of chunks
        # (to avoid generating too many questions)
        chunks_to_use = chunks[:15]  # Use 15 chunks per source

        print(f"Generating questions from {len(chunks_to_use)} chunks...")
        for i, chunk in enumerate(chunks_to_use, 1):
            print(f"  Processing chunk {i}/{len(chunks_to_use)}: {chunk.article_title[:50]}...")
            questions = generate_questions_from_chunk(chunk, source)

            # Add IDs
            for q in questions:
                q_id = f"{source.replace(' ', '_').upper()}_{i:03d}_{q['question_type'].upper()}"
                q["id"] = q_id

            all_questions.extend(questions)

            # Rate limiting
            import time
            time.sleep(0.5)

        print(f"Generated {len([q for q in all_questions if q['expected_source'] == source])} questions from {source}")
        print()

    # Save questions
    output_file = Path(__file__).parent / "test_questions_generated.json"
    with open(output_file, "w") as f:
        json.dump(all_questions, f, indent=2)

    print("=" * 70)
    print(f"✅ Generated {len(all_questions)} test questions")
    print(f"Saved to: {output_file}")
    print("=" * 70)
    print()

    # Show summary
    by_source = defaultdict(int)
    by_type = defaultdict(int)

    for q in all_questions:
        by_source[q["expected_source"]] += 1
        by_type[q["question_type"]] += 1

    print("By Source:")
    for source, count in by_source.items():
        print(f"  {source}: {count} questions")
    print()

    print("By Type:")
    for q_type, count in by_type.items():
        print(f"  {q_type}: {count} questions")
    print()

    print("To use these questions for evaluation:")
    print(f"  cp {output_file} test_questions.json")
    print()


if __name__ == "__main__":
    main()
