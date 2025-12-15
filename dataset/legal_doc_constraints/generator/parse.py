"""
Parse Title 26 XML (Title 26, U.S. Code) into structured JSONL format.

This script:
- Loads the fixed raw XML file for Title 26 from ``raw_data/title26.xml``.
- Walks the USLM XML hierarchy (subtitle, chapter, subchapter, part, subpart, section).
- Extracts records at **section and subsection level only**:
  * For sections with subsections: processes each subsection separately
  * For sections without subsections: processes the entire section as one record
  * Within each subsection/section: combines ALL nested content (paragraphs, subparagraphs, clauses) into one text block
- Normalizes the text (removing page headers/footers and editorial notes while
  preserving legal numbering and internal citations).

The output is a JSONL file at:
    ``processed_data/parsed.jsonl``

Each line is a JSON object for **one section or subsection** with:
- ``id``: Sequential numeric identifier (as string).
- ``hierarchy``: Object describing title / subtitle / chapter / subchapter / part / subpart / section.
- ``subsection_path``: String like ``"(a)(1)(A)"`` (empty for main section text).
- ``heading``: Section heading/title.
- ``element_type``: Either ``"section"`` or ``"subsection"``.
- ``identifier``: Full USLM identifier path.
- ``raw_text``: Full text of the element before normalization/cleanup.
- ``text``: Normalized text (headers/footers/notes removed, whitespace cleaned, all nested content combined).

A formatted version is automatically generated at ``processed_data/parsed_formatted.jsonl``.
"""

import json
import re
import uuid
from pathlib import Path
from typing import Dict, List, Optional
from xml.etree import ElementTree as ET

# Import formatting function
from format_jsonl import format_as_pretty_jsonl

# USLM namespace
USLM_NS = "{http://xml.house.gov/schemas/uslm/1.0}"


TEXT_SKIP_TAGS = {
    # Editorial / notes / references (but preserve ref text content, just skip the element itself)
    "notes",
    "note",
    "sourceCredit",
    "credit",
    "toc",
    "crossHeading",
    "crossReference",
    # Note: "ref" is NOT in skip tags - we want to preserve reference text like "section 1561"
    # Layout / non-substantive
    "table",
    "page",
    "header",
    "footer",
    "footnote",
}

# Structural tags where we want to stop pulling text from children and instead
# treat them as separate elements (we will process them on their own).
STRUCTURAL_CHILD_TAGS = {
    "section",
    "subsection",
    "paragraph",
    "subparagraph",
    "clause",
    "subclause",
}


def _strip_ns(tag: str) -> str:
    """Remove XML namespace from a tag name."""
    return tag.replace(USLM_NS, "")


def get_raw_text_content(elem: ET.Element) -> str:
    """
    Extract plain text content from an element *before* structural cleanup.

    This keeps everything (including notes/headers/footers/etc.) and only
    normalizes whitespace. Useful for debugging and provenance.
    """
    text_parts: List[str] = []

    if elem.text:
        text_parts.append(elem.text)

    for child in elem:
        text_parts.append(get_raw_text_content(child))
        if child.tail:
            text_parts.append(child.tail)

    result = "".join(text_parts)
    # Normalize whitespace but otherwise keep content as-is
    result = re.sub(r"\s+", " ", result)
    return result.strip()


