# Ragas-based RAG Evaluation

This directory contains tools for evaluating the Care-Beacon RAG system using the ragas framework.

## Files

- `evaluate_rag.py` - Main evaluation script using ragas metrics
- `generate_test_questions.py` - Generate test questions from database content
- `test_questions.json` - Test questions for evaluation
- `switch_prompts.sh` - Helper script to switch between production and evaluation prompts
- `results/` - Evaluation results and reports

## Quick Start

### 1. Switch to Evaluation Prompts

For accurate ragas metrics, use simplified prompts without medical disclaimers:

```bash
cd evaluation/ragas
./switch_prompts.sh eval
```

This will backup your production prompts and switch to evaluation prompts.

**Important:** Restart your API server after switching prompts!

### 2. Run Evaluation

Make sure your API server is running on localhost:8000, then:

```bash
python evaluate_rag.py
```

The evaluation will:
- Load test questions from `test_questions.json`
- Query your RAG API for each question
- Evaluate responses using ragas metrics:
  - **Faithfulness**: Factual accuracy vs retrieved context
  - **Answer Relevancy**: How well answer addresses the question
  - **Context Precision**: Relevance of retrieved chunks
  - **Context Recall**: Coverage of ground truth information
- Generate detailed results in `results/`

### 3. Switch Back to Production Prompts

After evaluation, restore your production prompts:

```bash
./switch_prompts.sh prod
```

**Remember to restart your API server!**

## Understanding Prompts

### Production Prompts (`config/prompts.yaml`)
- Comprehensive, well-cited answers
- Medical disclaimers and safety language
- Empathetic tone
- **Best for:** Real patient interactions
- **Ragas scores:** Lower (penalized for verbosity)

### Evaluation Prompts (`config/prompts_eval.yaml`)
- Concise, focused answers
- Minimal disclaimers
- Direct responses
- **Best for:** Accurate ragas evaluation metrics
- **Ragas scores:** Higher (rewards conciseness)

## Evaluation Metrics

| Metric | Range | What it Measures |
|--------|-------|------------------|
| **Faithfulness** | 0-1 | Are answers factually accurate based on retrieved context? |
| **Answer Relevancy** | 0-1 | Does the answer directly address the question? |
| **Context Precision** | 0-1 | Are the retrieved chunks relevant to the question? |
| **Context Recall** | 0-1 | Do retrieved chunks cover the ground truth answer? |

**Good scores:** 0.7+
**Acceptable:** 0.5-0.7
**Needs improvement:** <0.5

## Generating New Test Questions

To create test questions from your actual database content:

```bash
python generate_test_questions.py
```

This will:
1. Sample chunks from Cleveland Clinic and Canadian Cancer Society sources
2. Use GPT-4o-mini to generate 2-3 questions per chunk
3. Save to `test_questions_generated.json`
4. Display summary statistics

## Tips for Accurate Evaluation

1. **Always use evaluation prompts** when running ragas metrics
2. **Keep production prompts** for real patient interactions
3. **Restart API** after switching prompts
4. **Review failing questions** in detailed results CSV
5. **Focus on trends** rather than individual scores

## Example Workflow

```bash
# 1. Switch to evaluation mode
./switch_prompts.sh eval

# 2. Restart your API server (in another terminal)
# Stop current server, then restart with evaluation prompts loaded

# 3. Run evaluation
python evaluate_rag.py

# 4. Review results
cat results/evaluation_YYYYMMDD_HHMMSS_summary.txt

# 5. Switch back to production
./switch_prompts.sh prod

# 6. Restart API server again
```

## Troubleshooting

**Issue:** Evaluation shows 0% answer relevancy
**Solution:** Make sure you switched to evaluation prompts and restarted the API

**Issue:** API connection errors
**Solution:** Verify API is running on localhost:8000 with `curl http://localhost:8000/health`

**Issue:** Low context recall scores
**Solution:** Check if test questions match your database sources (Cleveland Clinic, Canadian Cancer Society, etc.)

**Issue:** `switch_prompts.sh` permission denied
**Solution:** Run `chmod +x switch_prompts.sh`

**Issue:** Low faithfulness/context recall with non-empty responses
**Solution:** Make sure evaluation uses `include_full_text=True` to send complete chunk text to ragas (not truncated excerpts)

**Issue:** Test questions about topics not in database
**Solution:** Regenerate test questions with improved prompt constraints, or filter out unanswerable questions manually

## Lessons Learned

### Truncated Contexts Break Evaluation (Nov 2024)
Initial evaluation showed 46% faithfulness with 98/102 questions having zero context recall. Investigation revealed the API was only sending 100-character truncated `text_excerpt` to ragas instead of full chunk text. Ragas correctly identified that answers contained claims not present in the truncated contexts.

**Fix:** Added `include_full_text` parameter throughout the pipeline:
- API models: Added optional `full_text` field
- Answer generator: Conditionally populate full text when requested
- Evaluation script: Request full text and use it for ragas

**Result:** Faithfulness jumped from 46% → 76% (+30 points!)

### Bad Test Questions Skew Metrics (Nov 2024)
"Screening" question type showed 32.8% answer relevancy despite perfect context recall (100%). Investigation revealed questions asked about "botulinum antitoxin" (botulism treatment) but database contained "Botox" (cosmetic/medical use of botulinum toxin). System correctly responded "sources don't mention this specific medication" - low relevancy was appropriate!

**Fix:**
1. Filtered out 3 unanswerable questions
2. Improved question generation prompt to prevent term substitution
3. Added constraints to only use information explicitly in source chunks

**Result:** Answer relevancy improved from 69.4% → 70.8%, crossing "good" threshold
