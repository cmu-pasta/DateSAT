#!/usr/bin/env python3
import argparse, csv, json, re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

try:
    import yaml  # pip install pyyaml
except Exception:
    yaml = None

DATE_PERIOD_KEYS: Set[str] = {
    "StartTime","EndTime","StartDate","EndDate","ValidFrom","ValidTo","NotBefore","NotAfter",
    "Schedule","ScheduleExpression","CronExpression","Rate","Interval","IntervalInSeconds",
    "StartWindowMinutes","CompletionWindowMinutes","PreferredBackupWindow","PreferredMaintenanceWindow",
    "Duration","DurationSeconds","Timeout","TimeoutSeconds","IdleTimeout","IdleTimeoutSeconds",
    "ExecutionTimeout","ExecutionTimeoutSeconds","TimeoutInMinutes","AttemptDurationSeconds",
    "StopTimeout","StartTimeout","GracePeriod","GracePeriodSeconds",
    "Retention","RetentionDays","RetentionInDays","RetentionPeriod","RetentionPolicy","RetentionPeriodInDays",
    "DeleteAfterDays","TransitionInDays","ExpirationInDays","NoncurrentVersionExpirationInDays",
    "Lifecycle","LifecycleRules","RotationRules","AutomaticallyAfterDays",
    "DefaultTTL","MinTTL","MaxTTL","Ttl","TTL","ttl","TtlSeconds","TimeToLive",
    "AccessTokenValidity","IdTokenValidity","RefreshTokenValidity","TokenValidityUnits",
    "LogRetention","LogRetentionDays","MessageRetentionPeriod",
    "SnapshotRetentionLimit","AutomatedSnapshotStartHour","AutomatedSnapshotRetentionPeriod",
    "BackupRetentionPeriod","DeletionWindowInDays","PendingWindowInDays","ScheduleExpressionTimezone",
    "BufferingHints","SizeInMBs",
}

SERVICE_BY_CF_TYPE_PREFIX: Dict[str, str] = {
    "AWS::S3::": "s3","AWS::RDS::": "rds","AWS::Redshift::": "redshift","AWS::IAM::": "iam",
    "AWS::KMS::": "kms","AWS::CloudFront::": "cloudfront","AWS::Route53::": "route53",
    "AWS::Lambda::": "lambda","AWS::Events::": "events","AWS::CloudWatch::": "cloudwatch",
    "AWS::Logs::": "logs","AWS::Backup::": "backup","AWS::SecretsManager::": "secretsmanager",
    "AWS::KinesisFirehose::": "firehose","AWS::AutoScaling::": "autoscaling","AWS::ElastiCache::": "elasticache",
    "AWS::ECR::": "ecr","AWS::ECS::": "ecs","AWS::Batch::": "batch","AWS::EMR::": "emr",
    "AWS::Glue::": "glue","AWS::CloudTrail::": "cloudtrail","AWS::OpenSearchService::": "opensearch",
    "AWS::Neptune::": "neptune","AWS::SNS::": "sns","AWS::SQS::": "sqs","AWS::StepFunctions::": "stepfunctions",
    "AWS::SSM::": "ssm",
}

