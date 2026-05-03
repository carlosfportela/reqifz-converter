#!/usr/bin/env python3
"""
migrate_reqifz.py
-----------------
Migrates a ReqIFZ package exported from IBM DOORS Next Generation (DNG) 6.0.4
to a format compatible with IBM ELM 7.2.

What it does:
  1. Extracts the .reqifz (ZIP) package.
  2. Parses the embedded ReqIF XML file(s).
  3. Fixes XHTML/XML structural incompatibilities:
       - Removes block-level elements (tables, divs, etc.) nested inside <p> tags
         by promoting them to siblings.
       - Strips empty <p> tags left behind by the operation above.
  4. Re-packages everything (fixed XML + original binary attachments) into a
     new .reqifz file ready for import into ELM 7.2.

Usage:
    python migrate_reqifz.py <input.reqifz> [output.reqifz]

If output path is omitted, the script writes  <input>_migrated.reqifz
next to the original file.

Requirements: Python 3.8+  (no third-party libraries needed)
"""

import argparse
import copy
import logging
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# XHTML namespace as used by DNG in ReqIF XHTML content
XHTML_NS = "http://www.w3.org/1999/xhtml"

# Block-level tags that must NOT be children of <p>
BLOCK_TAGS = {
    f"{{{XHTML_NS}}}{tag}"
    for tag in (
        "table", "thead", "tbody", "tfoot", "tr", "th", "td",
        "div", "blockquote", "pre", "ul", "ol", "li",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "figure", "figcaption", "section", "article", "header", "footer",
    )
} | {
    # Also handle un-namespaced variants just in case
    tag for tag in (
        "table", "thead", "tbody", "tfoot", "tr", "th", "td",
        "div", "blockquote", "pre", "ul", "ol", "li",
    )
}

# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

def register_namespaces(xml_path: Path) -> None:
    """
    Pre-scan the XML file to register all namespace prefixes so that
    ElementTree preserves them (instead of rewriting as ns0, ns1, …).
    """
    events = ("start-ns",)
    for _, (prefix, uri) in ET.iterparse(str(xml_path), events=events):
        try:
            ET.register_namespace(prefix, uri)
        except ValueError:
            pass  # Some prefixes are reserved; ignore silently


def parse_xml(xml_path: Path) -> ET.ElementTree:
    register_namespaces(xml_path)
    return ET.parse(str(xml_path))


def write_xml(tree: ET.ElementTree, xml_path: Path) -> None:
    tree.write(
        str(xml_path),
        encoding="utf-8",
        xml_declaration=True,
    )


# ---------------------------------------------------------------------------
# XHTML fixing logic
# ---------------------------------------------------------------------------

def _tag_name(element: ET.Element) -> str:
    """Return the local tag name (without namespace)."""
    tag = element.tag
    if tag and tag[0] == "{":
        return tag.split("}", 1)[1]
    return tag


def _is_block(element: ET.Element) -> bool:
    return element.tag in BLOCK_TAGS


def _is_empty_p(element: ET.Element) -> bool:
    """True if <p> has no children, no text, and no tail (or whitespace only)."""
    p_tag = f"{{{XHTML_NS}}}p"
    plain_p = "p"
    if element.tag not in (p_tag, plain_p):
        return False
    has_text = bool(element.text and element.text.strip())
    has_children = len(element) > 0
    return not has_text and not has_children


def _split_p_around_blocks(p_elem: ET.Element) -> list[ET.Element]:
    """
    Given a <p> element that contains block-level children, split it into
    a sequence of elements:
      - text/inline content before the first block  → new <p>
      - the block element itself
      - text/inline content after the block (tail)  → new <p>
      - … repeat for each block child

    Returns a flat list of elements to replace the original <p>.
    """
    result: list[ET.Element] = []

    # We'll build a "current <p>" to collect inline content
    def new_p() -> ET.Element:
        return ET.Element(p_elem.tag, attrib=copy.deepcopy(p_elem.attrib))

    current_p = new_p()
    current_p.text = p_elem.text  # text before first child

    for child in list(p_elem):
        if _is_block(child):
            # Flush accumulated inline content as a <p> (if non-empty)
            if not _is_empty_p(current_p):
                result.append(current_p)
            # Promote the block element; its tail becomes the next <p>'s text
            tail_text = child.tail
            child.tail = None
            result.append(child)
            # Start a new <p> for the tail content
            current_p = new_p()
            current_p.text = tail_text
        else:
            # Inline child – move into the current <p>
            current_p.append(child)

    # Flush any remaining inline content
    if not _is_empty_p(current_p):
        result.append(current_p)

    return result


def fix_block_in_p(parent: ET.Element) -> int:
    """
    Recursively walk *parent*, fixing any <p> element that directly contains
    block-level children.  Returns the number of fixes applied.
    """
    fixes = 0
    i = 0
    while i < len(parent):
        child = parent[i]

        # First recurse into this child's own descendants
        fixes += fix_block_in_p(child)

        p_tag_ns = f"{{{XHTML_NS}}}p"
        p_tag_plain = "p"
        if child.tag in (p_tag_ns, p_tag_plain):
            has_block_child = any(_is_block(gc) for gc in child)
            if has_block_child:
                replacements = _split_p_around_blocks(child)
                # Replace the single <p> at position i with the replacement list
                parent.remove(child)
                for offset, elem in enumerate(replacements):
                    parent.insert(i + offset, elem)
                fixes += 1
                # Don't advance i – re-examine the same position
                # (the inserted elements may themselves need fixing)
                continue

        i += 1

    return fixes


