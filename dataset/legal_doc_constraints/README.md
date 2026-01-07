# Legal Document Date Constraint Extraction

This directory contains scripts and data for extracting realistic date period operations constraints from legal document (United States Code, Title 26) for use with DateSMT.

## Overview

The processing pipeline extracts temporal clauses from United States Code XML and converts them into the same constraint format used by the LLM-generated constraints.

## Directory Structure

```
dataset/legal_doc_constraints/
├── raw_data/
│   └── title26.xml                  # Original Title 26 XML file (USLM format)
├── generator/
│   ├── parse.py                     # Parse XML into structured JSONL (sentence-level)
│   ├── detect.py                    # Detect temporal clauses
│   ├── normalize.py                 # Normalize to DateSMT format
│   └── run_tests.py                 # Test extracted constraints
├── processed_data/
│   ├── parsed/
│   │   └── sections.jsonl           # Parsed sentence-level records (from parse.py)
│   ├── candidates.jsonl             # Temporal candidates (from detect.py)
│   ├── constraints.jsonl            # Normalized constraints (from normalize.py)
│   └── results/                     # Test results (from run_tests.py)
└── README.md                        # This file
```

## Processing Pipeline

The extraction process consists of four main steps:

### Step 1: Parse XML (`parse.py`)

Parses the fixed Title 26 XML file and produces **element-level** records (per section/subsection/paragraph/etc.) with hierarchy metadata.

```bash
# From repository root
python dataset/legal_doc_constraints/generator/parse.py
```

This always reads:
- Input: `dataset/legal_doc_constraints/raw_data/title26.xml`
- Output: `dataset/legal_doc_constraints/processed_data/parsed/sections.jsonl`

**Output:** `processed_data/parsed/sections.jsonl` – one JSON object **per element** with:
- `id`: Unique identifier for the element
- `section_id`: Human-readable section id, e.g., `"26 USC § 6501"`
- `hierarchy`: Object describing `title`, `subtitle`, `chapter`, `subchapter`, `part`, `subpart`, `section`
- `subsection_path`: Subsection path string, e.g., `"(a)(1)(A)"`
- `heading`: Section heading/title
- `element_type`: One of `section`, `subsection`, `paragraph`, `subparagraph`, `clause`
- `raw_text`: Full element text before structural cleanup (for provenance/debugging)
- `text`: Normalized body text for the element (page headers/footers and editorial notes removed)
- `cross_refs`: List of cross references to other Title 26 provisions (if any), each with parsed target title/section/path

### Step 2: Detect Temporal Clauses (`detect.py`)

Identifies clauses containing temporal logic (dates, periods, deadlines).

```bash
python dataset/legal_doc_constraints/generator/detect.py \
    dataset/legal_doc_constraints/processed_data/parsed/sections.jsonl \
    --output dataset/legal_doc_constraints/processed_data/candidates.jsonl
```

**Output:** `processed_data/candidates.jsonl` - Subset of parsed sections that contain temporal patterns:
- All fields from Step 1
- `temporal_hit`: `true`
- `temporal_metadata`: Matched patterns and spans

**Detection Criteria:**
- Period keywords: year(s), month(s), day(s), period, week(s), quarter(s)
- Temporal relations: within, not later than, after, before, on or before, etc.
- Tax anchors: taxable year, filing date, due date, assessment, etc.
- Effective/applicability cues: effective on/after, for taxable years beginning after, etc.
- Date patterns: "15th day of the 4th month", date literals (YYYY-MM-DD, MM/DD/YYYY)

**Exclusions:**
- Clauses mentioning time-of-day (hours, minutes, seconds)
- Time zone references (DST, standard time)

### Step 4: Normalize to Constraints

Converts temporal clauses into DateSMT constraint format. **Three approaches available:**

#### Option A: LLM-Based Normalization (Recommended)

Uses LLM to understand context and extract meaningful constraints. More reliable and handles complexity.

