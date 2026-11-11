// The decisions example must stay a valid instance of the published schema, so
// the plan template, the reference docs, and the file cannot drift apart.
// The validator covers exactly the keywords the schema uses; if the schema
// grows a keyword, this test must grow with it.

import { test, before } from "node:test";
import assert from "node:assert/strict";
import { readJson } from "./helpers.mts";

type Schema = Record<string, unknown>;

const SCHEMA_PATH = "skills/review/modernizer/assets/dependency-decisions.schema.json";
const EXAMPLE_PATH = "skills/review/modernizer/assets/dependency-decisions.example.json";

let schema: Schema;
let example: unknown;

before(async (): Promise<void> => {
  schema = await readJson<Schema>(SCHEMA_PATH);
  example = await readJson<unknown>(EXAMPLE_PATH);
});

function lookup(root: Schema, ref: string): Schema {
  assert.ok(ref.startsWith("#/"), `unsupported $ref: ${ref}`);
  let node: unknown = root;
  for (const key of ref.slice(2).split("/")) {
    assert.ok(node && typeof node === "object", `unresolved $ref: ${ref}`);
    node = (node as Schema)[key];
  }
  assert.ok(node && typeof node === "object", `unresolved $ref: ${ref}`);
  return node as Schema;
}

function hasType(type: string, value: unknown): boolean {
  switch (type) {
    case "object":
      return typeof value === "object" && value !== null && !Array.isArray(value);
    case "array":
      return Array.isArray(value);
    case "string":
      return typeof value === "string";
    case "integer":
      return typeof value === "number" && Number.isInteger(value);
    case "number":
      return typeof value === "number";
    case "boolean":
      return typeof value === "boolean";
    case "null":
      return value === null;
    default:
      return false;
  }
}

function check(node: Schema, value: unknown, root: Schema, at: string, errors: string[]): void {
  if (typeof node.$ref === "string") {
    check(lookup(root, node.$ref), value, root, at, errors);
    return;
  }

  if (Array.isArray(node.oneOf)) {
    const results = node.oneOf.map((branch) => {
      const branchErrors: string[] = [];
      check(branch as Schema, value, root, at, branchErrors);
      return branchErrors;
    });
    const passing = results.filter((branchErrors) => branchErrors.length === 0);
    if (passing.length !== 1) {
      // Report why the closest branch failed, so a broken example is diagnosable.
      const fewest = results.reduce((best, current) =>
        current.length < best.length ? current : best,
      );
      errors.push(
        `${at}: matches ${passing.length} of ${node.oneOf.length} oneOf branches, expected exactly 1; closest branch: ${fewest.slice(0, 3).join("; ")}`,
      );
    }
    return;
  }

  if (typeof node.type === "string" && !hasType(node.type, value)) {
    errors.push(`${at}: expected ${node.type}, got ${Array.isArray(value) ? "array" : typeof value}`);
    return;
  }

  if (Array.isArray(node.enum) && !node.enum.includes(value)) {
    errors.push(`${at}: ${JSON.stringify(value)} is not one of ${JSON.stringify(node.enum)}`);
  }

  if (typeof value === "string") {
    if (typeof node.minLength === "number" && value.length < node.minLength) {
      errors.push(`${at}: shorter than minLength ${node.minLength}`);
    }
    if (node.format === "date" && !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
      errors.push(`${at}: ${JSON.stringify(value)} is not a YYYY-MM-DD date`);
    }
  }

  if (typeof value === "number" && typeof node.minimum === "number" && value < node.minimum) {
    errors.push(`${at}: below minimum ${node.minimum}`);
  }

  if (Array.isArray(value)) {
    if (typeof node.minItems === "number" && value.length < node.minItems) {
      errors.push(`${at}: has ${value.length} items, minItems is ${node.minItems}`);
    }
    if (node.items) {
      value.forEach((item, index) => check(node.items as Schema, item, root, `${at}[${index}]`, errors));
    }
  }

  if (value && typeof value === "object" && !Array.isArray(value)) {
    const object = value as Record<string, unknown>;
    const properties = (node.properties as Record<string, Schema> | undefined) ?? {};
    for (const key of (node.required as string[] | undefined) ?? []) {
      if (!(key in object)) errors.push(`${at}: missing required key "${key}"`);
    }
    for (const [key, child] of Object.entries(object)) {
      if (key in properties) {
        check(properties[key], child, root, `${at}.${key}`, errors);
      } else if (node.additionalProperties === false) {
        errors.push(`${at}: unexpected key "${key}"`);
      }
    }
  }
}

function collectRefs(node: unknown, refs: string[] = []): string[] {
  if (Array.isArray(node)) {
    for (const item of node) collectRefs(item, refs);
  } else if (node && typeof node === "object") {
    for (const [key, value] of Object.entries(node)) {
      if (key === "$ref" && typeof value === "string") refs.push(value);
      else collectRefs(value, refs);
    }
  }
  return refs;
}

test("every schema $ref resolves to a local definition", (): void => {
  const refs = collectRefs(schema);
  assert.ok(refs.length > 0, "expected the schema to use $ref");
  for (const ref of refs) {
    assert.doesNotThrow((): void => void lookup(schema, ref), `${SCHEMA_PATH}: ${ref} does not resolve`);
  }
});

test("the example satisfies the decisions schema", (): void => {
  const errors: string[] = [];
  check(schema, example, schema, "$", errors);
  assert.deepEqual(errors, [], `${EXAMPLE_PATH} does not satisfy ${SCHEMA_PATH}:\n${errors.join("\n")}`);
});

test("the validator rejects a bad decision state", (): void => {
  const broken = structuredClone(example) as { decisions: Array<Record<string, unknown>> };
  broken.decisions[0].status = "done";
  const errors: string[] = [];
  check(schema, broken, schema, "$", errors);
  assert.ok(
    errors.some((error) => error.includes("decisions[0].status")),
    `expected a status error, got:\n${errors.join("\n")}`,
  );
});
