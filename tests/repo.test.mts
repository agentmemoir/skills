// Structural invariants of the collection: skills, indexes, and the package
// manifest. These are cheap, deterministic checks that catch drift between the
// source of truth (skills/<category>/<name>/SKILL.md) and the places that must mirror it.

import { test, before } from "node:test";
import assert from "node:assert/strict";
import * as path from "node:path";
import { listSkillDirs, readText, readJson, frontmatter, frontmatterValue, run } from "./helpers.mts";

type PackageJson = {
  name?: string;
  version?: string;
  license?: string;
  bin?: Record<string, string>;
  scripts?: Record<string, string>;
};

type Marketplace = {
  plugins: Array<{ skills: string[] }>;
};

let pkg: PackageJson;
let marketplace: Marketplace;
let skillDirs: string[];

before(async (): Promise<void> => {
  pkg = await readJson<PackageJson>("package.json");
  marketplace = await readJson<Marketplace>(".claude-plugin/marketplace.json");
  skillDirs = await listSkillDirs();
});

test("every skill directory has a SKILL.md", async (): Promise<void> => {
  for (const rel of skillDirs) {
    const text = await readText(`skills/${rel}/SKILL.md`);
    assert.ok(text.length > 0, `skills/${rel}/SKILL.md is empty`);
  }
});

test("each SKILL.md frontmatter name matches its directory", async (): Promise<void> => {
  for (const rel of skillDirs) {
    const name = path.basename(rel);
    const text = await readText(`skills/${rel}/SKILL.md`);
    const front = frontmatter(text);
    assert.ok(front, `skills/${rel}/SKILL.md has no frontmatter`);
    assert.equal(frontmatterValue(front, "name"), name, `skills/${rel}/SKILL.md: name must equal the directory`);
    const description = frontmatterValue(front, "description");
    assert.ok(description, `skills/${rel}/SKILL.md: description is empty`);
    assert.ok(description.length <= 1024, `skills/${rel}/SKILL.md: description exceeds 1024 characters`);
  }
});

test("every skill declares the index metadata the generator reads", async (): Promise<void> => {
  for (const rel of skillDirs) {
    const text = await readText(`skills/${rel}/SKILL.md`);
    const front = frontmatter(text);
    assert.ok(front, `skills/${rel}/SKILL.md has no frontmatter`);
    const category = frontmatterValue(front, "category");
    assert.ok(category, `skills/${rel}/SKILL.md: category is empty`);
    assert.equal(
      category,
      path.dirname(rel),
      `skills/${rel}/SKILL.md: category must equal the parent directory`,
    );
    for (const field of ["title", "summary", "say"]) {
      assert.ok(
        frontmatterValue(front, field),
        `skills/${rel}/SKILL.md: ${field} is empty`,
      );
    }
  }
});

test("the generated index matches the skill frontmatter", async (): Promise<void> => {
  const result = await run("node", ["scripts/generate-index.cjs", "--check"]);
  assert.equal(
    result.status,
    0,
    `README index and marketplace are stale, run "npm run generate:index"\n${result.stdout}${result.stderr}`,
  );
});

test("marketplace lists exactly the skill directories, alphabetically", (): void => {
  const listed = marketplace.plugins[0].skills.map((entry) => path.normalize(entry.replace(/^\.\//, "")));
  assert.deepEqual(listed, skillDirs.map((rel) => path.join("skills", rel)));
  assert.deepEqual(listed, [...listed].sort(), "marketplace skills must stay alphabetical");
});

test("package.json bin targets exist and start with a node shebang", async (): Promise<void> => {
  for (const [name, rel] of Object.entries(pkg.bin || {})) {
    const text = await readText(rel);
    const first = text.split("\n", 1)[0];
    assert.equal(first, "#!/usr/bin/env node", `bin ${name}: ${rel} must start with a node shebang`);
  }
});

test("package.json declares name, version, license, and a test script", (): void => {
  assert.equal(typeof pkg.name, "string");
  assert.equal(typeof pkg.version, "string");
  assert.ok(pkg.license, "package.json is missing a license");
  assert.ok(pkg.scripts && pkg.scripts.test, "package.json is missing scripts.test");
});