```bash
# Set API key first
export ANTHROPIC_API_KEY="your-key-here"  # or OPENAI_API_KEY

python dataset/legal_doc_constraints/generator/normalize_llm.py \
    dataset/legal_doc_constraints/processed_data/candidates.jsonl \
    --output dataset/legal_doc_constraints/processed_data/constraints_llm.jsonl \
    --provider anthropic
```

**Advantages:**
- ✅ Understands context and semantics
- ✅ Handles complex expressions and conditional logic
- ✅ Generates meaningful variable names
- ✅ Can combine related constraints
- ✅ Better accuracy

**Options:**
- `--api-key`: API key (or set environment variable)
- `--model`: Specific model name
- `--provider`: `openai`, `anthropic`, or `auto`
- `--max-clauses`: Limit number of clauses to process (for testing)
- `--max-text-length`: Maximum text length per clause (default: 50000 chars). Longer text will be truncated to avoid context window limits.
- `--skip-errors`: Continue on errors

**Output:** Automatically generates both compact and pretty JSONL files (e.g., `constraints_llm.jsonl` and `constraints_llm_pretty.jsonl`)

#### Option C: Hybrid Normalization (Cost-Effective)

Combines rule-based and LLM approaches: uses rule-based for simple cases, LLM only for complex ones.

```bash
# Hybrid: rule-based for simple, LLM for complex
export ANTHROPIC_API_KEY="your-key-here"
python dataset/legal_doc_constraints/generator/normalize_hybrid.py \
    dataset/legal_doc_constraints/processed_data/candidates.jsonl \
    --output dataset/legal_doc_constraints/processed_data/constraints_hybrid.jsonl
```

**Advantages:**
- ✅ Significant cost savings (60-80% reduction in LLM calls)
- ✅ Better quality than rule-based alone
- ✅ Handles complex cases with LLM
- ✅ Can run without API key (rule-based only)

**Options:**
- `--api-key`: API key (optional - uses rule-based only if not provided)
- `--provider`: `openai`, `anthropic`, or `auto`
- `--use-llm-for-simple`: Use LLM even for simple cases (for comparison)
- `--max-clauses`: Limit number of clauses to process

**Output:** Automatically generates both compact and pretty JSONL files (e.g., `constraints_hybrid.jsonl` and `constraints_hybrid_pretty.jsonl`)

#### Option B: Rule-Based Normalization (Fast but Limited)

Uses regex pattern matching. Faster but less reliable.

```bash
python dataset/legal_doc_constraints/generator/normalize.py \
    dataset/legal_doc_constraints/processed_data/candidates.jsonl \
    --output dataset/legal_doc_constraints/processed_data/constraints.jsonl \
    --format jsonl
```

**Limitations:**
- ❌ No context understanding
- ❌ Misses cross-section relationships
- ❌ May generate meaningless constraints
- ❌ Cannot handle complex expressions

**Output:** Automatically generates both compact and pretty JSONL files (e.g., `constraints.jsonl` and `constraints_pretty.jsonl`)

**See `generator/ANALYSIS.md` for detailed comparison.**

**Cost Considerations:**
Processing all 35,326 candidates will incur API costs. Estimated costs (as of 2024):
- **Anthropic Claude 3.5 Sonnet**: ~$1,450
- **OpenAI GPT-4 Turbo**: ~$3,435
- **OpenAI GPT-3.5 Turbo**: ~$172 (cheaper, but lower quality)

**Cost-Saving Strategies:**

1. **Filter candidates first** (recommended):
   ```bash
   # Filter to high-quality candidates only
   python dataset/law/generator/filter_candidates.py \
       dataset/law/processed_data/candidates.jsonl \
       --min-score 0.5 \
       --max-candidates 5000 \
       --prioritize-sections 6511 6501 6072

   # Then process filtered candidates
   python dataset/law/generator/normalize_llm.py \
       dataset/law/processed_data/candidates_filtered.jsonl
   ```
   This can reduce costs by 70-90% while keeping the best candidates.

