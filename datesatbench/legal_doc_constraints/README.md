# DateSATBench's Legally Grounded Dataset Generator

The processing pipeline extracts temporal clauses from United States Code XML and converts them into the same constraint format used by the LLM-generated constraints.

## Processing Pipeline

The extraction process consists of four main steps:

### Step 1: Parse XML (`parse.py`)

Parses the fixed Title 26 XML file and produces **element-level** records (per section/subsection/paragraph/etc.) with hierarchy metadata.

```bash
# From repository root
python datesatbench/legal_doc_constraints/generator/parse.py
```

This always reads:
- Input: `datesatbench/legal_doc_constraints/raw_data/title26.xml`
- Output: `datesatbench/legal_doc_constraints/processed_data/parsed/parsed.jsonl`

The raw_data/title26.xml can be downloaded from https://uscode.house.gov/view.xhtml?path=/prelim@title26&edition=prelim

**Output:** `processed_data/parsed/parsed.jsonl` – one JSON object **per element** with:
- `id`: Unique identifier for the element
- `heading`: Section heading/title
- `identifier`: Full USLM identifier path
- `element_type`: One of `section` or `subsection`
- `raw_text`: Full element text before structural cleanup (for provenance/debugging)
- `text`: Normalized body text for the element (page headers/footers and editorial notes removed)

### Step 2: Filter Temporal Clauses (`filter.py`)

Identifies clauses containing temporal logic (dates, periods, deadlines).

```bash
python datesatbench/legal_doc_constraints/generator/detect.py \
    datesatbench/legal_doc_constraints/processed_data/parsed/parsed.jsonl \
    --output datesatbench/legal_doc_constraints/processed_data/filtered.jsonl
```

Please read details in code comments.

### Step 3: Random select

`random_select.py` can be used to randomly select filtered clauses to proceed to step 4.

### Step 4: Normalize to Constraints

Converts temporal clauses into DateSAT constraint format.

```bash
# Set API key first
export ANTHROPIC_API_KEY="your-key-here"  # or OPENAI_API_KEY

python datesatbench/legal_doc_constraints/generator/llm_extractor.py \
    --input datesatbench/legal_doc_constraints/processed_data/selected.jsonl \
    --output datesatbench/legal_doc_constraints/constraints/1.jsonl \
    --provider anthropic
```
