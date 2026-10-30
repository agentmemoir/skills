#!/usr/bin/env python3
"""
blueprint.py - Automation engine for Blueprint Product Domain Specifications (PDS).

Automates generated artifacts:
1. glossary.md: compiles ubiquitous language from domains/*.md into single index.
2. README.md domain map: compiles DDD topology, context table, and mermaid diagram.
3. README.md navigation: compiles status, scope, and decision record index.
4. sync & restore: mirrors central suite to project folder and restores on clone.
5. migrate: scaffolds unit files, archives consumed next.json, and reports progress.

Usage:
    python3 blueprint.py generate <suite-dir>
    python3 blueprint.py sync <suite-dir> [--repo-root <path>]
    python3 blueprint.py restore <product> [--repo-root <path>]
    python3 blueprint.py migrate init --legacy <legacy-dir> --work <work-dir>
    python3 blueprint.py migrate status --work <work-dir>
    python3 blueprint.py migrate rollover --work <work-dir>
    python3 blueprint.py --self-check
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


def slugify(text: str) -> str:
    """Generate a clean slug for markdown anchors or filenames."""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s]+", "-", s)
    return s


def replace_generated_region(
    content: str, marker_name: str, new_body: str
) -> str:
    """Replace content between BEGIN GENERATED and END GENERATED markers."""
    pattern = re.compile(
        rf"(<!--\s*BEGIN GENERATED:\s*{re.escape(marker_name)}\s*-->\n)(.*?)(\n<!--\s*END GENERATED:\s*{re.escape(marker_name)}\s*-->)",
        re.DOTALL,
    )
    replacement = rf"\g<1>{new_body.strip()}\g<3>"
    if pattern.search(content):
        return pattern.sub(replacement, content)
    # If markers not present, return content unchanged
    return content


# -----------------------------------------------------------------------------
# 1. Glossary Generator
# -----------------------------------------------------------------------------

def extract_ubiquitous_terms(domain_file: Path) -> List[Dict[str, Any]]:
    """
    Extract terms defined in the domain file's 'Ubiquitous Language' section.
    Distinguishes whether the term has an explicit heading anchor or is a bullet definition.
    """
    terms: List[Dict[str, Any]] = []
    text = domain_file.read_text(encoding="utf-8")
    lines = text.splitlines()

    in_ubiquitous = False
    current_term: Optional[str] = None
    current_gloss: List[str] = []
    current_is_heading = False

    def flush_term():
        nonlocal current_term, current_gloss, current_is_heading
        if current_term:
            gloss_str = " ".join(current_gloss).strip()
            # Pick first sentence for gloss if long
            m = re.match(r"^(.*?[.!?])(\s+[A-Z0-9]|$)", gloss_str)
            if m:
                gloss_str = m.group(1).strip()
            term_slug = slugify(current_term)
            # Check if an explicit HTML anchor exists in the file for this term
            has_html_anchor = bool(
                re.search(rf'<(?:a|span|div)[^>]*(?:id|name)=["\']{re.escape(term_slug)}["\']', text, re.I)
            )
            terms.append({
                "term": current_term,
                "anchor": term_slug,
                "has_anchor": current_is_heading or has_html_anchor,
                "gloss": gloss_str or "Definition owned by bounded context.",
                "file": domain_file.name,
            })
            current_term = None
            current_gloss = []
            current_is_heading = False

    for line in lines:
        stripped = line.strip()
        if re.match(r"^##\s+Ubiquitous Language", stripped, re.IGNORECASE):
            in_ubiquitous = True
            continue
        elif in_ubiquitous and re.match(r"^##\s+", stripped):
            flush_term()
            in_ubiquitous = False
            break

        if not in_ubiquitous:
            continue

        # Pattern: ### Term
        heading_match = re.match(r"^###+\s+(.+)$", stripped)
        if heading_match:
            flush_term()
            current_term = heading_match.group(1).strip()
            current_is_heading = True
            continue

        # Pattern: - **Term** — Def or - **Term**: Def
        bullet_match = re.match(r"^[-*]\s+\*\*([^*]+)\*\*\s*[:—–-]\s*(.+)$", stripped)
        if bullet_match:
            flush_term()
            current_term = bullet_match.group(1).strip()
            current_gloss.append(bullet_match.group(2).strip())
            current_is_heading = False
            continue

        if current_term and stripped:
            current_gloss.append(stripped)

    flush_term()
    return terms


def generate_glossary(suite_dir: Path) -> Path:
    """Generate or update glossary.md from domain files."""
    domains_dir = suite_dir / "domains"
    glossary_file = suite_dir / "glossary.md"

    terms: List[Dict[str, Any]] = []
    if domains_dir.is_dir():
        for dfile in sorted(domains_dir.glob("*.md")):
            terms.extend(extract_ubiquitous_terms(dfile))

    # Sort terms alphabetically
    terms.sort(key=lambda t: t["term"].lower())

    list_lines = []
    for t in terms:
        # Only use anchor slug if the term corresponds to a real heading/anchor in the file
        if t["has_anchor"]:
            link = f"domains/{t['file']}#{t['anchor']}"
        else:
            link = f"domains/{t['file']}"
        list_lines.append(f"- [**{t['term']}**]({link}) — {t['gloss']}")

    generated_block = "\n".join(list_lines) if list_lines else "No ubiquitous terms recorded yet."

    if not glossary_file.exists():
        content = (
            "# Ubiquitous Language\n\n"
            "This index records every term across the product's bounded contexts. "
            "Each domain file owns the full definition of its terms; this gloss is an index pointer.\n\n"
            "<!-- BEGIN GENERATED: ubiquitous language -->\n"
            f"{generated_block}\n"
            "<!-- END GENERATED: ubiquitous language -->\n"
        )
        glossary_file.write_text(content, encoding="utf-8")
    else:
        existing = glossary_file.read_text(encoding="utf-8")
        if "BEGIN GENERATED: ubiquitous language" in existing:
            updated = replace_generated_region(existing, "ubiquitous language", generated_block)
        else:
            updated = (
                existing.rstrip()
                + "\n\n<!-- BEGIN GENERATED: ubiquitous language -->\n"
                + generated_block
                + "\n<!-- END GENERATED: ubiquitous language -->\n"
            )
        glossary_file.write_text(updated, encoding="utf-8")

    return glossary_file


# -----------------------------------------------------------------------------
# 2. Domain Map Generator
# -----------------------------------------------------------------------------

def extract_domain_metadata(domain_file: Path) -> Dict[str, Any]:
    """Extract context name, subdomain class, summary, status, and relationships."""
    text = domain_file.read_text(encoding="utf-8")
    lines = text.splitlines()

    title = domain_file.stem.capitalize()
    status = "draft"
    subdomain_class = "supporting"
    summary = ""
    relationships: List[str] = []

    # Check title
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            break

    # Check Status line
    for line in lines[:10]:
        m = re.match(r"^Status:\s*(draft|settled)", line.strip(), re.IGNORECASE)
        if m:
            status = m.group(1).lower()
            break

    # Check Subdomain Class
    class_match = re.search(r"\b(?:Subdomain\s+Class|Class):\s*(core|supporting|generic)\b", text, re.IGNORECASE)
    if class_match:
        subdomain_class = class_match.group(1).lower()

    # Check Purpose & Scope
    in_purpose = False
    purpose_lines = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^##\s+Purpose\s+&\s+Scope", stripped, re.IGNORECASE):
            in_purpose = True
            continue
        elif in_purpose and stripped.startswith("## "):
            break
        elif in_purpose and stripped:
            purpose_lines.append(stripped)

    if purpose_lines:
        first_sentence = " ".join(purpose_lines)
        sm = re.match(r"^(.*?[.!?])(\s+|$)", first_sentence)
        summary = sm.group(1).strip() if sm else first_sentence
    else:
        summary = f"Bounded context for {title}."

    # Check Relationships
    in_rel = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"^##\s+Relationships", stripped, re.IGNORECASE):
            in_rel = True
            continue
        elif in_rel and stripped.startswith("## "):
            break
        elif in_rel and stripped:
            relationships.append(stripped)

    return {
        "file": domain_file.name,
        "stem": domain_file.stem,
        "title": title,
        "status": status,
        "class": subdomain_class,
        "summary": summary,
        "relationships": relationships,
    }


def generate_domain_map_markdown(domains: List[Dict[str, Any]]) -> str:
    """Generate Markdown topology and Mermaid diagram for bounded contexts."""
    if not domains:
        return "No bounded contexts settled yet."

    # Table of contexts
    rows = ["| Bounded Context | Class | Status | Summary |", "|---|---|---|---|"]
    for d in domains:
        rows.append(f"| [{d['title']}](domains/{d['file']}) | `{d['class']}` | `{d['status']}` | {d['summary']} |")

    # Mermaid diagram
    diagram_lines = ["```mermaid", "flowchart TD"]
    for d in domains:
        clean_title = d["title"].replace('"', "'").replace("\\", "")
        diagram_lines.append(f"  {d['stem']}[\"{clean_title}\\n({d['class']})\"]")

    # Trace edge links from relationships
    edge_count = 0
    for d in domains:
        for rel in d["relationships"]:
            for target in domains:
                if target["stem"] != d["stem"] and (
                    target["stem"] in rel.lower() or target["title"].lower() in rel.lower()
                ):
                    diagram_lines.append(f"  {d['stem']} --> {target['stem']}")
                    edge_count += 1
                    break

    diagram_lines.append("```")

    parts = [
        "### Bounded Contexts",
        "\n".join(rows),
        "",
        "### Context Map Topology",
        "\n".join(diagram_lines),
    ]
    return "\n".join(parts)


# -----------------------------------------------------------------------------
# 3. Navigation Index Generator
# -----------------------------------------------------------------------------

def extract_decision_metadata(dec_file: Path) -> Dict[str, str]:
    """Extract metadata from decisions/NNNN-<slug>.md."""
    text = dec_file.read_text(encoding="utf-8")
    lines = text.splitlines()

    title = dec_file.stem
    date_str = ""
    summary = ""

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            break

    for line in lines[:10]:
        dm = re.match(r"^Date:\s*(\d{4}-\d{2}-\d{2})", line.strip())
        if dm:
            date_str = dm.group(1)
            break

    # Look for Decision & Drivers summary
    in_decision = False
    decision_lines = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^##\s+Decision\s+&\s+Drivers", stripped, re.IGNORECASE):
            in_decision = True
            continue
        elif in_decision and stripped.startswith("## "):
            break
        elif in_decision and stripped:
            decision_lines.append(stripped)

    if decision_lines:
        first_sentence = " ".join(decision_lines)
        sm = re.match(r"^(.*?[.!?])(\s+|$)", first_sentence)
        summary = sm.group(1).strip() if sm else first_sentence
    else:
        summary = "Decision record."

    return {
        "file": dec_file.name,
        "title": title,
        "date": date_str or "Unrecorded",
        "summary": summary,
    }


def generate_navigation_markdown(
    domains: List[Dict[str, Any]], decisions: List[Dict[str, str]]
) -> str:
    """Generate navigation index of domain specifications and decision records."""
    sections = []

    # Domain contexts
    if domains:
        sections.append("#### Specifications")
        d_rows = ["| Document | Status | Summary |", "|---|---|---|"]
        d_rows.append("| [Glossary](glossary.md) | `settled` | Ubiquitous language index. |")
        for d in domains:
            d_rows.append(f"| [{d['title']}](domains/{d['file']}) | `{d['status']}` | {d['summary']} |")
        sections.append("\n".join(d_rows))

    # Decision records
    if decisions:
        sections.append("#### Decision Records")
        dec_rows = ["| Record | Date | Summary |", "|---|---|---|"]
        for dec in decisions:
            dec_rows.append(f"| [{dec['title']}](decisions/{dec['file']}) | `{dec['date']}` | {dec['summary']} |")
        sections.append("\n".join(dec_rows))

    return "\n\n".join(sections) if sections else "No suite files recorded yet."


def update_readme_indexes(suite_dir: Path) -> Path:
    """Update domain map and navigation index in README.md (or index.md)."""
    # Detect entry file
    entry_file = suite_dir / "README.md"
    if not entry_file.exists() and (suite_dir / "index.md").exists():
        entry_file = suite_dir / "index.md"

    domains_dir = suite_dir / "domains"
    domains: List[Dict[str, Any]] = []
    if domains_dir.is_dir():
        for dfile in sorted(domains_dir.glob("*.md")):
            domains.append(extract_domain_metadata(dfile))

    decisions_dir = suite_dir / "decisions"
    decisions: List[Dict[str, str]] = []
    if decisions_dir.is_dir():
        for decfile in sorted(decisions_dir.glob("*.md")):
            decisions.append(extract_decision_metadata(decfile))

    map_markdown = generate_domain_map_markdown(domains)
    nav_markdown = generate_navigation_markdown(domains, decisions)

    if not entry_file.exists():
        product_title = suite_dir.name.capitalize()
        content = (
            f"# {product_title} Product Domain Specification\n\n"
            "## Purpose & Problem Statement\n\n"
            f"The {product_title} specification establishes domain boundaries, models, and rules.\n\n"
            "## Scope & Boundaries\n\n"
            "Defines product domains and business invariants independent of implementation technology.\n\n"
            "## Domain Map\n\n"
            "<!-- BEGIN GENERATED: domain map -->\n"
            f"{map_markdown}\n"
            "<!-- END GENERATED: domain map -->\n\n"
            "## Navigation Index & Reading Paths\n\n"
            "<!-- BEGIN GENERATED: navigation -->\n"
            f"{nav_markdown}\n"
            "<!-- END GENERATED: navigation -->\n"
        )
        entry_file.write_text(content, encoding="utf-8")
    else:
        text = entry_file.read_text(encoding="utf-8")
        if "BEGIN GENERATED: domain map" in text:
            text = replace_generated_region(text, "domain map", map_markdown)
        else:
            # Check if ## Domain Map already exists without markers
            map_heading_match = re.search(r"^##\s+Domain Map\b.*?(?=\n##\s+|\Z)", text, re.MULTILINE | re.DOTALL)
            replacement_map = (
                "## Domain Map\n\n<!-- BEGIN GENERATED: domain map -->\n"
                + map_markdown.strip()
                + "\n<!-- END GENERATED: domain map -->\n"
            )
            if map_heading_match:
                text = text[:map_heading_match.start()] + replacement_map + text[map_heading_match.end():]
            else:
                text = text.rstrip() + f"\n\n{replacement_map}"

        if "BEGIN GENERATED: navigation" in text:
            text = replace_generated_region(text, "navigation", nav_markdown)
        else:
            # Check if ## Navigation Index already exists without markers
            nav_heading_match = re.search(r"^##\s+Navigation Index\b.*?(?=\n##\s+|\Z)", text, re.MULTILINE | re.DOTALL)
            replacement_nav = (
                "## Navigation Index & Reading Paths\n\n<!-- BEGIN GENERATED: navigation -->\n"
                + nav_markdown.strip()
                + "\n<!-- END GENERATED: navigation -->\n"
            )
            if nav_heading_match:
                text = text[:nav_heading_match.start()] + replacement_nav + text[nav_heading_match.end():]
            else:
                text = text.rstrip() + f"\n\n{replacement_nav}"

        entry_file.write_text(text, encoding="utf-8")

    return entry_file


def generate_all(suite_dir: Path) -> Tuple[Path, Path]:
    """Regenerate glossary, domain map, and navigation index for the suite."""
    g = generate_glossary(suite_dir)
    r = update_readme_indexes(suite_dir)
    return g, r


# -----------------------------------------------------------------------------
# 4. Sync & Restore Tool
# -----------------------------------------------------------------------------

def resolve_repo_root(start_dir: Optional[Path] = None) -> Path:
    """Find the Git repository root."""
    d = (start_dir or Path.cwd()).resolve()
    while d != d.parent:
        if (d / ".git").exists():
            return d
        d = d.parent
    return Path.cwd().resolve()


def get_git_remote_slug(repo_root: Path) -> Tuple[str, str]:
    """Extract owner and repo name from git remote origin."""
    try:
        proc = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        url = proc.stdout.strip()
        # Handle git@github.com:owner/repo.git or https://github.com/owner/repo.git
        m = re.search(r"[:/]([^/]+)/([^/]+?)(?:\.git)?$", url)
        if m:
            return m.group(1), m.group(2)
    except Exception:
        pass
    return "local", repo_root.name


def sync_suite(suite_dir: Path, repo_root: Optional[Path] = None) -> Dict[str, int]:
    """
    Mirror central suite to project folder according to blueprint.json.
    Reports: {'new': n, 'overwritten': n, 'deleted': n}
    """
    settings_file = suite_dir / "blueprint.json"
    if not settings_file.exists():
        raise FileNotFoundError(f"Missing settings file: {settings_file}")

    with open(settings_file, "r", encoding="utf-8") as f:
        settings = json.load(f)

    sync_setting = settings.get("sync", "off").lower()
    if sync_setting == "off":
        return {"new": 0, "overwritten": 0, "deleted": 0}

    root = (repo_root or resolve_repo_root(suite_dir)).resolve()
    local_dir_rel = settings.get("local_dir")
    if not local_dir_rel:
        raise ValueError("blueprint.json has sync enabled but lacks local_dir")

    local_dir_clean = str(local_dir_rel).strip()
    if not local_dir_clean or local_dir_clean in (".", "./", "/"):
        raise ValueError(f"local_dir cannot be the repository root or empty: {local_dir_rel}")

    target_dir = (root / local_dir_clean).resolve()

    # Safety check: prevent escaping repository root and prevent repository root itself
    try:
        rel = target_dir.relative_to(root)
        if rel == Path(".") or target_dir == root:
            raise ValueError(f"local_dir cannot resolve to the repository root itself: {local_dir_rel}")
    except ValueError as e:
        if "cannot resolve to the repository root" in str(e):
            raise
        raise ValueError(f"local_dir escapes repository root: {local_dir_rel}")

    target_dir.mkdir(parents=True, exist_ok=True)

    counts = {"new": 0, "overwritten": 0, "deleted": 0}

    # Gather source files (excluding any PHILOSOPHY.md or temp files)
    source_files: Dict[str, Path] = {}
    for p in suite_dir.rglob("*"):
        if p.is_file():
            rel = p.relative_to(suite_dir)
            source_files[str(rel)] = p

    # Copy / Overwrite to target
    for rel_str, src_path in source_files.items():
        dest_path = target_dir / rel_str
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if dest_path.exists():
            if dest_path.read_bytes() != src_path.read_bytes():
                shutil.copy2(src_path, dest_path)
                counts["overwritten"] += 1
        else:
            shutil.copy2(src_path, dest_path)
            counts["new"] += 1

    # Delete extraneous files in target that do not exist in central suite
    for p in target_dir.rglob("*"):
        if p.is_file():
            # Never delete git internals or hidden system files
            if any(part.startswith(".git") for part in p.parts):
                continue
            rel = str(p.relative_to(target_dir))
            if rel not in source_files:
                p.unlink()
                counts["deleted"] += 1

    # Cleanup empty directories in target
    for dirpath, dirnames, filenames in os.walk(target_dir, topdown=False):
        dp = Path(dirpath)
        if dp != target_dir and not any(dp.iterdir()):
            dp.rmdir()

    return counts


def restore_suite(
    product: str,
    repo_root: Optional[Path] = None,
    central_base: Optional[Path] = None,
    owner: Optional[str] = None,
    repo: Optional[str] = None,
) -> int:
    """
    Restore a missing central suite from a local project directory.
    Returns number of files copied into central suite.
    """
    root = (repo_root or resolve_repo_root()).resolve()
    if not owner or not repo:
        auto_owner, auto_repo = get_git_remote_slug(root)
        owner = owner or auto_owner
        repo = repo or auto_repo
    base = central_base or (Path.home() / ".agentmemoir" / owner / repo / "blueprints")
    central_suite = base / product

    # Guard: if central suite already has an entry point, central wins
    if (central_suite / "README.md").exists() or (central_suite / "index.md").exists():
        raise RuntimeError("Central suite already has an entry point; restore aborted.")

    # Scan root for candidate suite
    candidate_dir: Optional[Path] = None

    for candidate in root.rglob("blueprint.json"):
        # Ignore .git or ignored folders
        if any(part.startswith(".") for part in candidate.parts):
            continue
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("product") == product:
                candidate_dir = candidate.parent
                break
        except Exception:
            continue

    if not candidate_dir:
        # Fallback check: look for entry point + glossary.md + domains/
        for p in root.rglob("glossary.md"):
            if any(part.startswith(".") for part in p.parts):
                continue
            parent = p.parent
            if (parent / "domains").is_dir() and (
                (parent / "README.md").exists() or (parent / "index.md").exists()
            ):
                if parent.name == product:
                    candidate_dir = parent
                    break

    if not candidate_dir or not candidate_dir.is_dir():
        raise FileNotFoundError(f"No local candidate suite found matching product '{product}'")

    central_suite.mkdir(parents=True, exist_ok=True)
    copied_count = 0

    for src_path in candidate_dir.rglob("*"):
        if src_path.is_file():
            rel = src_path.relative_to(candidate_dir)
            dest = central_suite / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dest)
            copied_count += 1

    return copied_count


# -----------------------------------------------------------------------------
# 5. Migration Helper
# -----------------------------------------------------------------------------

def migrate_init(legacy_dir: Path, working_dir: Path) -> List[Path]:
    """Scan legacy documents and scaffold initial unit work files."""
    if not legacy_dir.is_dir():
        raise NotADirectoryError(f"Legacy directory not found: {legacy_dir}")

    working_dir.mkdir(parents=True, exist_ok=True)
    unit_files: List[Path] = []
    deliverables = []

    for item in sorted(legacy_dir.glob("*.md")):
        slug = item.stem.lower()
        if slug in ("readme", "index"):
            continue
        unit_data = {
            "unit": slug,
            "status": "pending",
            "sources": [str(item)],
            "targets": [f"domains/{slug}.md"],
            "invariants": [],
            "verification": "",
        }
        ufile = working_dir / f"{slug}.json"
        ufile.write_text(json.dumps(unit_data, indent=2), encoding="utf-8")
        unit_files.append(ufile)
        deliverables.append({
            "name": f"{slug.capitalize()} context",
            "sources": [str(item)],
            "targets": [f"domains/{slug}.md"],
            "description": f"Migrate legacy {item.name} into {slug} bounded context.",
        })

    next_file = working_dir / "next.json"
    if not next_file.exists() and deliverables:
        next_data = {
            "session_scope": f"migrate-{deliverables[0]['targets'][0].replace('domains/', '').replace('.md', '')}",
            "status": "ready",
            "deliverables": deliverables[:2],  # Take first batch
            "invariants_to_preserve": ["A settled rule survives every migration step."],
        }
        next_file.write_text(json.dumps(next_data, indent=2), encoding="utf-8")

    return unit_files


def migrate_status(working_dir: Path) -> Dict[str, Any]:
    """Read all unit files in working_dir and report counts and deliverables."""
    if not working_dir.is_dir():
        return {"total": 0, "counts": {}, "units": []}

    counts = {"pending": 0, "in_progress": 0, "migrated": 0, "verified": 0, "blocked": 0}
    units = []

    for ufile in sorted(working_dir.glob("*.json")):
        if ufile.name == "next.json":
            continue
        try:
            with open(ufile, "r", encoding="utf-8") as f:
                data = json.load(f)
            st = data.get("status", "pending")
            counts[st] = counts.get(st, 0) + 1
            units.append({"unit": data.get("unit", ufile.stem), "status": st})
        except Exception:
            continue

    total = sum(counts.values())
    return {"total": total, "counts": counts, "units": units}


def migrate_rollover(
    working_dir: Path,
    consumed_base: Optional[Path] = None,
    repo_root: Optional[Path] = None,
) -> Path:
    """
    Archive consumed next.json and construct new next.json from remaining units.
    """
    next_file = working_dir / "next.json"
    if not next_file.exists():
        raise FileNotFoundError(f"Missing {next_file}")

    root = (repo_root or resolve_repo_root(working_dir)).resolve()
    owner, repo = get_git_remote_slug(root)
    consumed_dir = consumed_base or (Path.home() / ".agentmemoir" / owner / repo / "migration-consumed")
    consumed_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.date.today().isoformat()
    archive_name = f"{today}-next.json"
    archive_path = consumed_dir / archive_name
    counter = 1
    while archive_path.exists():
        archive_path = consumed_dir / f"{today}-next-{counter}.json"
        counter += 1

    shutil.move(str(next_file), str(archive_path))

    # Look for units that are in_progress, blocked, or pending
    next_deliverables = []
    for ufile in sorted(working_dir.glob("*.json")):
        if ufile.name == "next.json":
            continue
        try:
            with open(ufile, "r", encoding="utf-8") as f:
                udata = json.load(f)
            status = udata.get("status", "pending")
            if status in ("pending", "in_progress", "blocked"):
                next_deliverables.append({
                    "name": f"{udata.get('unit', '').capitalize()} context",
                    "sources": udata.get("sources", []),
                    "targets": udata.get("targets", []),
                    "description": f"Carry-over / continue migration for {udata.get('unit')}.",
                })
        except Exception:
            continue

    if next_deliverables:
        new_next = {
            "session_scope": f"migrate-{next_deliverables[0]['name'].lower().replace(' ', '-')}",
            "status": "ready",
            "deliverables": next_deliverables[:2],
            "invariants_to_preserve": ["A settled rule survives every migration step."],
        }
    else:
        new_next = {
            "session_scope": "migration-complete",
            "status": "done",
            "deliverables": [],
            "invariants_to_preserve": [],
        }

    next_file.write_text(json.dumps(new_next, indent=2), encoding="utf-8")
    return archive_path


# -----------------------------------------------------------------------------
# 6. Deep Structural AST & Integrity Validator
# -----------------------------------------------------------------------------

def validate_suite(suite_dir: Path) -> List[str]:
    """
    Perform deep structural AST validation of a Blueprint PDS suite.
    Returns a list of error strings; an empty list indicates full compliance.
    """
    errors: List[str] = []

    # 1. blueprint.json
    settings_file = suite_dir / "blueprint.json"
    if not settings_file.exists():
        errors.append("Missing required settings file: blueprint.json")
    else:
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
            if not settings.get("product"):
                errors.append("blueprint.json: missing 'product' slug")
            sync_val = settings.get("sync")
            if sync_val not in ("on", "off", "custom"):
                errors.append(f"blueprint.json: invalid 'sync' value '{sync_val}', must be on, off, or custom")
            if sync_val in ("on", "custom"):
                local_dir = settings.get("local_dir")
                if not local_dir:
                    errors.append("blueprint.json: 'local_dir' is required when sync is on or custom")
                elif str(local_dir).strip() in (".", "./", "/"):
                    errors.append("blueprint.json: 'local_dir' cannot be repo root or empty")
            if not settings.get("updated"):
                errors.append("blueprint.json: missing 'updated' date string")
        except json.JSONDecodeError as e:
            errors.append(f"blueprint.json is invalid JSON: {e}")

    # 2. Entry point (README.md or index.md)
    entry_file = suite_dir / "README.md"
    if not entry_file.exists() and (suite_dir / "index.md").exists():
        entry_file = suite_dir / "index.md"

    if not entry_file.exists():
        errors.append("Missing suite entry point: README.md (or index.md)")
    else:
        text = entry_file.read_text(encoding="utf-8")
        req_sections = [
            "Purpose & Problem Statement",
            "Scope & Boundaries",
            "Domain Map",
            "Navigation Index",
        ]
        for sec in req_sections:
            if not re.search(rf"^##\s+{re.escape(sec)}", text, re.MULTILINE | re.IGNORECASE):
                errors.append(f"{entry_file.name}: missing required section '## {sec}'")

    # 3. Domains
    domains_dir = suite_dir / "domains"
    domain_files = list(domains_dir.glob("*.md")) if domains_dir.is_dir() else []
    if not domain_files:
        errors.append("Missing or empty 'domains/' directory: at least one bounded context required")

    domain_headings: Dict[str, Set[str]] = {}
    domain_terms: Set[str] = set()

    for dfile in domain_files:
        dtext = dfile.read_text(encoding="utf-8")
        if not re.search(r"^#\s+.+", dtext, re.MULTILINE):
            errors.append(f"{dfile.name}: missing title '# <Title>'")
        if not re.search(r"^Status:\s*(draft|settled)", dtext, re.MULTILINE | re.IGNORECASE):
            errors.append(f"{dfile.name}: missing status line ('Status: draft' or 'Status: settled')")
        if not re.search(r"\b(?:Subdomain\s+Class|Class):\s*(core|supporting|generic)\b", dtext, re.IGNORECASE):
            errors.append(f"{dfile.name}: missing Subdomain Class ('Class: core|supporting|generic')")

        # Extract headings and anchors for link resolution
        headings = set()
        for line in dtext.splitlines():
            m = re.match(r"^#+\s+(.+)$", line.strip())
            if m:
                headings.add(slugify(m.group(1)))
            for id_m in re.finditer(r'<(?:a|span|div)[^>]*(?:id|name)=["\']([^"\']+)["\']', line, re.I):
                headings.add(id_m.group(1).lower())
        domain_headings[dfile.name] = headings

        # Check required sections
        d_req = [
            "Purpose & Scope",
            "Ubiquitous Language",
            "Concepts & Model",
            "Capabilities & Operations",
            "Rules & Invariants",
            "Relationships",
        ]
        for sec in d_req:
            if not re.search(rf"^##\s+{re.escape(sec)}", dtext, re.MULTILINE | re.IGNORECASE):
                errors.append(f"{dfile.name}: missing required section '## {sec}'")

        # Collect ubiquitous terms
        for t in extract_ubiquitous_terms(dfile):
            domain_terms.add(t["term"].lower())

    # 4. Glossary
    glossary_file = suite_dir / "glossary.md"
    if domain_terms and not glossary_file.exists():
        errors.append("Missing glossary.md for suite with ubiquitous terms")
    elif glossary_file.exists():
        gtext = glossary_file.read_text(encoding="utf-8")
        for target_file, target_slug in re.findall(r"domains/([\w-]+\.md)#([\w-]+)", gtext):
            if target_file not in domain_headings:
                errors.append(f"glossary.md: links to non-existent domain file 'domains/{target_file}'")
            elif target_slug not in domain_headings[target_file]:
                errors.append(f"glossary.md: broken anchor #{target_slug} in domains/{target_file}")

    # 5. Decisions
    decisions_dir = suite_dir / "decisions"
    if decisions_dir.is_dir():
        dec_files = sorted(decisions_dir.glob("*.md"))
        expected_num = 1
        for dec_file in dec_files:
            m = re.match(r"^(\d{4})-([\w-]+)\.md$", dec_file.name)
            if not m:
                errors.append(f"{dec_file.name}: invalid filename, must match NNNN-<slug>.md")
                continue
            num = int(m.group(1))
            if num != expected_num:
                errors.append(f"{dec_file.name}: non-monotonic decision number (expected {expected_num:04d}, got {num:04d})")
            expected_num = num + 1

            d_content = dec_file.read_text(encoding="utf-8")
            if not re.search(r"^Date:\s*\d{4}-\d{2}-\d{2}", d_content, re.MULTILINE):
                errors.append(f"{dec_file.name}: missing Date header ('Date: YYYY-MM-DD')")

    return errors


# -----------------------------------------------------------------------------
# 7. Self-Check (Automated Suite Verification)
# -----------------------------------------------------------------------------

def run_self_check() -> None:
    """Run built-in verification of generator, sync, restore, and migration tools."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        suite = root / "suite"
        suite.mkdir()
        domains = suite / "domains"
        domains.mkdir()
        decisions = suite / "decisions"
        decisions.mkdir()

        # 1. Test Domain files and Glossary generation (both headings and bullets)
        auth_doc = (
            "# Authentication Domain\n\n"
            "Status: settled\n\n"
            "Subdomain Class: core\n\n"
            "## Purpose & Scope\n\n"
            "Manages identity credentials, JWT tokens, and account access.\n\n"
            "## Ubiquitous Language\n\n"
            "### Token\n\n"
            "A signed cryptographic bearer token for API access.\n\n"
            "- **Credential** — Secret verification key owned by an identity.\n\n"
            "## Concepts & Model\n\n"
            "Entities and aggregates.\n\n"
            "## Capabilities & Operations\n\n"
            "Issuance and revocation.\n\n"
            "## Rules & Invariants\n\n"
            "Tokens expire in 1 hour.\n\n"
            "## Relationships\n\n"
            "Feeds downstream [Billing](domains/billing.md) context.\n"
        )
        (domains / "auth.md").write_text(auth_doc, encoding="utf-8")

        billing_doc = (
            "# Billing Domain\n\n"
            "Status: draft\n\n"
            "Subdomain Class: supporting\n\n"
            "## Purpose & Scope\n\n"
            "Manages invoice generation, customer payments, and charge lifecycle.\n\n"
            "## Ubiquitous Language\n\n"
            "- **Invoice**: A payable summary of charges due for customer orders.\n\n"
            "## Concepts & Model\n\n"
            "Invoice aggregates.\n\n"
            "## Capabilities & Operations\n\n"
            "Issue charges.\n\n"
            "## Rules & Invariants\n\n"
            "Invoices require valid line items.\n\n"
            "## Relationships\n\n"
            "Consumes identity from [Auth](domains/auth.md).\n"
        )
        (domains / "billing.md").write_text(billing_doc, encoding="utf-8")

        # 2. Test Decision Record
        dec_doc = (
            "# 0001 Use Stripe for Billing\n\n"
            "Date: 2026-10-30\n\n"
            "## Decision & Drivers\n\n"
            "We use Stripe checkout for PCI compliance.\n"
        )
        (decisions / "0001-use-stripe.md").write_text(dec_doc, encoding="utf-8")

        # 3. Test generate_all
        g_file, r_file = generate_all(suite)
        assert g_file.exists(), "glossary.md was not created"
        assert r_file.exists(), "README.md was not created"

        g_text = g_file.read_text(encoding="utf-8")
        assert "Token" in g_text and "Credential" in g_text and "Invoice" in g_text
        # Heading term has anchor
        assert "domains/auth.md#token" in g_text
        # Bullet term without heading does not have broken anchor
        assert "domains/auth.md" in g_text and "domains/billing.md" in g_text

        r_text = r_file.read_text(encoding="utf-8")
        assert "Authentication" in r_text and "Billing" in r_text
        assert "0001 Use Stripe for Billing" in r_text
        assert "flowchart TD" in r_text

        # Test duplicate section protection on re-generation
        generate_all(suite)
        r_text_after = r_file.read_text(encoding="utf-8")
        assert r_text_after.count("## Domain Map") == 1, "Duplicate ## Domain Map created"
        assert r_text_after.count("## Navigation Index") == 1, "Duplicate ## Navigation Index created"

        # 4. Test sync and sync safety guards
        mirror = root / "project-mirror"
        settings = {
            "product": "testprod",
            "entry_file": "README.md",
            "sync": "on",
            "local_dir": "project-mirror",
            "updated": "2026-10-31",
        }
        (suite / "blueprint.json").write_text(json.dumps(settings), encoding="utf-8")
        counts = sync_suite(suite, repo_root=root)
        assert counts["new"] >= 4, f"Sync expected >= 4 new files, got {counts}"
        assert (mirror / "glossary.md").exists()

        # Test repo-root guard: sync must reject "." or "/"
        bad_settings = dict(settings, local_dir=".")
        (suite / "blueprint.json").write_text(json.dumps(bad_settings), encoding="utf-8")
        try:
            sync_suite(suite, repo_root=root)
            assert False, "sync_suite should have rejected local_dir == '.'"
        except ValueError as err:
            assert "cannot be the repository root" in str(err) or "cannot resolve to the repository root" in str(err)
        # Restore good settings
        (suite / "blueprint.json").write_text(json.dumps(settings), encoding="utf-8")

        # 5. Test restore with explicit owner and repo
        central_test_dir = root / "central_blueprints"
        restored_count = restore_suite(
            "testprod",
            repo_root=root,
            central_base=central_test_dir,
            owner="myorg",
            repo="myrepo",
        )
        assert restored_count >= 4, f"Restore expected >= 4 files, got {restored_count}"
        assert (central_test_dir / "testprod" / "README.md").exists()

        # 6. Test migrate
        legacy_dir = root / "legacy_docs"
        legacy_dir.mkdir()
        (legacy_dir / "catalog.md").write_text("# Catalog\nProduct listing.", encoding="utf-8")
        (legacy_dir / "orders.md").write_text("# Orders\nOrder processing.", encoding="utf-8")

        work_dir = root / "migration_work"
        u_files = migrate_init(legacy_dir, work_dir)
        assert len(u_files) == 2, f"Expected 2 work units, got {len(u_files)}"
        status = migrate_status(work_dir)
        assert status["total"] == 2, f"Expected 2 units in status, got {status}"

        consumed_dir = root / "consumed"
        archive_path = migrate_rollover(work_dir, consumed_base=consumed_dir, repo_root=root)
        assert archive_path.exists(), "Archived next.json does not exist"
        assert (work_dir / "next.json").exists(), "Rolled over next.json does not exist"

        # 7. Test deep AST validate_suite
        val_errors = validate_suite(suite)
        assert len(val_errors) == 0, f"Expected clean validation, got errors: {val_errors}"

    print("blueprint.py: self-check passed successfully.")


