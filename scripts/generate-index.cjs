#!/usr/bin/env node
/**
 * Generate the README skill index and the marketplace skill list from skill
 * frontmatter, so adding a skill touches one file instead of four.
 *
 *   node scripts/generate-index.cjs           write the generated files
 *   node scripts/generate-index.cjs --check   fail when the committed files are stale
 *
 * Each skill declares its own index metadata in its frontmatter:
 *
 *   category: <folder name>   subject folder; must match the parent directory
 *   title:    <display name>  heading shown in the README index
 *   summary:  <prose>         index table cell (first sentence) and section body
 *   say:      <example>       the "Say:" line
 *
 * The README block between the GENERATED markers is overwritten. The
 * marketplace file keeps its hand-written fields; only plugins[0].skills is
 * regenerated, and the whole file is re-serialized the same way
 * scripts/format.cjs does, so the two stay byte-identical.
 */
"use strict";

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const SKILLS_DIR = path.join(ROOT, "skills");
const README_PATH = path.join(ROOT, "README.md");
const MARKETPLACE_PATH = path.join(ROOT, ".claude-plugin", "marketplace.json");

const BEGIN = "<!-- BEGIN GENERATED: skills index -->";
const END = "<!-- END GENERATED: skills index -->";

/** Longest first sentence allowed in an index table cell. */
const MAX_CELL = 140;

/**
 * The category registry: display title and the one-line focus shown in the
 * index table. The order here is the order in the README. Adding a category
 * means adding a folder and an entry here.
 */
const CATEGORIES = [
  { id: "code", title: "Code", focus: "Write, run, and test code inside one language" },
  { id: "docs", title: "Docs", focus: "Write and improve documentation" },
  {
    id: "engineering",
    title: "Engineering",
    focus: "Build lean code and keep verification gates honest",
  },
  {
    id: "portability",
    title: "Portability",
    focus: "Code that runs on hosts that block execution",
  },
  { id: "review", title: "Review", focus: "Verdicts on finished work" },
  { id: "web", title: "Web", focus: "Apps that run in a browser" },
  {
    id: "workflow",
    title: "Workflow",
    focus: "Decide, plan, and report progress with you",
  },
];

/** Parse the YAML frontmatter of a SKILL.md into top-level scalar fields. */
function parseFrontmatter(text) {
  const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n/.exec(text);
  if (!match) return null;
  const lines = match[1].split("\n");
  const data = {};
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim() || line.trim().startsWith("#")) {
      i += 1;
      continue;
    }
    const key = /^([A-Za-z0-9_-]+):(.*)$/.exec(line);
    if (!key) {
      i += 1;
      continue;
    }
    const name = key[1];
    const rest = key[2].trim();
    if (rest === "") {
      // A nested map or an empty value: skip it and any indented children.
      i += 1;
      continue;
    }
    if (rest.startsWith(">") || rest.startsWith("|")) {
      const folded = rest.startsWith(">");
      i += 1;
      const block = [];
      let indent = null;
      while (i < lines.length) {
        const current = lines[i];
        if (!current.trim()) {
          block.push("");
          i += 1;
          continue;
        }
        const currentIndent = current.length - current.trimStart().length;
        if (currentIndent === 0) break;
        if (indent === null) indent = currentIndent;
        if (currentIndent < indent) break;
        block.push(current.slice(indent));
        i += 1;
      }
      while (block.length && block[block.length - 1] === "") block.pop();
      if (folded) {
        const paragraphs = [];
        let current = [];
        for (const piece of block) {
          if (piece === "") {
            paragraphs.push(current.join(" "));
            current = [];
          } else {
            current.push(piece);
          }
        }
        paragraphs.push(current.join(" "));
        data[name] = paragraphs.join("\n").trim();
      } else {
        data[name] = block.join("\n");
      }
      continue;
    }
    let value = rest;
    if (value.length >= 2 && value[0] === value[1] && (value[0] === '"' || value[0] === "'")) {
      value = value.slice(1, -1);
    }
    data[name] = value;
    i += 1;
  }
  return data;
}

/** First sentence of a summary, used as the index table cell. */
function firstSentence(text) {
  const match = /^[\s\S]*?[.!?](?=\s|$)/.exec(text);
  return (match ? match[0] : text).trim();
}

/** GitHub heading anchor for a category title. */
function anchor(title) {
  return title.toLowerCase().replace(/[^a-z0-9 -]/g, "").replace(/ /g, "-");
}

/** Escape a value so it cannot break out of a Markdown table cell. */
function cell(text) {
  return text.replace(/\|/g, "\\|").replace(/\s+/g, " ").trim();
}

