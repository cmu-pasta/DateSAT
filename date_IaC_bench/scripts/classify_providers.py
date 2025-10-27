#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
from pathlib import Path

# -----------------------------
# Provider signatures to scan for
# -----------------------------
PROVIDER_SIGS = {
    "aws": {
        "npm": [
            "aws-cdk-lib", "@aws-cdk/", "@pulumi/aws", "@cdktf/provider-aws",
            "@cdktf/provider-aws-native", "aws-sdk"
        ],
        "python": [
            "aws-cdk-lib", "aws_cdk", "pulumi-aws"
        ],
        "go": [
            "github.com/aws/aws-cdk-go/awscdk", "github.com/pulumi/pulumi-aws"
        ],
        "java": [
            "software.amazon.awscdk",
        ],
        "hcl_cdktf": [
            "hashicorp/aws", "aws-native"
        ],
        "generic": [
            "AWS::"
        ],
    },
    "azure": {
        "npm": [
            "@pulumi/azure", "@pulumi/azure-native", "@cdktf/provider-azurerm"
        ],
        "python": [
            "pulumi-azure", "pulumi-azure-native"
        ],
        "go": [
            "github.com/pulumi/pulumi-azure", "github.com/pulumi/pulumi-azure-native"
        ],
        "java": [
        ],
        "hcl_cdktf": [
            "hashicorp/azurerm"
        ],
        "generic": [
            "AZURE::"
        ],
    },
    "gcp": {
        "npm": [
            "@pulumi/gcp", "@cdktf/provider-google"
        ],
        "python": [
            "pulumi-gcp"
        ],
        "go": [
            "github.com/pulumi/pulumi-gcp"
        ],
        "java": [],
        "hcl_cdktf": [
            "hashicorp/google", "hashicorp/google-beta"
        ],
        "generic": [
            "GCP::", "GOOGLE::"
        ],
    },
}

# Files we might scan to detect providers (repo-aware enrichment)
MANIFEST_FILES = [
    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "requirements.txt", "pyproject.toml", "Pipfile", "Pipfile.lock",
    "go.mod", "go.sum",
    "pom.xml", "build.gradle", "build.gradle.kts",
    "cdktf.json",
    "cdk.json", "Pulumi.yaml", "Pulumi.yml"
]

LOWER_RE = re.compile(r"[a-z0-9_\-:/.\[\]{}()@]+")


def norm_text(x: str) -> str:
    return (x or "").lower()


def csv_only_guess(row) -> set[str]:
    """
    Quick, CSV-only heuristic using 'solution', 'name', 'description', 'directory'.
    """
    providers: set[str] = set()
    sol = norm_text(row.get("solution", ""))
    name = norm_text(row.get("name", ""))
    desc = norm_text(row.get("description", ""))
    dird = norm_text(row.get("directory", ""))

    hay = " ".join([sol, name, desc, dird])

    # Strong signals from 'solution'
    if "aws cdk" in sol:
        providers.add("aws")
    if "cdktf" in sol or "pulumi" in sol:
        # Try keywords from name/description/directory
        if "aws" in hay or "amazon" in hay:
            providers.add("aws")
        if "azure" in hay or "azurerm" in hay:
            providers.add("azure")
        if "gcp" in hay or "google" in hay:
            providers.add("gcp")

    return providers


def scan_file_for_signatures(fp: Path) -> set[str]:
    """
    Read a file and try to match provider signatures.
    Handles JSON and text-ish manifest/lockfiles heuristically.
    """
    providers: set[str] = set()
    try:
        data = fp.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return providers

    low = data.lower()

    # Try JSON parse first if plausible
    if fp.suffix in [".json"]:
        try:
            obj = json.loads(data)
            blob = json.dumps(obj).lower()
            low = blob
        except Exception:
            pass

    # Match signatures
    for prov, buckets in PROVIDER_SIGS.items():
        for _, sigs in buckets.items():
            for sig in sigs:
                if sig.lower() in low:
                    providers.add(prov)
                    break
    return providers