def clean_reqif_xml(tree: ET.ElementTree) -> int:
    """
    Apply all XHTML fixes to the parsed ReqIF ElementTree.
    Returns total number of fixes.
    """
    root = tree.getroot()
    total_fixes = fix_block_in_p(root)
    log.info("Applied %d structural fix(es) to the ReqIF XML.", total_fixes)
    return total_fixes


# ---------------------------------------------------------------------------
# Image / attachment reference validation (informational only)
# ---------------------------------------------------------------------------

def audit_image_refs(tree: ET.ElementTree, available_files: set[str]) -> None:
    """
    Scan the XML for <img src="..."> references and warn about any that
    do not have a corresponding file in the archive.
    """
    img_tag_ns = f"{{{XHTML_NS}}}img"
    img_tag_plain = "img"
    root = tree.getroot()
    missing = []
    for img in root.iter():
        if img.tag in (img_tag_ns, img_tag_plain):
            src = img.get("src", "")
            if src:
                # Normalise: strip leading "./" or "/"
                normalized = src.lstrip("./").lstrip("/")
                if normalized and normalized not in available_files:
                    missing.append(src)
    if missing:
        log.warning(
            "%d image reference(s) in the XML have no matching file in the archive:",
            len(missing),
        )
        for ref in missing:
            log.warning("  Missing: %s", ref)
    else:
        log.info("All image references resolve to files present in the archive.")


# ---------------------------------------------------------------------------
# Main migration pipeline
# ---------------------------------------------------------------------------

def migrate(input_path: Path, output_path: Path) -> None:
    log.info("Input  : %s", input_path)
    log.info("Output : %s", output_path)

    if not input_path.exists():
        log.error("Input file not found: %s", input_path)
        sys.exit(1)

    if not zipfile.is_zipfile(input_path):
        log.error("Input file is not a valid ZIP/ReqIFZ archive.")
        sys.exit(1)

    with tempfile.TemporaryDirectory(prefix="reqifz_migrate_") as tmp_dir:
        tmp = Path(tmp_dir)
        extract_dir = tmp / "extracted"
        fixed_dir = tmp / "fixed"
        extract_dir.mkdir()
        fixed_dir.mkdir()

        # ── Step 1: Extract ──────────────────────────────────────────────
        log.info("Extracting archive …")
        with zipfile.ZipFile(input_path, "r") as zf:
            zf.extractall(extract_dir)
            archive_names = set(zf.namelist())

        log.info("Archive contains %d file(s).", len(archive_names))

        # ── Step 2: Identify ReqIF XML file(s) ──────────────────────────
        reqif_files = sorted(
            p for p in extract_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in (".reqif", ".xml")
        )

        if not reqif_files:
            log.error(
                "No .reqif or .xml file found inside the archive. "
                "Cannot continue."
            )
            sys.exit(1)

        log.info("Found %d ReqIF XML file(s): %s", len(reqif_files),
                 [f.name for f in reqif_files])

        # Collect all filenames in the archive for image audit
        available = {n.lstrip("./").lstrip("/") for n in archive_names}

        # ── Step 3: Fix each ReqIF XML ───────────────────────────────────
        total_fixes = 0
        for reqif_path in reqif_files:
            log.info("Processing: %s", reqif_path.name)
            tree = parse_xml(reqif_path)
            audit_image_refs(tree, available)
            fixes = clean_reqif_xml(tree)
            total_fixes += fixes

            # Write fixed XML to the fixed_dir, preserving sub-path
            rel = reqif_path.relative_to(extract_dir)
            dest = fixed_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            write_xml(tree, dest)
            log.info("Wrote fixed XML: %s", dest.name)

        # ── Step 4: Copy non-XML files unchanged ─────────────────────────
        for src_file in extract_dir.rglob("*"):
            if src_file.is_file() and src_file not in reqif_files:
                rel = src_file.relative_to(extract_dir)
                dest = fixed_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dest)

        # ── Step 5: Re-package into new .reqifz ──────────────────────────
        log.info("Re-packaging into %s …", output_path.name)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf_out:
            for f in sorted(fixed_dir.rglob("*")):
                if f.is_file():
                    arcname = f.relative_to(fixed_dir).as_posix()
                    zf_out.write(f, arcname)
                    log.debug("  Added: %s", arcname)

        size_kb = output_path.stat().st_size / 1024
        log.info(
            "Done. Output written: %s (%.1f KB) | Total fixes: %d",
            output_path,
            size_kb,
            total_fixes,
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Migrate a ReqIFZ file exported from IBM DNG 6.0.4 "
            "to be compatible with IBM ELM 7.2."
        )
    )
    parser.add_argument(
        "input",
        metavar="INPUT.reqifz",
        help="Path to the source .reqifz file.",
    )
    parser.add_argument(
        "output",
        metavar="OUTPUT.reqifz",
        nargs="?",
        default=None,
        help=(
            "Path for the migrated .reqifz output. "
            "Defaults to <input>_migrated.reqifz."
        ),
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    input_path = Path(args.input).resolve()

    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_path = input_path.with_name(
            input_path.stem + "_migrated" + input_path.suffix
        )

    migrate(input_path, output_path)


if __name__ == "__main__":
    main()
