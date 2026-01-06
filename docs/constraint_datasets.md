## Constraint Datasets in DATE-SMT

This document summarizes how the two main constraint datasets are generated:

- LLM-generated synthetic constraints (`dataset/llm_constraints`)
- Legal-document–extracted constraints (`dataset/legal_doc_constraints`)

---

## 1. LLM Constraint Dataset (`dataset/llm_constraints`)

### 1.1 Generation

For each tag, 20 constraints are generated.
  (valid tags: `year_vs_days`, `month_vs_days`, `symbolic_date_vars`, `property_access`, `logical_operators`).
How many string constraints each object contains (default: 5–10).

Internally, `ConstraintGenerator.generate_constraints()`:

- Builds a natural-language **system prompt** (`SYSTEM_PROMPT`) that describes:
  - Allowed DateSMT syntax (Date/Period constructors, operators, logical connectives).
  - Valid date range: **1900‑03‑01 ≤ Date ≤ 2100‑02‑28**.
  - Content diversity and coverage tags.
  - Variable-count and “avoid trivial constraints” rules.
  - Output schema: each object has `description`, `declarations`, `constraints`, `coverage_tags`.
- Builds a **task-specific prompt** describing:
  - How many objects to generate.
  - Allowed coverage tags (if `--tags` was given).
  - Target constraints-per-object range.
- Calls a provider-agnostic `LLMClient` (`dataset/llm.py`) with:
  - The fixed `SYSTEM_PROMPT` as the system message.
  - The constructed local prompt as the user message.

### 1.2 Coverage tags

Each generated constraint object carries one or more `coverage_tags` describing what it tests.
The current tags (also used for `--tags`) are:

- **`year_vs_days`**: one year vs. 365/366 days (e.g., `x + Period(1,0,0)` vs `x + Period(0,0,365)`).
- **`month_vs_days`**: one month vs. 28/30/31 days (e.g., end-of-month behavior).
- **`symbolic_date_vars`**: symbolic variables used inside `Date(...)` (e.g., `Date(x.year + 4, x.month, x.day)`).
- **`property_access`**: constraints that use `.year`, `.month`, `.day` on date variables.
- **`logical_operators`**: non-trivial use of `&&`, `||`, `!`, and `->`.

When `--tags` is provided:

- The prompt explicitly instructs the LLM to:
  - **Only** generate objects whose `coverage_tags` are a subset of the allowed list.
  - Focus the constraints on those behaviors (no unrelated categories mixed in).

### 1.3 Validation & feedback loop during generation

Generation is **not** one-shot. Each batch of objects goes through a structured validation loop in
`ConstraintGenerator._one_call()`:

1. **JSON parsing & schema check**
   - Attempt to parse the LLM response as a JSON array.
   - Validate structure via `_basic_schema_ok()`:
     - Each element must be a dict with `description`, `declarations`, `constraints`, `coverage_tags`.
     - `constraints` must be a non-empty list of strings.
2. **Constraint count check**
   - For each object, count how many top-level constraint strings it has.
   - Enforce `min_constraints_per_object` / `max_constraints_per_object` or `exact_constraints_per_object`.
3. **Parser-based validation**
   - For each object, call `_validate_constraints_with_parser()`:
     - Uses `datesmt.constraint_parser.ConstraintParser` to generate and execute builder code.
     - Ensures all `declarations` and `constraints` are syntactically valid for DateSMT.
4. **Feedback to the LLM**
   - On any failure (JSON parse error, schema error, constraint-count mismatch, or parser error),
     a detailed feedback message is constructed, including:
     - Error type and message.
     - Offending object index.
     - Previews of the generated `declarations` and `constraints`.
   - This feedback is appended to the prompt and the batch is re-generated up to `retries+1` times.

If parsing fails with a hard API error (e.g., 401/403/rate limit), the code fails fast instead of retrying.

### 1.4 Logging

The generator logs all LLM calls and feedback to timestamped JSONL files:

- Location (per run):  
  `dataset/llm_constraints/constraints/llm_calls_YYYY-MM-DD_HH-MM-SS.jsonl`
- Each line records:
  - `batch_id`, `timestamp`, `attempt`
  - `prompt` (truncated)
  - `response_preview` (truncated)
  - Any `feedback_type` / `parse_error` / `object_index`, etc.

These logs make it possible to reproduce or debug individual generations.

### 1.5 Combining per-tag files into a single dataset

Once per-tag constraint files (e.g., `year_vs_days.json`, `month_vs_days.json`,
`symbolic_date_vars.json`, `property_access.json`, `logical_operators.json`) have been generated,
they are merged with:

```bash
python dataset/llm_constraints/generator/combine_constraints.py \
  --constraints-dir dataset/llm_constraints/constraints \
  --output dataset/llm_constraints/constraints/constraints.json
```

`combine_constraints.py`:

- Reads all `*.json` files in the constraints directory **except** `constraints.json`.
- Processes files in **alphabetical order**.
- For each dict-style constraint object:
  - Preserves its existing `id` as `generated_id` (if present).
  - Assigns a new continuous `id` of the form:
    - `llm-<FILENAME>-<NUM>`  
      (e.g., `llm-logical_operators-1`, `llm-logical_operators-2`, then continuing into the next file).