2. **Use hybrid approach** (rule-based + LLM):
   ```bash
   # Uses rule-based for simple cases, LLM only for complex ones
   python dataset/law/generator/normalize_hybrid.py \
       dataset/law/processed_data/candidates.jsonl \
       --api-key $ANTHROPIC_API_KEY
   ```
   Typically reduces LLM calls by 60-80%, saving significant costs.

3. **Start small**: Test with `--max-clauses 100` first
4. **Use cheaper models**: GPT-3.5 Turbo is ~8x cheaper than Claude 3.5
5. **Process in batches**: Use `--max-clauses` to control costs incrementally

**Output:**
- `processed_data/constraints.jsonl` - Compact JSONL format (one JSON object per line, for programmatic use)
- `processed_data/constraints_pretty.jsonl` - Pretty JSONL format (formatted with indentation, for human reading)

Both files are automatically generated. The pretty version is easier to read in text editors.

Constraints in DateSMT format:
```json
{
  "id": "26usc-6511-a-1-abc123",
  "description": "Claim for credit or refund must be filed within 3 years...",
  "constraints": [
    "x >= anchor_date",
    "x <= anchor_date + Period(3, 0, 0)"
  ],
  "coverage_tags": ["year_vs_days", "tax_law"],
  "provenance": {
    "usc_ref": {"title": 26, "section": 6511, "path": "(a)"},
    "original_text": "...",
    "heading": "Limitations on allowance of credits and refunds"
  }
}
```

**Output Format Options:**
- `--format jsonl`: One constraint per line (default, recommended for large datasets)
- `--format json`: Single JSON array (easier to read, but slower for large files)

**Normalization Patterns:**
- "within X years/months/days" → `x >= anchor AND x <= anchor + Period(...)`
- "not later than X period after Y" → `x <= anchor + Period(...)`
- "for taxable years beginning after YYYY-MM-DD" → `x >= Date(YYYY, MM, DD)`
- Date literals → `x >= Date(...)` or `x < Date(...)`

### Step 4: Test Constraints (`run_tests.py`)

Tests extracted constraints with DateSMT methods.

```bash
# Test all constraints with all methods
python dataset/law/run_tests.py \
    dataset/law/processed_data/constraints.jsonl

# Test with specific methods only
python dataset/law/run_tests.py \
    dataset/law/processed_data/constraints.jsonl \
    --methods baseline_bitvector enumeration

# Test with custom timeout and output directory
python dataset/law/run_tests.py \
    dataset/law/processed_data/constraints.jsonl \
    --output-dir dataset/law/processed_data/results \
    --timeout 300000 \
    --no-analysis
```

**Output:** Results directory containing:
- `{approach}_{implementation}_{timestamp}.json`: Results for each approach
- `smt2/`: SMT-LIB files for each constraint
- `checked_summary.json`: Analysis summary (if `--analysis` enabled)

**Command-Line Arguments:**
- `constraints_file`: Path to constraints JSON/JSONL file
- `--output-dir`: Output directory (default: `dataset/law/processed_data/results`)
- `--timeout`: Timeout in milliseconds (default: 600000 = 10 minutes)
- `--methods`: Select specific methods (see examples above)
- `--analysis`: Enable analysis (default: True)
- `--no-analysis`: Skip analysis

## Complete Workflow Example