CONSTRUCTOR_PATTERNS = [
    (re.compile(r"\b([A-Za-z0-9_]+)\.Bucket\s*\("), "s3"),
    (re.compile(r"\b([A-Za-z0-9_]+)\.LifecycleRule\s*\("), "s3"),
    (re.compile(r"\b([A-Za-z0-9_]+)\.DatabaseInstance\s*\("), "rds"),
    (re.compile(r"\b([A-Za-z0-9_]+)\.LogGroup\s*\("), "logs"),
    (re.compile(r"\b([A-Za-z0-9_]+)\.Rule\s*\("), "events"),
    (re.compile(r"\b([A-Za-z0-9_]+)\.Trail\s*\("), "cloudtrail"),
    (re.compile(r"\b([A-Za-z0-9_]+)\.Key\s*\("), "kms"),
    (re.compile(r"\b([A-Za-z0-9_]+)\.Secret\s*\("), "secretsmanager"),
    (re.compile(r"\b([A-Za-z0-9_]+)\.Distribution\s*\("), "cloudfront"),
    (re.compile(r"\b([A-Za-z0-9_]+)\.RecordSet\s*\("), "route53"),
    (re.compile(r"new\s+s3\.Bucket\s*\("), "s3"),(re.compile(r"new\s+s3\.LifecycleRule\s*\("), "s3"),
    (re.compile(r"new\s+rds\."), "rds"),(re.compile(r"new\s+logs\.LogGroup\s*\("), "logs"),
    (re.compile(r"new\s+cloudfront\."), "cloudfront"),(re.compile(r"new\s+route53\."), "route53"),
    (re.compile(r"new\s+events\.Rule\s*\("), "events"),(re.compile(r"new\s+secretsmanager\."), "secretsmanager"),
    (re.compile(r"new\s+kms\."), "kms"),(re.compile(r"new\s+aws\.s3\.Bucket\s*\("), "s3"),
    (re.compile(r"new\s+aws\.cloudwatch\.LogGroup\s*\("), "logs"),
]

CODE_EXTS = {".py",".ts",".js",".tsx",".jsx",".go",".java"}
DATA_EXTS = {".json",".yaml",".yml",".template",".sam"}