- Writes the combined array to `constraints/constraints.json`.

The resulting `constraints.json` is the master LLM constraint dataset.

---

## 2. Legal-Doc Constraint Dataset (`dataset/legal_doc_constraints`)

### 2.1 Source data

The legal-doc dataset is derived from U.S. Internal Revenue Code (Title 26) text.
The source text is pre-processed into records (e.g., clauses/sections) stored in:

- `dataset/legal_doc_constraints/processed_data/selected.jsonl`

Each record includes:

- A unique `id`.
- A text span from the statute.
- Optional metadata (headings, context, etc.).

### 2.2 Extraction entry point

- Code: `dataset/legal_doc_constraints/generator/llm_extractor.py`
- CLI (simplified):

```bash
python dataset/legal_doc_constraints/generator/llm_extractor.py \
  --input dataset/legal_doc_constraints/processed_data/selected.jsonl \
  --output dataset/legal_doc_constraints/constraints/constraints_YYYY-MM-DD_HH-MM-SS.jsonl
```

Arguments (see the script for full details):

- **`--input`**: JSONL file of pre-selected legal text records.
- **`--output`**: JSONL file where extracted constraints are written.
- **`--id-range`** (optional): process only a subset of record IDs. I generated 10 by 10 and then putted them together into constraints.json.
- **`--api-key`**, **`--model`**, **`--provider`**: LLM configuration.

### 2.3 Legal extraction prompt & output format

`llm_extractor.py` defines `LEGAL_EXTRACTION_PROMPT`, which:

- Instructs the LLM to:
  - Convert legal clauses into precise DateSMT constraints.
  - Extract *all explicit* and logically required temporal constraints.
- Defines a type system:
  - `date`, `int`, `bool` symbolic variable types.
  - Concrete `Date(year, month, day)` and `Period(years, months, days)` constructors.
- Specifies allowed operations:
  - Date ± Period, Period ± Period, Period × int.
  - Comparisons, logical operators (`&&`, `||`, `!`, `->`), implications, and property access `.year/.month/.day`.
- Lists **forbidden** expressions (e.g., Period comparisons, dates out of range, undeclared variables).
- Requires output to be either:
  - A single JSON object:
    ```json
    {
      "description": "...",
      "declarations": ["var_name: type", ...],
      "constraints": ["constraint_expr", ...]
    }
    ```
  - Or the literal `null` if the text has no temporal semantics.

### 2.4 Record-by-record extraction with validation & feedback

For each input record, `extract_constraints_with_llm()`:

1. **Calls the LLM**
   - Sends the statute text plus the `LEGAL_EXTRACTION_PROMPT`.
2. **Parses the LLM response**
   - Tries strict JSON parsing first.
   - Has multiple fallback strategies (e.g., strip surrounding text, fix trailing commas).
3. **Structural validation**
   - Ensures the result is either `null` or an object with:
     - `description`, `declarations`, `constraints`.
4. **Parser-based validation**
   - Uses `_validate_constraints_with_parser()`:
     - Calls `ConstraintParser.generate_builder_code()` with the returned `constraints` and `declarations`.
     - Catches syntax/semantic errors produced by the parser.
5. **Feedback & retry**
   - On any error (JSON parse, missing fields, parser errors), constructs a detailed feedback message:
     - Includes the parser error and the candidate declarations/constraints.
   - Feeds this back into the LLM prompt and retries up to `max_retries` times.
   - Each attempt and its corresponding feedback are logged.

Successful extractions are written to the output JSONL file, preserving the original record IDs and adding provenance.

### 2.5 Logging

Analogous to the LLM synthetic pipeline, `llm_extractor.py` logs LLM calls:

- Logs are stored as `llm_calls_YYYY-MM-DD_HH-MM-SS.jsonl` under
  `dataset/legal_doc_constraints/constraints/`.
- Each line records:
  - `record_id`, `timestamp`, `attempt`
  - The feedback type (`json_parse_error`, `parser_error`, etc.).
  - Previews of the response or offending constraints.

This allows inspection of how each legal clause was interpreted and repaired.

### 2.6 Aggregated constraints file

Once extraction is complete, the main constraints dataset lives in:

- `dataset/legal_doc_constraints/constraints/constraints.jsonl`

Each line is a JSON object representing constraints for a single legal record, with:

- `id` (source record identifier)
- `description`
- `declarations`
- `constraints`
- Optional derived IDs (e.g., `parsed_id`, `filtered_id`) and provenance.

---

## 3. Post-generation Testing & Validation (both datasets)

Both datasets are tested and validated using a common infrastructure:

- **Benchmark runner**: `dataset/run_benchmarks.py`
- **Validation logic**: `dataset/validation.py`
- **Enumeration baseline**: `datesmt/enumeration_baseline.py`

In brief:

1. Constraints from either dataset (LLM or legal-doc) are fed into the benchmark runner.
2. Multiple symbolic approaches (int and bitvector) plus the enumeration baseline are run.
3. If analysis is enabled, each symbolic solution is checked against the enumeration baseline:
   - Enumeration is treated as ground truth.
   - Results are summarized into `checked_summary*.json` files.

This gives a uniform way to assess solver performance and correctness on both synthetic and legally-derived constraint sets.

