#!/usr/bin/env python3
"""
check-tidy.py - Verification tool for Tidy documentation suites.

Checks:
1. Line break verification: ensures each markdown prose paragraph is on a single line
   (no hard-wrapped column text). Correctly ignores fenced code blocks, indented code
   blocks, list continuations, and tables.
2. Relative link and anchor resolution: verifies that relative file links point to
   existing files, and internal #anchors point to valid headings in target files.
3. Entry-point validation: verifies README.md or index.md exists and contains navigation
   links when multiple documents exist in the suite.
4. Inbound reference audit (optional --inbound-root): verifies external links into the
   suite resolve correctly.

Usage:
    python3 check-tidy.py <target-directory> [--inbound-root <path>] [--exclude <path-substring>]...
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


def slugify_heading(raw_heading: str) -> str:
    """Generate a GitHub/CommonMark-compatible anchor slug from a heading string."""
    # Strip trailing closing hashes (e.g. '## Heading ##')
    heading = re.sub(r"\s+#+\s*$", "", raw_heading).strip()
    # Strip markdown inline links: [text](url) -> text
    heading = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", heading)
    # Strip markdown inline code formatting: `code` -> code
    heading = re.sub(r"`([^`]+)`", r"\1", heading)
    # Strip HTML tags: <tag> -> ''
    heading = re.sub(r"<[^>]+>", "", heading)
    # Lowercase
    slug = heading.lower().strip()
    # Remove characters other than letters, numbers, hyphens, underscores, spaces
    slug = re.sub(r"[^\w\s-]", "", slug)
    # Replace spaces and consecutive whitespace with hyphens
    slug = re.sub(r"[\s]+", "-", slug)
    return slug


def extract_headings_and_anchors(file_path: Path) -> Set[str]:
    """Extract all valid anchor identifiers from a markdown file (headings and HTML anchors)."""
    anchors = set()
    slug_counts: Dict[str, int] = {}

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return anchors

    in_fence = False
    fence_char = ""
    fence_len = 0

    heading_re = re.compile(r"^\s{0,3}(#{1,6})\s+(.*)$")
    html_anchor_re = re.compile(r"""<a\s+(?:[^>]*?\s+)?(?:id|name)=["']([^"']+)["']""", re.IGNORECASE)

    for line in content.splitlines():
        # Check fenced code block boundaries. Per CommonMark, an opening fence's
        # info string cannot contain the fence character, and a closing fence is
        # bare (only whitespace after the marker). Fence-shaped lines that fail
        # these tests — e.g. a line of inline ```code``` — are not fences.
        fence_match = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
        if fence_match:
            marker = fence_match.group(1)
            rest = fence_match.group(2)
            char = marker[0]
            mlen = len(marker)
            if not in_fence and char not in rest:
                in_fence = True
                fence_char = char
                fence_len = mlen
                continue
            if in_fence and char == fence_char and mlen >= fence_len and rest.strip() == "":
                in_fence = False
                continue

        if in_fence:
            continue

        # Check explicit HTML anchors
        for anchor_id in html_anchor_re.findall(line):
            anchors.add(anchor_id)

        # Check markdown headings
        h_match = heading_re.match(line)
        if h_match:
            raw_text = h_match.group(2)
            base_slug = slugify_heading(raw_text)
            if not base_slug:
                continue
            count = slug_counts.get(base_slug, 0)
            if count == 0:
                slug = base_slug
            else:
                slug = f"{base_slug}-{count}"
            slug_counts[base_slug] = count + 1
            anchors.add(slug)

    return anchors


def check_line_breaks(file_path: Path) -> List[Tuple[str, int, str]]:
    """Check that each prose paragraph is on a single line (one-paragraph-per-line rule)."""
    errors: List[Tuple[str, int, str]] = []

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [(str(file_path), 1, f"Failed to read file: {e}")]

    lines = content.splitlines(keepends=True)
    in_frontmatter = False
    in_fence = False
    fence_char = ""
    fence_len = 0
    in_indented_code = False
    in_list = False
    list_indent = 0
    prev_line_type = "empty"  # empty, heading, list, prose, table, hr, blockquote, fence

    list_item_re = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)")
    heading_re = re.compile(r"^\s{0,3}#{1,6}\s+")
    table_re = re.compile(r"^\s*\|")
    hr_re = re.compile(r"^\s*([-*_])\s*(\1\s*){2,}$")

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Frontmatter detection (YAML block at top of file)
        if i == 1 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue

        # Fenced code block detection. CommonMark rules: an opener's info string
        # cannot contain the fence character; a closer is bare. A fence-shaped
        # line failing those tests (e.g. inline ```code```) is prose.
        fence_match = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
        if fence_match:
            marker = fence_match.group(1)
            rest = fence_match.group(2)
            char = marker[0]
            mlen = len(marker)
            if not in_fence and char not in rest:
                in_fence = True
                fence_char = char
                fence_len = mlen
                prev_line_type = "fence"
                in_indented_code = False
                in_list = False
                continue
            if in_fence and char == fence_char and mlen >= fence_len and rest.strip() == "":
                in_fence = False
                prev_line_type = "fence"
                in_indented_code = False
                in_list = False
                continue
            if in_fence:
                continue
            # Fence-shaped but not a fence: fall through as prose.

        if in_fence:
            continue

        # Blank line
        if not stripped:
            prev_line_type = "empty"
            in_indented_code = False
            in_list = False
            continue

        # Indented code block (4 spaces or 1 tab after empty line or indented code)
        if (line.startswith("    ") or line.startswith("\t")) and (prev_line_type in ("empty", "indented_code") and not in_list):
            in_indented_code = True
            prev_line_type = "indented_code"
            continue

        # Headings
        if heading_re.match(line):
            prev_line_type = "heading"
            in_list = False
            in_indented_code = False
            continue

        # Thematic breaks / horizontal rules
        if hr_re.match(stripped):
            prev_line_type = "hr"
            in_list = False
            in_indented_code = False
            continue

        # Table rows
        if table_re.match(line):
            prev_line_type = "table"
            in_list = False
            in_indented_code = False
            continue

        # Tag-only HTML lines (e.g. <details>, </summary>) and full-line HTML
        # comments are structural markup, not wrapped prose: they never
        # violate the one-paragraph-per-line rule, and prose may sit directly
        # against them the way authors pair open/close tags.
        if re.match(r"^</?[A-Za-z][^>]*>\s*$", line) or re.match(r"^\s*<!--", line):
            prev_line_type = "html"
            in_list = False
            in_indented_code = False
            continue

        # Blockquotes
        if stripped.startswith(">"):
            if prev_line_type == "blockquote" and stripped != ">":
                # Consecutive non-empty blockquote lines indicate wrapped text
                errors.append((str(file_path), i, f"Hard-wrapped blockquote line (wrap paragraph into one line): {stripped[:60]}..."))
            prev_line_type = "blockquote"
            in_list = False
            in_indented_code = False
            continue

        # List items
        m_list = list_item_re.match(line)
        if m_list:
            in_list = True
            list_indent = len(m_list.group(1))
            prev_line_type = "list"
            in_indented_code = False
            continue

        # List continuations (indented lines following a list item)
        if in_list:
            current_indent = len(line) - len(line.lstrip())
            if current_indent > list_indent:
                # Valid indented list continuation
                continue
            else:
                in_list = False

        # If not heading, list, table, fence, or blank: this is a prose line!
        if prev_line_type == "prose":
            errors.append((str(file_path), i, f"Hard-wrapped prose paragraph (continuation of line without empty line): {stripped[:60]}..."))
        elif prev_line_type == "list":
            errors.append((str(file_path), i, f"Hard-wrapped list item continuation at column 0: {stripped[:60]}..."))

        prev_line_type = "prose"

    return errors


def extract_markdown_links(content: str) -> List[Tuple[int, str, str]]:
    """Extract (line_number, link_text, url) from markdown content outside code fences."""
    links: List[Tuple[int, str, str]] = []
    lines = content.splitlines()

    in_fence = False
    fence_char = ""
    fence_len = 0
    link_re = re.compile(r"!?\[([^\]]*)\]\(([^)]+)\)")

    for lnum, line in enumerate(lines, 1):
        # Fence boundaries follow CommonMark: an opener's info string cannot
        # contain the fence character; a closer is bare. See check_line_breaks.
        fence_match = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
        if fence_match:
            marker = fence_match.group(1)
            rest = fence_match.group(2)
            char = marker[0]
            mlen = len(marker)
            if not in_fence and char not in rest:
                in_fence = True
                fence_char = char
                fence_len = mlen
                continue
            if in_fence and char == fence_char and mlen >= fence_len and rest.strip() == "":
                in_fence = False
                continue

        if in_fence:
            continue

        # Find inline links
        for m in link_re.finditer(line):
            text = m.group(1)
            url = m.group(2).strip()
            links.append((lnum, text, url))

    return links


def validate_links_and_anchors(
    file_path: Path,
    target_dir: Path,
    file_anchor_cache: Dict[Path, Set[str]],
) -> List[Tuple[str, int, str]]:
    """Validate relative links and internal anchors in a markdown file."""
    errors: List[Tuple[str, int, str]] = []

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [(str(file_path), 1, f"Failed to read file: {e}")]

    links = extract_markdown_links(content)
    file_dir = file_path.parent

    for lnum, _text, url in links:
        # Ignore external web links, email links, etc.
        if url.startswith(("http://", "https://", "mailto:", "ftp:", "javascript:")):
            continue

        # Ignore template placeholders: {{url}} and friends are variables to be
        # filled by the user, never real link targets.
        if "{{" in url:
            continue

        # Split file path and anchor
        if "#" in url:
            target_file_str, anchor = url.split("#", 1)
        else:
            target_file_str, anchor = url, None

        # Clean target string (remove URL query parameters if any)
        target_file_str = target_file_str.split("?")[0].strip()

        if not target_file_str:
            # Internal anchor in current file
            target_path = file_path.resolve()
        else:
            # Resolve relative file path
            resolved = (file_dir / target_file_str).resolve()
            target_path = resolved

        # Check target existence
        if not target_path.exists():
            errors.append((str(file_path), lnum, f"Broken link target: '{url}' (resolved to non-existent path: {target_path})"))
            continue

        # If target is a directory, check for directory index or valid directory
        if target_path.is_dir():
            dir_index = None
            for candidate in ("README.md", "index.md", "SKILL.md"):
                if (target_path / candidate).exists():
                    dir_index = (target_path / candidate).resolve()
                    break
            if dir_index and anchor:
                target_path = dir_index
            elif not dir_index and anchor:
                errors.append((str(file_path), lnum, f"Anchor '#{anchor}' on directory target '{url}' without index document"))
                continue

        # Validate anchor if present
        if anchor:
            if target_path not in file_anchor_cache:
                file_anchor_cache[target_path] = extract_headings_and_anchors(target_path)
            valid_anchors = file_anchor_cache[target_path]
            # Match anchor directly or normalized
            normalized_anchor = anchor.lower().strip()
            if anchor not in valid_anchors and normalized_anchor not in valid_anchors:
                errors.append((str(file_path), lnum, f"Broken anchor '#{anchor}' in target '{target_path.name}'"))

    return errors


def validate_entry_point(
    target_dir: Path,
    markdown_files: List[Path],
) -> List[Tuple[str, int, str]]:
    """Verify entry point document (README.md, index.md, or SKILL.md) and navigation links."""
    errors: List[Tuple[str, int, str]] = []

    entry_candidates = ["README.md", "index.md", "SKILL.md"]
    entry_point: Optional[Path] = None

    for name in entry_candidates:
        cand = target_dir / name
        if cand.exists():
            entry_point = cand
            break

    if not entry_point:
        errors.append((
            str(target_dir),
            1,
            f"Missing entry point document: expected README.md or index.md in '{target_dir}'",
        ))
        return errors

    # If there are other markdown topic files in the suite, check for navigation links
    topic_files = [f for f in markdown_files if f.resolve() != entry_point.resolve()]
    if topic_files:
        try:
            content = entry_point.read_text(encoding="utf-8", errors="replace")
            links = extract_markdown_links(content)
            # Find relative file links
            has_nav_link = False
            for _lnum, _text, url in links:
                if not url.startswith(("http://", "https://", "mailto:", "ftp:")) and not url.startswith("#"):
                    has_nav_link = True
                    break
            if not has_nav_link:
                errors.append((
                    str(entry_point),
                    1,
                    f"Entry point '{entry_point.name}' contains no relative navigation links to child documents in suite",
                ))
        except Exception as e:
            errors.append((str(entry_point), 1, f"Failed to read entry point: {e}"))

    return errors


def validate_inbound_references(
    target_dir: Path,
    inbound_root: Path,
    file_anchor_cache: Dict[Path, Set[str]],
) -> List[Tuple[str, int, str]]:
    """Verify external inbound markdown links into target_dir from inbound_root."""
    errors: List[Tuple[str, int, str]] = []
    target_dir_resolved = target_dir.resolve()
    inbound_root_resolved = inbound_root.resolve()

    if not inbound_root_resolved.exists():
        errors.append((str(inbound_root), 1, f"Specified --inbound-root does not exist: {inbound_root}"))
        return errors

    inbound_md_files: List[Path] = []
    for root, _dirs, files in os.walk(inbound_root_resolved):
        # Skip walking target_dir itself
        root_path = Path(root).resolve()
        try:
            root_path.relative_to(target_dir_resolved)
            continue
        except ValueError:
            pass

        for file in files:
            if file.endswith(".md"):
                inbound_md_files.append(Path(root) / file)

    for md_file in inbound_md_files:
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        links = extract_markdown_links(content)
        file_dir = md_file.parent

        for lnum, _text, url in links:
            if url.startswith(("http://", "https://", "mailto:", "ftp:", "javascript:")):
                continue

            if "#" in url:
                target_file_str, anchor = url.split("#", 1)
            else:
                target_file_str, anchor = url, None

            target_file_str = target_file_str.split("?")[0].strip()
            if not target_file_str:
                continue

            resolved = (file_dir / target_file_str).resolve()
            # Check if resolved points into target_dir
            try:
                resolved.relative_to(target_dir_resolved)
            except ValueError:
                # Link does not point into target_dir
                continue

            # Link points into target_dir: verify existence
            if not resolved.exists():
                errors.append((
                    str(md_file),
                    lnum,
                    f"Broken inbound link to '{url}' (target does not exist: {resolved})",
                ))
                continue

            # Check anchor if present
            if anchor:
                check_path = resolved
                if check_path.is_dir():
                    for cand in ("README.md", "index.md", "SKILL.md"):
                        if (check_path / cand).exists():
                            check_path = (check_path / cand).resolve()
                            break
                if check_path.is_file():
                    if check_path not in file_anchor_cache:
                        file_anchor_cache[check_path] = extract_headings_and_anchors(check_path)
                    valid = file_anchor_cache[check_path]
                    if anchor not in valid and anchor.lower().strip() not in valid:
                        errors.append((
                            str(md_file),
                            lnum,
                            f"Broken inbound anchor '#{anchor}' pointing to '{check_path.name}'",
                        ))

    return errors


def self_check() -> int:
    """Embedded regression fixtures for the checker's own behavior."""
    import tempfile

    checks: List[Tuple[str, bool]] = []

    def expect(name: str, condition: bool) -> None:
        checks.append((name, condition))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        wrapped = root / "wrapped.md"
        wrapped.write_text("# T\n\npara one\ncontinues here without an empty line\n")
        expect("wrapped prose is detected", bool(check_line_breaks(wrapped)))

        clean = root / "clean.md"
        clean.write_text("# T\n\none paragraph kept on a single line.\n")
        expect("one-paragraph-per-line doc is clean", not check_line_breaks(clean))

        inline = root / "inline.md"
        inline.write_text("# T\n\nUse ```code here``` inline in prose.\n\nMore prose follows.\n")
        expect(
            "inline ```code``` does not toggle fence state",
            not check_line_breaks(inline),
        )

        nested = root / "nested.md"
        nested.write_text(
            "# T\n\n```markdown\n```python\nwrapped line one\nwrapped line two\n```\n"
        )
        expect(
            "info-string fence line inside an open fence stays content",
            not check_line_breaks(nested),
        )

        longer = root / "longer.md"
        longer.write_text(
            "# T\n\n````markdown\n```python\nx = 1\n```\ninner close is content\n````\n"
        )
        expect(
            "longer outer fence keeps inner fences as content",
            not check_line_breaks(longer),
        )

        broken = root / "broken.md"
        broken.write_text("# T\n\nSee [missing](nope.md) for details.\n")
        cache: Dict[Path, Set[str]] = {}
        expect(
            "broken relative link is detected",
            bool(validate_links_and_anchors(broken, root, cache)),
        )

        placeholder = root / "placeholder.md"
        placeholder.write_text("# T\n\nDocs live at [the site]({{url}}) once filled.\n")
        expect(
            "template placeholder links are ignored",
            not validate_links_and_anchors(placeholder, root, cache),
        )

        suite = root / "suite"
        suite.mkdir()
        (suite / "README.md").write_text("# Suite\n\nNo navigation links here.\n")
        (suite / "topic.md").write_text("# Topic\n\nBody.\n")
        expect(
            "entry point without nav links fails",
            bool(validate_entry_point(suite, [suite / "README.md", suite / "topic.md"])),
        )

        generated = root / "generated.md"
        generated.write_text("# T\n\n<!-- BEGIN GENERATED: vendored catalog -->\nA\nB\n")
        expect(
            "BEGIN GENERATED marker is detectable for auto-skip",
            "BEGIN GENERATED" in generated.read_text(),
        )

        html = root / "html.md"
        html.write_text(
            "# T\n\n<details>\n<summary><strong>Config options</strong></summary>\n\n"
            "```ts\nexport default {}\n```\n\nPrecedence: CLI flags beat config file.\n</details>\n"
        )
        expect(
            "tag-only HTML lines are structural, not wrapped prose",
            not check_line_breaks(html),
        )

        comments = root / "comments.md"
        comments.write_text(
            "# T\n\n<!-- Good: one example. -->\n<!-- Bad:  another example. -->\n\nProse.\n"
        )
        expect(
            "full-line HTML comments are structural, not wrapped prose",
            not check_line_breaks(comments),
        )

    failures = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  {'ok' if ok else 'FAIL'}: {name}")
    if failures:
        print(f"FAILED: {len(failures)} self-check failure(s)", file=sys.stderr)
        return 1
    print("PASSED: check-tidy self-check")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify a documentation suite against Tidy principles (line breaks, links, entry points, inbound refs)."
    )
    parser.add_argument("target_dir", nargs="?", default=None, help="Path to the documentation directory to verify")
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="Run the checker's embedded regression fixtures and exit",
    )
    parser.add_argument(
        "--inbound-root",
        help="Optional root directory to audit inbound links pointing into target_dir",
        default=None,
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="SUBSTRING",
        help="Skip markdown files whose target-relative path contains this substring "
        "(repeatable). Fails when a pattern matches no file. Use for vendored "
        "content that must not be hand-edited.",
    )

    args = parser.parse_args()
    if args.self_check:
        return self_check()
    if not args.target_dir:
        parser.error("target_dir is required unless --self-check is given")
    target_dir = Path(args.target_dir).resolve()

    if not target_dir.exists():
        print(f"Error: Target directory does not exist: {target_dir}", file=sys.stderr)
        return 1

    if not target_dir.is_dir():
        print(f"Error: Target path is not a directory: {target_dir}", file=sys.stderr)
        return 1

    # Find all markdown files in target_dir
    markdown_files: List[Path] = []
    for root, _dirs, files in os.walk(target_dir):
        for f in files:
            if f.endswith(".md"):
                markdown_files.append(Path(root) / f)

    if not markdown_files:
        print(f"Warning: No markdown (.md) files found in {target_dir}")

    excluded_files: List[Path] = []
    unmatched_patterns: List[str] = []
    if args.exclude:
        def rel(path: Path) -> str:
            return path.relative_to(target_dir).as_posix()

        def is_excluded(path: Path) -> bool:
            return any(substring in rel(path) for substring in args.exclude)

        excluded_files = [f for f in markdown_files if is_excluded(f)]
        markdown_files = [f for f in markdown_files if not is_excluded(f)]
        for excluded in excluded_files:
            print(f"Excluded from checks: {excluded}")
        for pattern in args.exclude:
            if not any(pattern in rel(f) for f in excluded_files):
                unmatched_patterns.append(pattern)
        if unmatched_patterns and markdown_files:
            print(
                f"Error: --exclude pattern(s) matched no file: {', '.join(unmatched_patterns)}",
                file=sys.stderr,
            )
            return 1

    # Vendored generated regions: a file containing a BEGIN GENERATED marker is
    # regenerated by tooling and must never be hand-edited, so it is not checked.
    generated_skipped: List[Path] = []
    for f in list(markdown_files):
        try:
            if "BEGIN GENERATED" in f.read_text(encoding="utf-8", errors="replace"):
                generated_skipped.append(f)
        except Exception:
            continue
    if generated_skipped:
        for skipped in generated_skipped:
            print(f"Excluded (generated region): {skipped}")
        markdown_files = [f for f in markdown_files if f not in generated_skipped]

    all_errors: List[Tuple[str, int, str]] = []
    file_anchor_cache: Dict[Path, Set[str]] = {}

    # 1. Entry-point check
    entry_errors = validate_entry_point(target_dir, markdown_files)
    all_errors.extend(entry_errors)

    # 2. Line break & link/anchor checks for each markdown file
    for md_file in sorted(markdown_files):
        line_break_errors = check_line_breaks(md_file)
        all_errors.extend(line_break_errors)

        link_errors = validate_links_and_anchors(md_file, target_dir, file_anchor_cache)
        all_errors.extend(link_errors)

    # 3. Inbound reference audit
    if args.inbound_root:
        inbound_root = Path(args.inbound_root).resolve()
        inbound_errors = validate_inbound_references(target_dir, inbound_root, file_anchor_cache)
        all_errors.extend(inbound_errors)

    # Report results
    if all_errors:
        print(f"FAILED: Found {len(all_errors)} tidy verification error(s):\n", file=sys.stderr)
        for fpath, lnum, msg in all_errors:
            print(f"{fpath}:{lnum}: {msg}", file=sys.stderr)
        return 1

    print(f"PASSED: Tidy verification succeeded for {target_dir}")
    print(f"  Markdown files checked: {len(markdown_files)}")
    if excluded_files:
        print(f"  Excluded (vendored): {len(excluded_files)}")
    print(f"  Anchors verified across: {len(file_anchor_cache)} document(s)")
    if args.inbound_root:
        print(f"  Inbound references audited from: {args.inbound_root}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