def get_text_content(elem: ET.Element, include_nested_structural: bool = False) -> str:
    """
    Extract plain text content from an element, preserving numbering and
    citations but skipping editorial notes, page headers/footers.
    
    Args:
        include_nested_structural: If True, includes text from nested structural
            units (paragraphs, subparagraphs, clauses). If False, skips them.
            Set to True when processing subsections that should include all content.
    
    IMPORTANT: Preserves text content of <ref> elements (like "section 1561")
    but skips the element wrapper to avoid duplication.
    """
    text_parts = []

    # Get direct text
    if elem.text:
        text_parts.append(elem.text.strip())

    # Get text from relevant child elements
    for child in elem:
        child_tag = _strip_ns(child.tag)

        # Skip editorial / layout / notes
        if child_tag in TEXT_SKIP_TAGS:
            # Preserve tail text after skipped element
            if child.tail:
                text_parts.append(child.tail.strip())
            continue

        # Handle nested structural units based on flag
        if child_tag in STRUCTURAL_CHILD_TAGS:
            if include_nested_structural:
                # Include text from nested structural units
                nested_text = get_text_content(child, include_nested_structural=True)
                if nested_text:
                    text_parts.append(nested_text)
            else:
                # Skip nested structural units; they will be handled separately
                if child.tail:
                    text_parts.append(child.tail.strip())
            continue

        # For <ref> elements: preserve their text content (like "section 1561")
        # but don't recurse into children to avoid duplication
        if child_tag == "ref":
            # Get text content of ref element itself
            ref_text_parts = []
            if child.text:
                ref_text_parts.append(child.text.strip())
            # Also get text from direct children (but not deeply nested)
            for ref_child in child:
                if ref_child.text:
                    ref_text_parts.append(ref_child.text.strip())
                if ref_child.tail:
                    ref_text_parts.append(ref_child.tail.strip())
            if ref_text_parts:
                text_parts.append(" ".join(ref_text_parts))
            # Preserve tail after ref
            if child.tail:
                text_parts.append(child.tail.strip())
            continue

        child_text = get_text_content(child, include_nested_structural=include_nested_structural)
        if child_text:
            text_parts.append(child_text)

        # Add tail text (text after the element)
        if child.tail:
            text_parts.append(child.tail.strip())

    # Join and normalize whitespace
    result = " ".join(text_parts)
    # Normalize whitespace: collapse multiple spaces/newlines to single space
    result = re.sub(r'\s+', ' ', result)
    return result.strip()


def extract_identifier(elem: ET.Element) -> Optional[str]:
    """Extract identifier attribute from element."""
    return elem.get("identifier", "")


def parse_identifier(identifier: str) -> Dict:
    """
    Parse a USLM identifier into hierarchy and subsection path.

    Example identifier:
        /us/usc/t26/stA/ch1/schB/ptI/spt2/s6511/a/1/A

    Returns a dict:
    {
        "title": 26,
        "section": "6511",
        "hierarchy": {
            "title": 26,
            "subtitle": "A",
            "chapter": "1",
            "subchapter": "B",
            "part": "I",
            "subpart": "2",
            "section": "6511",
        },
        "subsection_path": "(a)(1)(A)",
        "section_id": "26 USC § 6511",
    }
    """
    # Default result for malformed identifiers
    result = {
        "title": 26,
        "section": None,
        "hierarchy": {
            "title": 26,
            "subtitle": None,
            "chapter": None,
            "subchapter": None,
            "part": None,
            "subpart": None,
            "section": None,
        },
        "subsection_path": "",
        "section_id": "26 USC § ?",
    }

    if not identifier:
        return result

    parts = identifier.strip("/").split("/")
    # Expect something like: us / usc / t26 / ...
    try:
        t_index = parts.index("t26")
    except ValueError:
        return result

    i = t_index + 1
    hierarchy = result["hierarchy"].copy()

    code_map = {
        "st": "subtitle",
        "ch": "chapter",
        "sch": "subchapter",
        "pt": "part",
        "spt": "subpart",
    }

    section = None

    # Parse hierarchy codes until we hit section ("s") or run out
    while i < len(parts):
        tok = parts[i]
        if tok in code_map and i + 1 < len(parts):
            hierarchy[code_map[tok]] = parts[i + 1]
            i += 2
            continue
        if tok == "s" and i + 1 < len(parts):
            section = parts[i + 1]
            hierarchy["section"] = section
            i += 2
            break
        # Unexpected token – stop early
        break

    path_tokens = parts[i:]
    subsection_path = "".join(f"({p})" for p in path_tokens)

    section_id = f"26 USC § {section}" if section is not None else "26 USC § ?"

    result.update(
        {
            "title": 26,
            "section": section,
            "hierarchy": hierarchy,
            "subsection_path": subsection_path,
            "section_id": section_id,
        }
    )
    return result


