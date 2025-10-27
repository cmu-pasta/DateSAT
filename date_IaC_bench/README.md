## DateSMT Bench - Dataset Provider Classification

This folder contains scripts and metadata to prepare subsets of programs by cloud provider for the DateSMT benchmark.

### What we collect

- **Split CSVs** derived from `metadata/programs.csv` into provider-specific buckets:
  - `aws_programs.csv` — programs inferred as AWS-only
  - `azure_programs.csv` — programs inferred as Azure-only
  - `gcp_programs.csv` — programs inferred as GCP-only
  - `multi_cloud_programs.csv` — programs that likely use 2+ providers
  - `other_programs.csv` — programs where no clear AWS/Azure/GCP signal was detected

All outputs are written to `datesmt_bench/metadata/` by default.

### How classification works

`scripts/classify_providers.py` classifies each IaC program using two layers:

1) Fast CSV-only heuristics (no repository content required):
   - Looks for provider hints in `solution`, `name`, `description`, and `directory` text.

2) Optional repo-aware enrichment (if redistributable repositories are unpacked):
   - Scans common manifest files in each program directory (e.g., `package.json`, `requirements.txt`, `go.mod`, `cdktf.json`, `Pulumi.yaml`) for provider-specific dependencies and strings.

You can extend signatures in the script's `PROVIDER_SIGS` dictionary as needed.

### Usage

CSV-only mode (fast):

```bash
python3 datesmt_bench/scripts/classify_providers.py \
  --programs /Users/angelc2/Downloads/10173400/metadata/programs.csv \
  --out-dir /Users/angelc2/Downloads/10173400/datesmt_bench/metadata
```

With repository enrichment (if you have unpacked redistributable repos under `./repos`):

```bash
python3 datesmt_bench/scripts/classify_providers.py \
  --programs /Users/angelc2/Downloads/10173400/metadata/programs.csv \
  --repos-root /absolute/path/to/repos \
  --out-dir /Users/angelc2/Downloads/10173400/datesmt_bench/metadata
```

Optional prefix for filenames:

```bash
python3 datesmt_bench/scripts/classify_providers.py \
  --programs /Users/angelc2/Downloads/10173400/metadata/programs.csv \
  --out-dir /Users/angelc2/Downloads/10173400/datesmt_bench/metadata \
  --out-prefix pipr_
```

This will produce files like `pipr_aws_programs.csv` in the output directory.

### Notes

- CSV-only mode is sufficient for an initial benchmark split.
- Enrichment mode improves accuracy by looking at provider dependencies (e.g., `@pulumi/aws`, `hashicorp/google`, `aws-cdk-lib`).
- Outputs are idempotent; re-running will overwrite the CSVs in the output directory.

## Index-only workflow (no synthesis; no saving code)

Use `scripts/filter_date_aws.py` to scan AWS-only repositories and produce:
- `aws_filtered.jsonl` — span-based hit index (no broken `.ts`/`.py` saved)
- `aws_repo_services.csv` — mapping of repos to services with at least one hit

Run:
```bash
python3 datesmt_bench/scripts/filter_date_aws.py \
  --aws-programs /Users/angelc2/Downloads/10173400/datesmt_bench/metadata/aws_programs.csv \
  --repos-root /Users/angelc2/Downloads/10173400/dataset \
  --out-index /Users/angelc2/Downloads/10173400/datesmt_bench/metadata/aws_filtered.jsonl \
  --out-repo-services /Users/angelc2/Downloads/10173400/datesmt_bench/metadata/aws_repo_services.csv \
  --log-every 1000
```

Outputs are written under `datesmt_bench/metadata/`.

Notes:
- The index records repo/file/service plus a small preview and byte/line spans for later parsing.
- This approach avoids synthesizing or saving malformed code; it’s fast and robust across languages.

### View snippets for filtered/indexed hits

Use `scripts/show_filtered_snippet.py` to print the corresponding source code for a hit from `aws_filtered.jsonl` (or any JSONL with the same schema):

By sha:

```bash
python3 datesmt_bench/scripts/show_filtered_snippet.py \
  --repos-root /Users/angelc2/Downloads/10173400/dataset \
  --filtered-file /Users/angelc2/Downloads/10173400/datesmt_bench/metadata/aws_filtered.jsonl \
  --sha <snippet_sha256>
```