def repo_enrichment_guess(program_dir: Path) -> set[str]:
    """
    Look for provider signatures by scanning common manifest files in the program directory
    and (lightly) its immediate children directories.
    """
    providers: set[str] = set()
    if not program_dir.exists():
        return providers

    # Scan manifests in the directory root
    for mf in MANIFEST_FILES:
        fp = program_dir / mf
        if fp.exists() and fp.is_file():
            providers |= scan_file_for_signatures(fp)

    # Also peek into a few common subpaths
    for sub in ["src", "app", "infra", "lib", "cdktf.out", "cdk.out"]:
        subdir = program_dir / sub
        if subdir.exists() and subdir.is_dir():
            for mf in MANIFEST_FILES:
                fp = subdir / mf
                if fp.exists() and fp.is_file():
                    providers |= scan_file_for_signatures(fp)

    return providers


def classify_row(row, repos_root: Path | None) -> set[str]:
    """
    Combine CSV-only guess with optional repo-aware enrichment.
    """
    providers = csv_only_guess(row)

    if repos_root is not None:
        repo_id = str(row.get("repository", "")).strip()
        directory = row.get("directory", "")
        if repo_id and directory:
            program_dir = (repos_root / repo_id / directory).resolve()
            providers |= repo_enrichment_guess(program_dir)

    return providers


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify IaC programs by cloud provider.")
    parser.add_argument("--programs", required=True, help="Path to programs.csv")
    parser.add_argument("--repos-root", default=None,
                        help="Root dir of unpacked redistributable repos (for enrichment), e.g., ./repos")
    parser.add_argument("--out-dir", default=None,
                        help="Directory to write outputs. Defaults to same folder as --programs")
    parser.add_argument("--out-prefix", default="",
                        help="Optional prefix for output CSVs (e.g., 'pipr_')")
    args = parser.parse_args()

    programs_path = Path(args.programs).resolve()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else programs_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    repos_root = Path(args.repos_root).resolve() if args.repos_root else None
    if repos_root and not repos_root.exists():
        print(f"[WARN] repos-root '{repos_root}' not found. Proceeding without repo enrichment.")
        repos_root = None
    prefix = args.out_prefix

    aws_path   = out_dir / f"{prefix}aws_programs.csv"
    azure_path = out_dir / f"{prefix}azure_programs.csv"
    gcp_path   = out_dir / f"{prefix}gcp_programs.csv"
    multi_path = out_dir / f"{prefix}multi_cloud_programs.csv"
    other_path = out_dir / f"{prefix}other_programs.csv"

    aws_count = azure_count = gcp_count = multi_count = other_count = 0

    with programs_path.open("r", newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        base_fields = reader.fieldnames or []
        extra_fields = ["is_aws", "is_azure", "is_gcp", "provider_set"]
        out_fields = list(dict.fromkeys(list(base_fields) + extra_fields))

        # Prepare writers
        def open_writer(path: Path):
            f = path.open("w", newline="", encoding="utf-8")
            w = csv.DictWriter(f, fieldnames=out_fields)
            w.writeheader()
            return f, w

        aws_f, aws_w = open_writer(aws_path)
        azure_f, azure_w = open_writer(azure_path)
        gcp_f, gcp_w = open_writer(gcp_path)
        multi_f, multi_w = open_writer(multi_path)
        other_f, other_w = open_writer(other_path)

        try:
            for row in reader:
                provs = classify_row(row, repos_root)
                is_aws = int("aws" in provs)
                is_azure = int("azure" in provs)
                is_gcp = int("gcp" in provs)
                provider_set = ",".join(sorted(provs)) if provs else ""

                out_row = dict(row)
                out_row.update({
                    "is_aws": is_aws,
                    "is_azure": is_azure,
                    "is_gcp": is_gcp,
                    "provider_set": provider_set,
                })

                total = is_aws + is_azure + is_gcp
                if total == 1:
                    if is_aws:
                        aws_w.writerow(out_row)
                        aws_count += 1
                    elif is_azure:
                        azure_w.writerow(out_row)
                        azure_count += 1
                    else:
                        gcp_w.writerow(out_row)
                        gcp_count += 1
                elif total >= 2:
                    multi_w.writerow(out_row)
                    multi_count += 1
                else:
                    other_w.writerow(out_row)
                    other_count += 1
        finally:
            aws_f.close(); azure_f.close(); gcp_f.close(); multi_f.close(); other_f.close()

    # Summary
    print("=== Provider classification summary ===")
    print(f"AWS-only:   {aws_count}")
    print(f"Azure-only: {azure_count}")
    print(f"GCP-only:   {gcp_count}")
    print(f"Multi:      {multi_count}")
    print(f"Other:      {other_count}")
    print("Outputs written:", aws_path, azure_path, gcp_path, multi_path, other_path)


if __name__ == "__main__":
    main()


