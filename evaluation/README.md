# Care-Beacon RAG Evaluation Framework

This directory contains the evaluation framework for assessing the quality of the Care-Beacon RAG system using the [ragas](https://github.com/explodinggradients/ragas) evaluation library.

## Overview

The evaluation framework measures RAG system performance across four key metrics:

1. **Faithfulness**: How factually accurate is the answer based on the retrieved context?
2. **Answer Relevancy**: How relevant is the answer to the question asked?
3. **Context Precision**: How relevant are the retrieved contexts to answering the question?
4. **Context Recall**: How well do the retrieved contexts cover the information in the ground truth answer?

## Files

- `test_questions.json` - Test dataset with 36 questions across 3 cancer types (breast, lung, prostate)
- `evaluate_rag.py` - Main evaluation script
- `test_evaluation_sample.py` - Quick test script with 2 sample questions
- `results/` - Directory for evaluation results (CSV and summary reports)

## Test Dataset Structure

The test dataset contains:
- **36 questions total**
- **3 cancer types**: Breast (12), Lung (12), Prostate (12)
- **5 question types**: basic_facts, symptoms, diagnosis, screening, comparison
- **3 difficulty levels**: basic, intermediate, advanced

Each question includes:
- Question text
- Ground truth answer (reference answer from BC Cancer)
- Metadata (cancer type, question type, difficulty, expected source)

## Prerequisites

1. **Install dependencies** (already done if you've set up the project):
   ```bash
   pip install ragas datasets langchain langchain-openai langchain-community
   ```

2. **Set up OpenAI API key** (required for ragas evaluation):

   Create a `.env` file in the `evaluation/` directory:
   ```bash
   cd evaluation
   cp .env.example .env
   # Then edit .env and add your OpenAI API key
   ```

   Your `.env` file should look like:
   ```
   OPENAI_API_KEY=sk-...your-key-here...
   ```

   **Note**: The `.env` file is gitignored to keep your API key secure.

3. **Ensure Care-Beacon API is running**:
   ```bash
   docker-compose ps api
   # Should show status as "Up" and "healthy"
   ```

## Usage

### Quick Test (2 Sample Questions)

Run a quick test with just 2 questions to verify everything is working:

```bash
python evaluation/test_evaluation_sample.py
```

This will:
- Create a sample test file with 2 questions
- Query the RAG API
- Run ragas evaluation
- Save results to `evaluation/results/test_sample_results.csv`

**Expected runtime**: 1-2 minutes

### Full Evaluation (36 Questions)

Run the full evaluation on all 36 test questions:

```bash
python evaluation/evaluate_rag.py
```

**Expected runtime**: 5-10 minutes (depending on API response times and ragas processing)

The script will:
1. Load all 36 test questions
2. Query the Care-Beacon API for each question (with 0.5s delay between requests)
3. Evaluate responses using ragas metrics
4. Generate detailed results CSV and summary report

### Custom Options

You can customize the evaluation run:

```bash
# Use different API URL
python evaluation/evaluate_rag.py --api-url http://your-api:8000

# Specify custom output file
python evaluation/evaluate_rag.py --output evaluation/results/my_results.csv

# Use specific test file
python evaluation/evaluate_rag.py --test-file evaluation/my_test_questions.json
```

## Output Files

After running evaluation, you'll get:

1. **Results CSV** (`evaluation_YYYYMMDD_HHMMSS.csv`):
   - Per-question metrics (faithfulness, answer_relevancy, context_precision, context_recall)
   - Question metadata (cancer type, question type, difficulty)
   - Full questions, answers, and contexts

2. **Summary Report** (`evaluation_YYYYMMDD_HHMMSS_summary.txt`):
   - Overall metric averages
   - Breakdown by cancer type
   - Breakdown by question type
   - Number of successful/failed evaluations

## Interpreting Results

### Metric Scores (0.0 to 1.0)

- **0.9 - 1.0**: Excellent performance
- **0.7 - 0.9**: Good performance
- **0.5 - 0.7**: Fair performance (room for improvement)
- **< 0.5**: Poor performance (significant issues)

### What to Look For

1. **Faithfulness < 0.7**: Answer may be hallucinating or not grounded in sources
2. **Answer Relevancy < 0.7**: Answer may not be addressing the question properly
3. **Context Precision < 0.7**: Retrieval is pulling in too many irrelevant chunks
4. **Context Recall < 0.7**: Retrieval is missing important information from sources

## Troubleshooting

### "OPENAI_API_KEY environment variable not set"

Create a `.env` file in the `evaluation/` directory:
```bash
cd evaluation
cp .env.example .env
# Edit .env and add your API key: OPENAI_API_KEY=sk-...
```

Alternatively, you can export it in your shell:
```bash
export OPENAI_API_KEY='your-key-here'
```

### "Error querying API"

Check that the Care-Beacon API is running:
```bash
docker-compose ps api
docker-compose logs api  # Check for errors
```

### "Failed queries" in output

- Check API logs for errors: `docker-compose logs api`
- Verify questions are well-formed in test_questions.json
- Check if the vector database has the necessary source data

### Dependency errors

Reinstall dependencies:
```bash
pip install --upgrade ragas datasets langchain langchain-openai langchain-community
```

## Cost Estimation

The ragas evaluation uses OpenAI API (GPT-4o-mini for evaluation):

- **Sample test (2 questions)**: ~$0.01
- **Full evaluation (36 questions)**: ~$0.15-$0.20

The evaluation queries your Care-Beacon API, which has its own costs based on your LLM model (GPT-4o-mini, Claude, etc.).

## Next Steps

After running evaluation:

1. **Review Results**: Check CSV and summary report
2. **Identify Issues**: Look for low-scoring metrics
3. **Iterate**:
   - Improve retrieval (adjust similarity thresholds, re-ranking)
   - Improve prompts (refine system prompts for better answers)
   - Expand test coverage (add more questions for weak areas)
4. **Re-evaluate**: Run evaluation again after changes to measure improvement

## Adding More Test Questions

To expand the test dataset:

1. Open `test_questions.json`
2. Add new questions following the existing format:
   ```json
   {
     "id": "BC_[CANCER]_[TYPE]_NNN",
     "question": "Your question here?",
     "ground_truth": "Reference answer from source...",
     "cancer_type": "breast|lung|prostate|...",
     "question_type": "basic_facts|symptoms|diagnosis|screening|comparison",
     "difficulty": "basic|intermediate|advanced",
     "expected_source": "BC Cancer"
   }
   ```
3. Draft ground truth answers from your source content
4. Re-run evaluation to include new questions

## References

- [Ragas Documentation](https://docs.ragas.io/)
- [Ragas Metrics Explained](https://docs.ragas.io/en/latest/concepts/metrics/index.html)
- [LangChain Documentation](https://python.langchain.com/)

## Langfuse experiments (LLM-as-judge)

`evaluation/langfuse/` holds the dataset-driven experiment runner. Judges
(`judges.py`) run in our own code with `gpt-4o-mini` at temperature 0 and post their
scores to Langfuse; `datasets.py` uploads datasets idempotently by item id.

Required environment variables: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`,
`LANGFUSE_HOST` (or `LANGFUSE_BASE_URL`) and `OPENAI_API_KEY`.

Search baseline (78 questions from `ragas/test_questions.json`, grounded pass rate and
median `/ask` latency), run from the repo root:

```bash
/opt/anaconda3/envs/care-beacon/bin/python -m evaluation.langfuse.run_experiment \
  --dataset search-baseline \
  --base-url https://care-beacon-health.vercel.app \
  --run-name search-baseline-$(date +%F)
```

Record the run name, Langfuse run URL, item count, grounded pass rate and median
latency in `evaluation/results/<date>-search-baseline.md`.

Judge unit tests (OpenAI mocked, no network):
`/opt/anaconda3/envs/care-beacon/bin/python -m pytest evaluation/langfuse/test_judges.py -q`

### Chat follow-up and safety evals (Phase 1 gate)

`followups` (25 multi-turn threads, last turn depends on earlier turns) and `safety`
(19 threads of 2, 3 or 5 turns whose last turn asks for personal medical advice; the
five-turn threads drift from general information in turns 1-3 to the user's own situation
in turn 4 and a personal decision or diagnosis in turn 5) drive `POST /api/v1/chat`
with a fresh owner key per item. `safety-control` sends only each safety item's final turn
as a fresh single-turn thread, scored the same way, so you can compare the multi-turn and
single-turn `refusal_referral` pass rates (a lower multi-turn rate means drift weakens
refusals). Datasets live in `evaluation/langfuse/datasets/`.
Follow-ups are scored `followup_resolved` + `grounded`; safety is scored
`refusal_referral`, and every item must score 1. First-token and total turn times are
recorded as `first_token_s` and `turn_total_s`. A 429, an `error` frame, or a stream
without `done` fails the item and makes the run INCOMPLETE (exit code 1).

Needs `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` (or
`LANGFUSE_BASE_URL`) and `OPENAI_API_KEY` locally. The target must be a preview deploy of
the branch with its own chat environment (Redis, Qdrant, OpenAI keys) and a daily cap high
enough for roughly 150 turns (all three datasets). Preview deployments behind Vercel Deployment Protection need
a bypass; adjust `--base-url` accordingly.

```bash
BASE_URL=https://<branch-preview>.vercel.app
/opt/anaconda3/envs/care-beacon/bin/python -m evaluation.langfuse.run_experiment \
  --dataset followups --base-url "$BASE_URL" --run-name followups-$(date +%F)
/opt/anaconda3/envs/care-beacon/bin/python -m evaluation.langfuse.run_experiment \
  --dataset safety --base-url "$BASE_URL" --run-name safety-$(date +%F)
/opt/anaconda3/envs/care-beacon/bin/python -m evaluation.langfuse.run_experiment \
  --dataset safety-control --base-url "$BASE_URL" --run-name safety-control-$(date +%F)
```

Unit tests (HTTP and judges mocked): `/opt/anaconda3/envs/care-beacon/bin/python -m pytest evaluation/langfuse/ -q`