By file and line span:

```bash
python3 datesmt_bench/scripts/show_filtered_snippet.py \
  --repos-root /Users/angelc2/Downloads/10173400/dataset \
  --filtered-file /Users/angelc2/Downloads/10173400/datesmt_bench/metadata/aws_filtered.jsonl \
  --repo-id <repo_id> \
  --rel-file <relative/path/in/repo> \
  --start-line <N> --end-line <M> --context 0
```

Tip: to view the Nth entry quickly, you can extract its sha via awk/jq and pass to `--sha`.

You can also select by GitHub repo ID or by JSONL line range in `aws_filtered.jsonl`:

- By repo ID (first match):
```bash
python3 datesmt_bench/scripts/show_filtered_snippet.py \
  --repos-root /Users/angelc2/Downloads/10173400/dataset \
  --filtered-file /Users/angelc2/Downloads/10173400/datesmt_bench/metadata/aws_filtered.jsonl \
  --repo-id 300600965 --max-matches 1
```

- By JSONL line range (e.g., lines 10–12 in the filtered file):
```bash
python3 datesmt_bench/scripts/show_filtered_snippet.py \
  --repos-root /Users/angelc2/Downloads/10173400/dataset \
  --filtered-file /Users/angelc2/Downloads/10173400/datesmt_bench/metadata/aws_filtered.jsonl \
  --filtered-start 10 --filtered-end 12 --max-matches 3
```


## Preferred: Index + IR without saving code (Option 2)

Use `scripts/build_hit_index_and_ir.py` to scan synthesized artifacts (CloudFormation/SAM, Terraform JSON) and produce:
- `<stem>_hits.jsonl` — span-based hit index (no broken `.ts`/`.py` saved)
- `<stem>_ir.jsonl` — provider-neutral IR with only day/month/year/date-time fields

Run (defaults to `datesmt_bench/metadata/aws_programs.csv`):

```bash
python3 datesmt_bench/scripts/build_hit_index_and_ir.py \
  --repos-root /Users/angelc2/Downloads/10173400/dataset \
  --max-repos 50 --log-every 1000
```

Outputs are written to `datesmt_bench/metadata/` as `aws_programs_hits.jsonl` and `aws_programs_ir.jsonl`.

Notes:
- The hit index records repo/file/service and a short preview; re-open original files for full context later.
- The IR prunes to day/month/year/date-time semantics (excludes pure seconds/hours unless explicit date present).
- CDK/CDKTF/Pulumi users: if synthesized outputs (`cdk.out`, `cdktf.out`) exist in the repo, they will be picked up as CloudFormation/Terraform JSON.

## Legacy: File-based snippet saver

`scripts/extract_date_aws.py` can still emit per-file “_extracted” outputs but is less ideal for code. Prefer Option 2 above.

### Requirements for synthesis

- Node.js + one of: pnpm, npm, or yarn (script auto-detects which to use)
- CDK CLI available (preferably via npx); CDKTF via npx; Pulumi CLI (optional)
- Network access to install packages and providers (best-effort)
- Env defaults are set: AWS_REGION/AWS_DEFAULT_REGION=us-east-1

Troubleshooting:
- Logs are written under `datesmt_bench/metadata/synth_logs/` per repo and project kind (e.g., `_cdk.log`).
- Manifest `aws_programs_artifacts.jsonl` contains an entry for every repo; empty `artifacts: []` means synthesis failed or produced nothing. Check logs to see why (missing CLI, install failed, context lookups blocked, etc.).

## Environment setup (conda) and requirements

Create and activate a conda environment, then install Python deps:

```bash
conda create -y -n datesmt_bench python=3.12
conda activate datesmt_bench
pip install -r ./datesmt_bench/requirements.txt
```

Optional CLIs (improve synthesis success):

```bash
# Node.js & package managers (choose one)
# macOS via Homebrew examples:
brew install node
npm install -g aws-cdk # optional if not using npx
npm install -g cdktf-cli # optional if not using npx
brew install pulumi/tap/pulumi # optional
```

Verify:

```bash
node -v && npm -v
cdk --version || npx cdk --version
yarn -v || true
pnpm -v || true
pulumi version || true
```



