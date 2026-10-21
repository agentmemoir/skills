---
name: sql-guidelines
description: Enforces Postgres SQL formatting conventions for case, layout, naming, and types. Use when writing or reviewing SQL.
category: code
title: SQL guidelines
summary: >-
  Postgres formatting conventions for case, layout, naming, and types. Keywords uppercase, type names
  lowercase (except `TIMESTAMP WITH TIME ZONE`), snake_case identifiers, 2-space indent, types at
  column 96, plus naming, type, table, function, and index rules. Applies to every SQL
  change.
say: >-
  "Write (or review) this SQL using
  sql-guidelines."
license: MIT
---

# SQL Guidelines

Postgres formatting conventions for case, layout, naming, and types. Follow them on every SQL change.

## When to Use

- Use when: writing or reviewing any SQL (`CREATE TABLE`, `CREATE INDEX`, functions, views, queries).
- Do not use for: non-SQL code.

## Case

- SQL keywords in **UPPERCASE** (`SELECT`, `FROM`, `WHERE`, `INSERT`, `RETURNS`, etc.).
- Data type names in **lowercase** (`uuid`, `text`, `bigint`, `integer`, `numeric`, `jsonb`) — the only exception is `TIMESTAMP WITH TIME ZONE`, which stays uppercase.
- Identifiers in **snake_case**.

## Formatting

- Indent body contents with 2 spaces.
- `CREATE TABLE`: the table name ends the first line, the opening paren goes alone on the next line, one column per line, closing `);` alone:
  ```sql
  CREATE TABLE subscriptions
  (
    ...
  );
  ```
- Column alignment is global, never per table or per block: right-pad the column name with spaces so the type starts at column 96 (1-based) in every `CREATE TABLE`. With the 2-space indent and 1 separating space this means padding the name to 92 characters. If indent + name already reaches column 95 or beyond, fall back to a single space. Constraints after the type are separated by single spaces.
- `CREATE [UNIQUE] INDEX`: the index name ends the first line, `ON ...` goes on the next line:
  ```sql
  CREATE UNIQUE INDEX subscriptions_vault_address_uix
  ON subscriptions (LOWER(vault_address));
  ```
- `WHERE` shares its line with the start of its condition:
  ```sql
  WHERE status <> 'canceled';
  ```
- Functions use this exact shape: name line, paren alone, one parameter per line with types at column 96 (same padding rule as table columns), `)` alone, `RETURNS <type>` on the next line, then `AS`, `$$`, body, `$$`, `LANGUAGE plpgsql;` each on their own lines. `CREATE OR REPLACE FUNCTION`, `(`, `)`, `RETURNS`, `AS`, `$$`, `BEGIN`, `END;`, `$$`, and `LANGUAGE plpgsql;` all start at column 1 with no indent. Parameters and the `DECLARE` line use 2-space indent. Statements inside `BEGIN` / `END` use 2-space indent, plus 2 per nesting level. Note: examples below carry an extra 2-space markdown list indent that is not part of the SQL — `  BEGIN` in the raw file means `BEGIN` in SQL:
  ```sql
  CREATE OR REPLACE FUNCTION insert_depositor_enrichments
  (
    _entries                                                                                     jsonb,
    _collected_by                                                                                text
  )
  RETURNS integer
  AS
  $$
    DECLARE v_entry jsonb;
  BEGIN
    ...
  END;
  $$
  LANGUAGE plpgsql;
  ```
- No parameters means no paren block: keep `()` on the name line, never explode it into `(` / `)` lines:
  ```sql
  CREATE OR REPLACE FUNCTION do_something()
  RETURNS integer
  AS
  ```
- `RETURNS TABLE(...)` columns follow the same one-per-line, types-at-column-96 rule as parameters.
- `DECLARE` is the one exception to column 96: it shares its line with the first variable, and variables align per block. The `DECLARE` line itself uses 2-space indent (strip the extra markdown list indent in the raw file):
  ```sql
    DECLARE v_entry jsonb;
  ```
- Views put `AS` on its own line:
  ```sql
  CREATE OR REPLACE VIEW master_ledger_view
  AS
  SELECT ...
  ```

## Naming

| Thing | Convention | Example |
|---|---|---|
| Tables | plural `snake_case` | `subscriptions`, `payment_records` |
| Columns | `snake_case` | `wallet_address`, `account_address` |
| Indexes | `{table}_{column(s)}_{inx\|uix}` | `depositor_enrichments_account_inx` |
| Functions | `snake_case` | `insert_depositor_enrichments` |
| Parameters | `snake_case` with `_` prefix | `_entries`, `_collected_by` |
| Local variables | `snake_case` with `v_` prefix | `v_count` |

## Types

Use full type names only — **never shortcuts**:

| Correct | Wrong |
|---|---|
| `integer` | `int` |
| `numeric` | `float` |
| `double precision` | `float8` |
| `boolean` | `bool` |
| `text` | `varchar` |

| Data | PG Type |
|---|---|
| String / address | `text` |
| Blockchain heights, timestamps, amounts | `bigint` |
| Precise decimal / wei amounts | `numeric` |
| Timestamps | `TIMESTAMP WITH TIME ZONE` |

- Use `LOWER()` on text columns for case-insensitive lookups.
- Use `DEFAULT(NOW())` for `created_at` / `updated_at`.

## Tables

- Use `CREATE TABLE IF NOT EXISTS`.
- Every table gets `created_at` and optionally `updated_at`.

## Functions

- Use `CREATE OR REPLACE FUNCTION` with `LANGUAGE plpgsql`.
- Validate JSONB inputs with `jsonb_typeof` + `RAISE EXCEPTION`.
- Use `ON CONFLICT DO NOTHING` for insert-avoiding-duplicates.

## Indexes

- One index per query pattern. Name descriptively per the naming table above.
- Use `LOWER()` in index expressions on text columns.
- Use partial indexes (`WHERE status <> 'canceled'`) when most rows share the same status.

## Workflow

1. Step one: write the SQL following the case, formatting, naming, and type rules above.
2. Step two: apply the Tables, Functions, and Indexes conventions.
3. Verify: `(` alone under table/function names; types start at column 96 in tables, signatures, and `RETURNS TABLE`; `ON` on its own line; `WHERE` sharing its line with its condition; function shape name / `(` / params / `)` / `RETURNS` / `AS` / `$$` / body / `$$` / `LANGUAGE` with `BEGIN` / `END;` at column 1 and `DECLARE` plus body statements at 2-space indent; `DECLARE` sharing its line with the first variable; view `AS` alone; keywords uppercase, data types lowercase except `TIMESTAMP WITH TIME ZONE`; 2-space indent.