def extract_heading(section_elem: ET.Element) -> Optional[str]:
    """Extract heading from a *section* element."""
    heading_elem = section_elem.find(f".//{USLM_NS}heading")
    if heading_elem is not None:
        return get_text_content(heading_elem)
    return None




def iter_element_records(xml_path: Path):
    """
    Walk the XML document and yield records at section and subsection level only.
    
    For subsections: combines ALL content within the subsection (ignoring
    paragraph/subparagraph/clause tags) into one record.
    For sections: only processed if they have no subsections.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    count = 0

    # Iterate over top-level sections
    for section_elem in root.iter(f"{USLM_NS}section"):
        section_identifier = extract_identifier(section_elem) or ""
        section_heading = extract_heading(section_elem)
        
        # Check if this section has subsections
        subsections = [
            child for child in section_elem
            if _strip_ns(child.tag) == "subsection"
        ]
        
        if subsections:
            # Process each subsection (combining all content within it)
            for subsection_elem in subsections:
                identifier = extract_identifier(subsection_elem) or section_identifier
                id_info = parse_identifier(identifier)
                
                # Extract all text from subsection, INCLUDING nested paragraphs/subparagraphs/clauses
                raw_text = get_raw_text_content(subsection_elem)
                text = get_text_content(subsection_elem, include_nested_structural=True)
                
                if not text:
                    continue
                
                count += 1
                yield {
                    "id": str(count),
                    "hierarchy": id_info["hierarchy"],
                    "subsection_path": id_info["subsection_path"],
                    "heading": section_heading,
                    "element_type": "subsection",
                    "identifier": identifier,
                    "raw_text": raw_text,
                    "text": text,
                }
        else:
            # Section has no subsections - process the section itself
            identifier = extract_identifier(section_elem) or section_identifier
            id_info = parse_identifier(identifier)
            
            raw_text = get_raw_text_content(section_elem)
            text = get_text_content(section_elem, include_nested_structural=True)
            
            if not text:
                continue
            
            count += 1
            yield {
                "id": str(count),
                "hierarchy": id_info["hierarchy"],
                "subsection_path": id_info["subsection_path"],
                "heading": section_heading,
                "element_type": "section",
                "identifier": identifier,
                "raw_text": raw_text,
                "text": text,
            }




def main():
    """
    Entry point: parse the fixed Title 26 XML file and write JSONL output.

    This script is intentionally non-parameterized for now: it always reads
    ``raw_data/title26.xml`` (relative to this package) and writes
    ``processed_data/parsed.jsonl``.
    """
    root_dir = Path(__file__).resolve().parents[1]
    xml_path = root_dir / "raw_data" / "title26.xml"
    output_path = root_dir / "processed_data" / "parsed.jsonl"

    if not xml_path.exists():
        raise FileNotFoundError(f"XML file not found: {xml_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Parsing Title 26 XML from: {xml_path}")
    print(f"Writing element-level records to: {output_path}")

    count = 0
    with output_path.open("w", encoding="utf-8") as out_f:
        for record in iter_element_records(xml_path):
            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
            if count % 5000 == 0:
                print(f"Processed {count} elements...")

    print(f"Done. Wrote {count} elements to {output_path}")
    
    # Automatically generate formatted version
    formatted_output_path = output_path.parent / f"{output_path.stem}_formatted.jsonl"
    print(f"\nGenerating formatted version: {formatted_output_path}")
    format_as_pretty_jsonl(output_path, formatted_output_path)
    print(f"Formatted version saved to: {formatted_output_path}")


if __name__ == "__main__":
    main()