```bash
# From repository root

# Step 1: Parse XML into sentence-level units
python dataset/legal_doc_constraints/generator/parse.py

# Step 2: Detect temporal clauses
python dataset/legal_doc_constraints/generator/detect.py \
    dataset/legal_doc_constraints/processed_data/parsed/sections.jsonl \
    --output dataset/legal_doc_constraints/processed_data/candidates.jsonl

# Step 3: Filter candidates (optional, but recommended to reduce costs)
python dataset/legal_doc_constraints/generator/filter_candidates.py \
    dataset/legal_doc_constraints/processed_data/candidates.jsonl \
    --min-score 0.5 \
    --max-candidates 5000

# Step 4: Normalize to constraints
# Option A: LLM-based (best quality, but expensive)
python dataset/law/generator/normalize_llm.py \
    dataset/law/processed_data/candidates_filtered.jsonl

# Option B: Hybrid (cost-effective, recommended)
python dataset/law/generator/normalize_hybrid.py \
    dataset/law/processed_data/candidates_filtered.jsonl

# Option C: Rule-based (free, but lower quality)
python dataset/law/generator/normalize.py \
    dataset/law/processed_data/candidates_filtered.jsonl

# Step 5: Test constraints
python dataset/law/generator/run_tests.py \
    dataset/law/processed_data/constraints.jsonl \
    --output-dir dataset/law/processed_data/results
```

## Quick Start

To run the complete pipeline in one go:

```bash
# From repository root

# 1. Parse and extract
python dataset/law/generator/parse.py dataset/law/raw_data/usc26.xml
python dataset/law/generator/detect.py dataset/law/processed_data/parsed/sections.jsonl

# 2. Filter candidates to reduce costs (recommended)
python dataset/law/generator/filter_candidates.py \
    dataset/law/processed_data/candidates.jsonl \
    --min-score 0.5 \
    --max-candidates 1000

# 3a. Option A: Hybrid normalization (recommended - cost-effective)
export ANTHROPIC_API_KEY="your-key-here"
python dataset/legal_doc_constraints/generator/normalize_hybrid.py \
    dataset/legal_doc_constraints/processed_data/candidates_filtered.jsonl \
    --max-clauses 100

# 3b. Option B: LLM-based only (best quality, but expensive)
# python dataset/legal_doc_constraints/generator/normalize_llm.py \
#     dataset/legal_doc_constraints/processed_data/candidates_filtered.jsonl \
#     --max-clauses 100

# 3c. Option C: Rule-based only (free, but less reliable)
# python dataset/legal_doc_constraints/generator/normalize.py \
#     dataset/legal_doc_constraints/processed_data/candidates_filtered.jsonl

# 4. Test constraints
python dataset/legal_doc_constraints/generator/run_tests.py \
    dataset/legal_doc_constraints/processed_data/constraints_hybrid.jsonl \
    --methods enumeration baseline_bitvector
```

## Constraint Format

Extracted constraints follow the same format as LLM-generated constraints:

```json
{
  "id": "unique-constraint-id",
  "description": "Human-readable description",
  "constraints": [
    "x >= Date(2020, 1, 1)",
    "x <= Date(2020, 12, 31)",
    "y == x + Period(0, 3, 0)"
  ],
  "coverage_tags": ["tax_law", "year_vs_days"],
  "provenance": {
    "usc_ref": {"title": 26, "section": 6511, "path": "(a)"},
    "original_text": "Original text from Title 26",
    "heading": "Section heading"
  }
}
```

**Constraint String Format:**
- Variables: `x`, `y`, `z`, etc.
- Dates: `Date(year, month, day)`
- Periods: `Period(years, months, days)`
- Operations: `+`, `-`, `==`, `!=`, `>=`, `<=`, `>`, `<`
- Expressions: `(x + Period(0, 1, 0))`, `y - x`, etc.

## Coverage Tags

Extracted constraints may include:
- `tax_law`: General tax law constraint
- `year_vs_days`: Year vs day period comparisons
- `month_vs_days`: Month vs day period comparisons
- `multi_period`: Multiple period operations
- `leap_year`: Leap year edge cases (if detected)

## Validation

The `run_tests.py` script uses the same validation framework as the LLM constraints:
- Tests with multiple approaches: baseline, epoch_days, hybrid, alpha_beta, alpha_beta_table
- Both int and bitvector implementations
- Enumeration baseline for ground truth
- Automatic validation using `dataset/utils/validation.py`