# -----------------------------------------------------------------------------
# Main CLI Entrypoint
# -----------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Blueprint PDS automation engine.")
    parser.add_argument("--self-check", action="store_true", help="Run self-tests and exit.")

    subparsers = parser.add_subparsers(dest="command")

    # generate
    gen_parser = subparsers.add_parser("generate", help="Generate glossary, domain map, and nav index.")
    gen_parser.add_argument("suite_dir", type=Path, help="Path to central blueprint suite directory.")

    # validate
    val_parser = subparsers.add_parser("validate", help="Validate suite structural integrity and DDD compliance.")
    val_parser.add_argument("suite_dir", type=Path, help="Path to central blueprint suite directory.")

    # sync
    sync_parser = subparsers.add_parser("sync", help="Mirror central suite to project folder.")
    sync_parser.add_argument("suite_dir", type=Path, help="Path to central blueprint suite directory.")
    sync_parser.add_argument("--repo-root", type=Path, default=None, help="Repository root path.")

    # restore
    res_parser = subparsers.add_parser("restore", help="Restore central suite from project clone.")
    res_parser.add_argument("product", type=str, help="Product slug.")
    res_parser.add_argument("--repo-root", type=Path, default=None, help="Repository root path.")
    res_parser.add_argument("--owner", type=str, default=None, help="Owner slug.")
    res_parser.add_argument("--repo", type=str, default=None, help="Repository slug.")

    # migrate
    mig_parser = subparsers.add_parser("migrate", help="Migration helpers.")
    mig_sub = mig_parser.add_subparsers(dest="subcommand")

    init_p = mig_sub.add_parser("init", help="Scaffold initial unit work files from legacy directory.")
    init_p.add_argument("--legacy", type=Path, required=True, help="Legacy documents directory.")
    init_p.add_argument("--work", type=Path, required=True, help="Working directory for unit files.")

    stat_p = mig_sub.add_parser("status", help="Report status of migration units.")
    stat_p.add_argument("--work", type=Path, required=True, help="Working directory for unit files.")

    roll_p = mig_sub.add_parser("rollover", help="Archive next.json and construct next session scope.")
    roll_p.add_argument("--work", type=Path, required=True, help="Working directory for unit files.")

    args = parser.parse_args()

    if args.self_check:
        run_self_check()
        return 0

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "generate":
        g, r = generate_all(args.suite_dir.resolve())
        print(f"Generated {g} and {r}")
        return 0

    if args.command == "validate":
        errs = validate_suite(args.suite_dir.resolve())
        if errs:
            print(f"FAILED: {len(errs)} validation error(s) found in {args.suite_dir}:")
            for e in errs:
                print(f"  - {e}")
            return 1
        print(f"OK: Suite at {args.suite_dir} is fully compliant with PDS specification.")
        return 0

    if args.command == "sync":
        counts = sync_suite(args.suite_dir.resolve(), repo_root=args.repo_root)
        print(f"Sync complete: {counts['new']} new, {counts['overwritten']} overwritten, {counts['deleted']} deleted.")
        return 0

    if args.command == "restore":
        n = restore_suite(
            args.product,
            repo_root=args.repo_root,
            owner=args.owner,
            repo=args.repo,
        )
        print(f"Restored {n} files into central suite.")
        return 0

    if args.command == "migrate":
        if args.subcommand == "init":
            units = migrate_init(args.legacy.resolve(), args.work.resolve())
            print(f"Initialized {len(units)} migration units in {args.work}.")
            return 0
        elif args.subcommand == "status":
            st = migrate_status(args.work.resolve())
            print(f"Migration status: {st['counts']['verified']} verified, {st['counts']['migrated']} migrated, "
                  f"{st['counts']['in_progress']} in_progress, {st['counts']['blocked']} blocked, "
                  f"{st['counts']['pending']} pending (Total: {st['total']}).")
            return 0
        elif args.subcommand == "rollover":
            archive = migrate_rollover(args.work.resolve())
            print(f"Archived previous scope to {archive} and rolled over next.json.")
            return 0
        else:
            mig_parser.print_help()
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