/** Every skill directory under skills/, sorted by category then name. */
function discoverSkills() {
  const skills = [];
  const categories = fs
    .readdirSync(SKILLS_DIR, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
  for (const category of categories) {
    const categoryDir = path.join(SKILLS_DIR, category);
    const names = fs
      .readdirSync(categoryDir, { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => entry.name)
      .sort();
    for (const name of names) {
      const file = path.join(categoryDir, name, "SKILL.md");
      if (!fs.existsSync(file)) continue;
      skills.push({ category, name, file });
    }
  }
  return skills;
}

/** Read and validate every skill's frontmatter; throws on the first problem. */
function loadSkills() {
  const known = new Set(CATEGORIES.map((category) => category.id));
  const skills = discoverSkills();
  const onDisk = new Set(skills.map((skill) => skill.category));
  for (const category of onDisk) {
    if (!known.has(category)) {
      throw new Error(
        `category '${category}' is not in the registry in scripts/generate-index.cjs; add it there`,
      );
    }
  }
  for (const category of known) {
    if (!onDisk.has(category)) {
      throw new Error(`category '${category}' is in the registry but has no folder under skills/`);
    }
  }
  return skills.map((skill) => {
    const text = fs.readFileSync(skill.file, "utf8");
    const front = parseFrontmatter(text);
    const where = `skills/${skill.category}/${skill.name}/SKILL.md`;
    if (!front) throw new Error(`${where}: missing YAML frontmatter block`);
    if (front.name !== skill.name) {
      throw new Error(`${where}: name '${front.name || ""}' must match the directory '${skill.name}'`);
    }
    if (!front.category) throw new Error(`${where}: frontmatter missing 'category'`);
    if (front.category !== skill.category) {
      throw new Error(
        `${where}: category '${front.category}' must match the parent directory '${skill.category}'`,
      );
    }
    for (const field of ["title", "summary", "say"]) {
      if (!front[field]) throw new Error(`${where}: frontmatter missing '${field}'`);
    }
    if (front.title.includes("\n")) throw new Error(`${where}: title must be a single line`);
    const lead = firstSentence(front.summary);
    if (lead.length > MAX_CELL) {
      throw new Error(
        `${where}: first summary sentence is ${lead.length} chars, max ${MAX_CELL}; shorten it`,
      );
    }
    if (lead.length < 10) throw new Error(`${where}: summary needs a first sentence of at least 10 chars`);
    return {
      category: skill.category,
      name: skill.name,
      title: front.title,
      summary: front.summary,
      say: front.say,
      lead,
    };
  });
}

/** Render the README index block. */
function renderIndex(skills) {
  const lines = ["## Categories", ""];
  lines.push("| Category | Skills | Focus |");
  lines.push("|---|---:|---|");
  for (const category of CATEGORIES) {
    const count = skills.filter((skill) => skill.category === category.id).length;
    lines.push(`| [${category.title}](#${anchor(category.title)}) | ${count} | ${category.focus} |`);
  }
  lines.push("");
  lines.push("## Skill Index");
  for (const category of CATEGORIES) {
    const inCategory = skills.filter((skill) => skill.category === category.id);
    if (inCategory.length === 0) continue;
    lines.push("");
    lines.push(`### ${category.title}`);
    lines.push("");
    lines.push(`\`skills/${category.id}/\``);
    lines.push("");
    lines.push("| Skill | Description |");
    lines.push("|---|---|");
    for (const skill of inCategory) {
      lines.push(
        `| [\`${skill.name}\`](skills/${skill.category}/${skill.name}/SKILL.md) | ${cell(skill.lead)} |`,
      );
    }
    for (const skill of inCategory) {
      lines.push("");
      lines.push(`#### ${skill.title}`);
      lines.push("");
      lines.push("```");
      lines.push(`npx skills add agentmemoir/skills --skill ${skill.name} --global -y`);
      lines.push("```");
      lines.push("");
      lines.push(skill.summary);
      lines.push("");
      lines.push(`Say: ${skill.say}`);
    }
  }
  return lines.join("\n");
}

/** Replace the generated block in a README, keeping everything else. */
function replaceBlock(text, body) {
  const start = text.indexOf(BEGIN);
  const stop = text.indexOf(END);
  if (start === -1) throw new Error(`README.md has no ${BEGIN} marker`);
  if (stop === -1) throw new Error(`README.md has no ${END} marker`);
  if (stop < start) throw new Error("README.md has the END marker before the BEGIN marker");
  return `${text.slice(0, start + BEGIN.length)}\n\n${body}\n\n${text.slice(stop)}`;
}

/** Re-serialize the marketplace file with a regenerated skills list. */
function renderMarketplace(raw, skills) {
  const marketplace = JSON.parse(raw);
  if (!marketplace.plugins || !marketplace.plugins[0]) {
    throw new Error(".claude-plugin/marketplace.json has no plugins[0]");
  }
  marketplace.plugins[0].skills = skills.map(
    (skill) => `./skills/${skill.category}/${skill.name}`,
  );
  return `${JSON.stringify(marketplace, null, 2)}\n`;
}

function main() {
  const check = process.argv.includes("--check");
  const skills = loadSkills();
  const readmeRaw = fs.readFileSync(README_PATH, "utf8");
  const readmeNext = replaceBlock(readmeRaw, renderIndex(skills));
  const marketplaceRaw = fs.readFileSync(MARKETPLACE_PATH, "utf8");
  const marketplaceNext = renderMarketplace(marketplaceRaw, skills);

  const stale = [];
  if (readmeNext !== readmeRaw) stale.push("README.md skill index");
  if (marketplaceNext !== marketplaceRaw) stale.push(".claude-plugin/marketplace.json");

  if (check) {
    if (stale.length > 0) {
      for (const file of stale) console.error(`FAIL ${file} is out of date with the skill frontmatter`);
      console.error("run: npm run generate:index");
      process.exit(1);
    }
    console.log("OK index (README + marketplace match the skill frontmatter)");
    return;
  }

  if (readmeNext !== readmeRaw) {
    fs.writeFileSync(README_PATH, readmeNext);
    console.log("wrote README.md skill index");
  }
  if (marketplaceNext !== marketplaceRaw) {
    fs.writeFileSync(MARKETPLACE_PATH, marketplaceNext);
    console.log("wrote .claude-plugin/marketplace.json");
  }
  if (stale.length === 0) console.log("OK index (already up to date)");
  else console.log(`OK index (${skills.length} skills)`);
}

try {
  main();
} catch (error) {
  console.error(`FAIL index: ${error && error.message ? error.message : error}`);
  process.exit(1);
}