def sha256(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()

def load_yaml_or_json(p: Path) -> Any:
    try:
        if p.suffix.lower() == ".json":
            return json.loads(p.read_text(encoding="utf-8", errors="ignore"))
        if p.suffix.lower() in (".yaml",".yml",".template",".sam") and yaml is not None:
            return yaml.safe_load(p.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return None
    return None

def is_cloudformation_template(obj: Any) -> bool:
    return isinstance(obj, dict) and isinstance(obj.get("Resources"), dict)

def cf_service_from_type(type_str: str) -> str:
    if not isinstance(type_str, str): return "unknown"
    for prefix, svc in SERVICE_BY_CF_TYPE_PREFIX.items():
        if type_str.startswith(prefix):
            return svc
    return "unknown"

def any_date_key_in_text(s: str) -> List[str]:
    low = s.lower(); keys = []
    for k in DATE_PERIOD_KEYS:
        if k.lower() in low: keys.append(k)
    return sorted(set(keys))

# ---- Qualification logic: prefer days/months/years or explicit date-time ----

_TTL_KEYS = {"minttl", "maxttl", "defaultttl", "ttl"}
_MAYBE_TIME_KEYS = {
    "duration", "interval", "timeout", "retryinterval", "retention", "retentionperiod",
    "messageretentionperiod", "executiontimeout", "startwindowminutes", "completionwindowminutes"
}

def _contains_day_month_year_units(s: str) -> bool:
    return bool(re.search(r"\b(day|days|month|months|year|years)\b", s, re.IGNORECASE) or
                re.search(r"Duration\.(days|months|years)\s*\(", s))

def _contains_explicit_date(s: str) -> bool:
    return bool(
        re.search(r"\b20\d{2}-\d{1,2}-\d{1,2}(?:[ T]\d{2}:\d{2})?\b", s) or
        re.search(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", s) or
        re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+20\d{2}\b", s, re.IGNORECASE)
    )

def _key_category(key: str) -> str | None:
    low = key.lower()
    if re.search(r"date|notbefore|notafter|validfrom|validto", low):
        return "date_point"
    if "days" in low or "years" in low or "windowindays" in low or low.endswith("indays") or "afterdays" in low:
        return "days_years"
    if low in _TTL_KEYS or low in _MAYBE_TIME_KEYS:
        return "maybe_time"
    return None

def _property_qualifies(key: str, value_str: str) -> bool:
    cat = _key_category(key)
    if cat == "days_years":
        return True
    if cat == "date_point":
        return _contains_explicit_date(value_str)
    if cat == "maybe_time":
        return _contains_day_month_year_units(value_str) or _contains_explicit_date(value_str)
    return False

def dict_has_qualifying_property(d: Any, found_keys: List[str]) -> bool:
    if isinstance(d, dict):
        for k, v in d.items():
            # stringify safely
            try:
                v_str = json.dumps(v, ensure_ascii=False, default=str)
            except Exception:
                v_str = str(v)
            if _property_qualifies(k, v_str):
                found_keys.append(k)
                return True
            if dict_has_qualifying_property(v, found_keys):
                return True
    elif isinstance(d, list):
        for it in d:
            if dict_has_qualifying_property(it, found_keys):
                return True
    return False

def find_lines(text: str, start: int, end: int) -> Tuple[int,int]:
    return text.count("\n", 0, start) + 1, text.count("\n", 0, end) + 1


def _line_start(text: str, idx: int) -> int:
    nl = text.rfind("\n", 0, idx)
    return 0 if nl == -1 else nl + 1


def _find_first_paren_or_brace(text: str, start_idx: int, search_limit: int = 500) -> int:
    end = min(len(text), start_idx + search_limit)
    segment = text[start_idx:end]
    p = segment.find("(")
    b = segment.find("{")
    cand = -1
    if p != -1 and b != -1:
        cand = min(p, b)
    elif p != -1:
        cand = p
    elif b != -1:
        cand = b
    return -1 if cand == -1 else start_idx + cand


def _brace_balanced_block(text: str, open_pos: int) -> Tuple[int, int]:
    i = open_pos
    if i >= len(text) or text[i] not in "({":
        return i, min(len(text), i + 400)
    stack = [text[i]]
    i += 1
    while i < len(text) and stack:
        ch = text[i]
        if ch in "({":
            stack.append(ch)
        elif ch in ")}":
            if stack:
                top = stack[-1]
                if (top == "(" and ch == ")") or (top == "{" and ch == "}"):
                    stack.pop()
        i += 1
    end = i if i <= len(text) else len(text)
    return open_pos, end

def index_cf_template(repo_id: str, rel: Path, text: str, obj: Dict[str,Any]) -> List[Dict[str,Any]]:
    out: List[Dict[str,Any]] = []
    resources = obj.get("Resources", {})
    for lid, res in resources.items():
        if not isinstance(res, dict): continue
        rtype = res.get("Type"); props = res.get("Properties", {}) or {}
        found_keys: List[str] = []
        if not dict_has_qualifying_property(props, found_keys):
            continue
        keys = sorted(set(found_keys))
        svc = cf_service_from_type(rtype or "")
        idx = text.find(lid); idx = max(idx, 0)
        start = max(0, idx - 80); end = min(len(text), idx + 600)
        snippet = text[start:end]
        sline, eline = find_lines(text, start, end)
        out.append({
            "repo_id": repo_id, "rel_file": str(rel), "language": rel.suffix.lstrip("."),
            "hit_type": "cf_template", "service": svc, "logical_id": lid,
            "start_line": sline, "end_line": eline, "start_byte": start, "end_byte": end,
            "keys_found": keys, "snippet_sha256": sha256(snippet), "snippet_preview": snippet[:400],
        })
    return out

def any_structured_date_key(text: str) -> List[str]:
    keys = set()
    # key: value OR "key": value
    for m in re.finditer(r"[\"']?([A-Za-z_][A-Za-z0-9_]+)[\"']?\s*:\s*([^\n,}\]]+)", text):
        k = m.group(1); v = m.group(2)
        if _property_qualifies(k, v):
            keys.add(k)
    # key = value (kwargs)
    for m in re.finditer(r"([A-Za-z_][A-Za-z0-9_]+)\s*=\s*([^\n,)\]]+)", text):
        k = m.group(1); v = m.group(2)
        if _property_qualifies(k, v):
            keys.add(k)
    return sorted(keys)

def index_code(repo_id: str, rel: Path, text: str) -> List[Dict[str,Any]]:
    out: List[Dict[str,Any]] = []
    seen_hashes: Set[str] = set()
    for pat, svc in CONSTRUCTOR_PATTERNS:
        for m in pat.finditer(text):
            # Find the argument/object block start, then capture a brace-balanced block
            open_pos = _find_first_paren_or_brace(text, m.start())
            if open_pos == -1:
                # Fallback to a small window if structure not found
                win_start = _line_start(text, m.start())
                win_end = min(len(text), m.end() + 800)
                snippet = text[win_start:win_end]
                keys = any_structured_date_key(snippet)
                if not keys:
                    continue
                sline, eline = find_lines(text, win_start, win_end)
                h = sha256(snippet.strip())
                if h in seen_hashes:
                    continue
                seen_hashes.add(h)
                out.append({
                    "repo_id": repo_id, "rel_file": str(rel), "language": rel.suffix.lstrip("."),
                    "hit_type": "code", "service": svc,
                    "start_line": sline, "end_line": eline, "start_byte": win_start, "end_byte": win_end,
                    "keys_found": keys, "snippet_sha256": h, "snippet_preview": snippet[:400],
                })
                continue

            block_start, block_end = _brace_balanced_block(text, open_pos)
            # Normalize to full line start for stable spans
            norm_start = _line_start(text, block_start)
            norm_end = block_end
            snippet = text[norm_start:norm_end]
            keys = any_structured_date_key(snippet)
            if not keys:
                continue
            sline, eline = find_lines(text, norm_start, norm_end)
            h = sha256(snippet.strip())
            if h in seen_hashes:
                continue
            seen_hashes.add(h)
            out.append({
                "repo_id": repo_id, "rel_file": str(rel), "language": rel.suffix.lstrip("."),
                "hit_type": "code", "service": svc,
                "start_line": sline, "end_line": eline, "start_byte": norm_start, "end_byte": norm_end,
                "keys_found": keys, "snippet_sha256": h, "snippet_preview": snippet[:400],
            })
    return out

def main():
    ap = argparse.ArgumentParser(description="Build a span-based hit index for date/period occurrences (no code saved)")
    ap.add_argument("--aws-programs", required=True)
    ap.add_argument("--repos-root", required=True)
    ap.add_argument("--out-index", required=True)
    ap.add_argument("--out-repo-services", required=True)
    ap.add_argument("--log-every", type=int, default=2000)
    args = ap.parse_args()

    repos_root = Path(args.repos_root)
    rows = list(csv.DictReader(open(args.aws_programs, encoding="utf-8")))

    seen: Set[str] = set()
    repo_services: Set[Tuple[str,str]] = set()
    outf = open(args.out_index, "w", encoding="utf-8")

    for row in rows:
        repo_id = str(row.get("repository",""))
        if not repo_id or repo_id in seen:
            continue
        seen.add(repo_id)

        repo_dir = repos_root / repo_id
        if not repo_dir.exists():
            continue

        files = [p for p in repo_dir.rglob("*") if p.is_file()]
        to_scan = [p for p in files if p.suffix.lower() in (CODE_EXTS | DATA_EXTS)]
        print(f"[INFO] Repo {repo_id}: scanning {len(to_scan)} files")

        for i, p in enumerate(to_scan, 1):
            if args.log_every and i % args.log_every == 0:
                print(f"  .. {i}/{len(to_scan)}")
            rel = p.relative_to(repo_dir)
            ext = p.suffix.lower()

            if ext in DATA_EXTS:
                obj = load_yaml_or_json(p)
                if obj and is_cloudformation_template(obj):
                    try:
                        text = p.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        text = json.dumps(obj, ensure_ascii=False)[:1000]
                    hits = index_cf_template(repo_id, rel, text, obj)
                    for h in hits:
                        outf.write(json.dumps(h, ensure_ascii=False) + "\n")
                        if h["service"] != "unknown":
                            repo_services.add((repo_id, h["service"]))

            if ext in CODE_EXTS:
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    text = ""
                if text:
                    hits = index_code(repo_id, rel, text)
                    for h in hits:
                        outf.write(json.dumps(h, ensure_ascii=False) + "\n")
                        if h["service"] != "unknown":
                            repo_services.add((repo_id, h["service"]))

    outf.close()

    with open(args.out_repo_services, "w", newline="", encoding="utf-8") as rf:
        w = csv.writer(rf)
        w.writerow(["repo_id","service"])
        for r,s in sorted(repo_services):
            w.writerow([r,s])

    print(f"[DONE] Hits written to: {args.out_index}")
    print(f"[DONE] Repo-service map: {args.out_repo_services}")

if __name__ == "__main__":
    main()