## Notes

1. **Normalization Approach**:
   - **LLM-based (`normalize_llm.py`)**: Recommended for production. Understands context, handles complexity, generates meaningful constraints. Requires API key.
   - **Rule-based (`normalize.py`)**: Fast but limited. Good for quick testing or simple patterns. See `generator/ANALYSIS.md` for detailed comparison.

2. **Cross-Section Relationships**: Legal constraints often span multiple sections/paragraphs. The current pipeline processes each clause independently. For production use, consider:
   - Using LLM with context from related sections
   - Post-processing to merge related constraints
   - Manual review of complex cases

3. **Symbolic Anchors**: Some constraints reference symbolic events (e.g., "filing_date", "close_of_taxable_year").
   - LLM-based approach: Uses meaningful variable names that can be instantiated
   - Rule-based approach: Uses concrete base dates (e.g., `Date(2020, 1, 1)`) as placeholders

4. **Constraint Quality**: Not all extracted constraints will be valid or useful. The testing phase helps identify which constraints are well-formed and solvable.

5. **Performance & Cost**:
   - Processing the full Title 26 XML (244K+ lines) may take several minutes
   - **Without filtering**: LLM normalization of all 35,326 candidates costs ~$172-$3,435
   - **With filtering** (recommended): Filter to top 1,500-5,000 candidates → costs ~$8-$150 (95%+ savings)
   - **Hybrid approach**: Use rule-based for simple cases → typically 60-80% cost reduction
   - Very long clauses (>50k chars) are automatically truncated to avoid context window limits

   **Example cost savings:**
   - Filter to 1,578 high-quality candidates: **$164-$3,281 saved** (95.5% reduction)
   - Hybrid approach on filtered candidates: Additional 60-80% savings on remaining LLM calls
   - **Total potential savings: 95-98%** compared to processing all candidates with LLM

6. **Reproducibility**: The scripts record metadata (edition, download date) for reproducibility. Keep the original XML file unchanged.

## Cost Optimization Summary

**Problem**: Processing all 35,326 candidates with LLM costs $172-$3,435.

**Solution**: Use a two-step approach:

1. **Filter first** (reduces candidates by 70-95%):
   ```bash
   python dataset/law/generator/filter_candidates.py \
       dataset/law/processed_data/candidates.jsonl \
       --min-score 0.5 \
       --max-candidates 5000
   ```
   **Result**: ~1,500-5,000 high-quality candidates → **$8-$150 cost** (95% savings)

2. **Use hybrid approach** (reduces LLM calls by 60-80%):
   ```bash
   python dataset/law/generator/normalize_hybrid.py \
       dataset/law/processed_data/candidates_filtered.jsonl
   ```
   **Result**: Rule-based handles simple cases, LLM only for complex → **Additional 60-80% savings**

**Total savings**: **95-98% cost reduction** while maintaining quality on the most important constraints.

## Troubleshooting

**Issue: "No constraints generated"**
- Check that `detect.py` found temporal candidates
- Review normalization patterns in `normalize.py`
- Some clauses may be too complex for automatic extraction

**Issue: "Constraints fail validation"**
- Some extracted constraints may reference symbolic anchors (e.g., "filing_date") that need to be instantiated
- Check constraint syntax matches DateSMT format
- Review `checked_summary.json` for detailed error messages

**Issue: "Processing is slow"**
- The XML file is large (244K+ lines). Consider:
  - Processing specific sections only
  - Using `--format jsonl` for faster I/O
  - Running detection/normalization in parallel batches

## Future Improvements

- [ ] Support for more complex temporal patterns (e.g., "15th day of the 4th month following")
- [ ] Better handling of symbolic anchors (instantiate with concrete dates)
- [ ] LLM-assisted normalization for ambiguous cases
- [ ] Coverage analysis and quality metrics
- [ ] Integration with constraint validation pipeline
