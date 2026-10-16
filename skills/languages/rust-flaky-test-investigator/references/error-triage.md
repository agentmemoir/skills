# Error Triage — Decode the Failure Before You Hypothesise

The failing run already printed the answer, usually on one line. Read it before you read any source code.

Most wrong diagnoses of an intermittent test are stories about *mechanism* built from reading the wrong file, when the mechanism was named in the panic the whole time. `Error { code: ReadOnly, extended_code: 776 }` is not a symptom — it is a lookup that ends the investigation. This file is the lookup step, and it belongs before every hypothesis.

## The rule

Enumerate every distinct value the error carries, resolve each one to its documented meaning, then treat each resolved value as a **named** hypothesis. Then read the code path that emitted it. A code you have not matched against the line that produced it is still a hypothesis, however specific it looks.

## Procedure

1. **Get the raw output.** `RUST_BACKTRACE=1`, `RUST_LOG=debug`, `--nocapture`, or `#[tracing_test::traced_test]` on the one test. Take the first line that names an error, not the last line of the panic.
2. **Enumerate the values.** Write them down before theorising. One panic usually carries several: a crate error type with a primary code and an extended code, an `io::Error` with `os error N`, an HTTP or gRPC status, an exit signal, and the assertion message. Any one of them may be the whole answer.
3. **Resolve each value from the vendor's own documentation**, not from a forum post, a blog, an error-code table on a third-party site, or your memory of that library. Search results rank those summaries above the vendor page, and they are sometimes wrong. Then check the value against the version the project pins — extended codes get added, and meanings get reworded between releases.
4. **Split primary from extended.** Most vendor schemes encode a coarse class in the low bits and the specific classification in the high bits. Both matter: the primary says *what kind of thing* went wrong, the extended says *which specific condition*.
5. **Name it.** `SQLITE_READONLY_ROLLBACK (776)` is a hypothesis with a name that a lookup can confirm or kill. "A WAL sidecar problem" is a story. If the failing line carries only a primary code, the specific one is still available — see the note on extended codes below, and read the failure again rather than settling for the coarse code.
6. **Read the emitting code path.** Search for the constant or the error constructor and read the branch that produces it — `rg 'READONLY|SQLITE_READONLY|extended_code'` and follow the match back. If the code path cannot produce that value, then your code is stale, you are reading a different error, or the vendor reuses a code and the numeric value is not the whole meaning.
7. **Split what is proven from what is not.** The resolved code names the mechanism. It does not tell you how often it happens, and it does not tell you how this test reached that condition. Rate still needs a run (Phase 2); the path from this test to that condition still needs reading (Phase 4).

## Vendor codes you will actually hit in Rust tests

### SQLite result codes

Rust SQLite wrappers pass the vendor code through unchanged, and the low 8 bits are the primary code: `776 & 0xff == 8` is `SQLITE_READONLY`, while the high bits carry the specific condition. Values verified against <https://www.sqlite.org/rescode.html> (page dated 2026-02-18).

| Value | Name | Documented meaning |
|---|---|---|
| 776 | `SQLITE_READONLY_ROLLBACK` | the database cannot be opened because it has a **hot journal that needs to be rolled back** but cannot be, because the database is read-only |
| 264 | `SQLITE_READONLY_RECOVERY` | a WAL database cannot be opened because it needs recovery, recovery requires write access, and only read access is available |
| 520 | `SQLITE_READONLY_CANTLOCK` | cannot obtain a read lock on a WAL database because the shared-memory (`-shm`) file is read-only |
| 261 | `SQLITE_BUSY_RECOVERY` | another process is busy recovering a WAL database after a crash |
| 1032 | `SQLITE_READONLY_DBMOVED` | the database file has moved since it was opened, so writing could corrupt it |
| 1544 | `SQLITE_READONLY_DIRECTORY` | no permission to create the journal file beside the database, which writing requires |
| 5 | `SQLITE_BUSY` | another connection, usually in another process, holds the write lock |
| 11 | `SQLITE_CORRUPT` | the database file is corrupt |
| 15 | `SQLITE_PROTOCOL` | the file-locking protocol failed; currently only returned in WAL mode under intense cross-process write contention |

Three things to know about the code itself.

**Extended codes are off by default, which matters.** SQLite enables them *per connection*, either with `sqlite3_extended_result_codes(db, 1)` or the `SQLITE_OPEN_EXRESCODE` open flag (SQLite 3.37.0+). `rusqlite` exposes the flag as `OpenFlags::SQLITE_OPEN_EXRESCODE`, and it is **not** part of rusqlite's default flags — those are `READ_WRITE | CREATE | URI | NO_MUTEX`. So a panic printing only `SQLITE_READONLY` is not the end of the available data: enable extended codes, or read `sqlite3_extended_errcode(db)` for the most recent one, and the specific condition comes back.

**One panic line can carry both.** `libsqlite3_sys::Error::new` masks `result_code & 0xff` into `code` and keeps the whole value in `extended_code`, which is why a rusqlite error can read `code: ReadOnly, extended_code: 776` — the primary on the left, the diagnosis on the right.

**A hot journal is not corruption.** It is a rollback journal a dead writer left behind, so the code says *who* died and *why* the open failed, and says nothing about the data.

**Check the vendor table, not a summary of it.** This is not hypothetical. A third-party SQLite error reference indexed in search results currently states that `SQLITE_READONLY_ROLLBACK` is extended code **264** — `264` is `SQLITE_READONLY_RECOVERY`, and it describes the WAL case. It reads as authoritative, it is wrong, and following it would have sent the investigation after the wrong mechanism. Numbers get transposed; codes get reassigned between releases; blog posts outlive the version they described. The vendor page is one fetch away and it is the only source that counts.

### OS errors

`Address already in use (os error 98)` on Linux, `(os error 48)` on macOS — same error, different number. Resolve the number on the machine that failed; do not assume Linux:

```bash
python3 -c 'import os; print(os.strerror(98))'
```

| Meaning | Linux | macOS |
|---|---|---|
| `Address already in use` | 98 | 48 |
| `Connection reset by peer` | 104 | 54 |
| `Connection refused` | 111 | 61 |
| `Broken pipe` | 32 | 32 |
| `No space left on device` | 28 | 28 |
| `Too many open files` (process) | 24 | 24 |
| `Too many open files` (system) | 23 | 23 |
| `Text file busy` | 26 | 26 |
| `Permission denied` | 13 | 13 |
| `Resource temporarily unavailable` (`EAGAIN`) | 11 | 35 |

`std::io::Error::kind()` is the coarse classification and is lossy — two different errnos map to `ErrorKind::PermissionDenied`. The number is the data.

### Exit signals

A test that died rather than panicked reports a signal, not a message. Read it with `std::process::ExitStatusExt::signal()` on Linux, or from the runner's `SIGxxx` status line.

| Signal | Number | Means |
|---|---|---|
| `SIGKILL` | 9 | killed by the OOM killer, by `Child::kill()`, or by a timeout policy — indistinguishable from the outside, so check the dmesg or the runner's own report |
| `SIGTERM` | 15 | something asked it to stop: a `Drop`, a `slow-timeout`, or the runner shutting down |
| `SIGABRT` | 6 | an abort, usually a panic in a destructor, a double panic, or a C library assertion |
| `SIGSEGV` / `SIGBUS` | 11 / 10 | bad memory access; in a Rust test, usually a `unsafe` bug or a corrupted file mapping |

A `SIGKILL` with no out-of-memory evidence is a strong hint that the test's own teardown killed something.

### HTTP and gRPC statuses

- `429` / `503` / `UNAVAILABLE` (14) — backpressure or a process that is not serving; find which by checking whether the client retried.
- `500` with an empty body, or a connection reset on the first request — the server died before or during the request, not a request bug.
- `504` / `DEADLINE_EXCEEDED` (4) — the caller ran out of budget; a hang or a starvation problem, not a wrong answer.
- `RESOURCE_EXHAUSTED` (8) — a quota, a connection pool, or a thread pool, and the pool depth is worth reading directly.

### SQLSTATE

If the project talks to PostgreSQL or MySQL, the five-character SQLSTATE classifies the failure for you: class `08` connection exception, `22` data exception, `23` integrity constraint violation, `40` transaction rollback (`40001` serialization failure, `40P01` deadlock detected), `53` insufficient resources. `40001` on one attempt and success on the next is a serialization retry rate, which is a wall-clock-adjacent finding rather than a data bug.

### Panic shapes worth decoding

- `assertion failed: left == right` with two huge values — the values are the data. Often an ordering difference, a length difference, or an extra record.
- `called \`Result::unwrap()\` on an \`Err\` value: <payload>` — the payload is the error, and it is often the only place the code appears.
- `assertion failed: (left == right) && (left == right2)` — a helper that already tried to give a good message; read the values it printed.
- `called \`Option::unwrap()\` on a \`None\` value` — the failure is upstream of the unwrap. Find what produced the `None`, not the unwrap.

## Worked example — the line that ended the investigation

A test failed twice in a whole-workspace run and never in a scoped one. The panic's first line was:

```
called `Result::unwrap()` on an `Err` value: Error { code: ReadOnly, extended_code: 776 }
```

Decoding it, in order:

1. `776` → `SQLITE_READONLY_ROLLBACK`: a hot journal needs rolling back and the connection cannot roll it back because it is read-only.
2. `code: ReadOnly` → the connection was opened read-only, which is why recovery was impossible. A read-only *assertion* therefore cannot read a store a killed writer left behind — the fix is `query_only` on a read-write connection, or a copy taken after the writer exits.
3. A hot journal means a writer died mid-transaction. Reading the code path that killed it found the test's own `Drop` calling `Child::kill()` on a child that was still writing.
4. Proven: the mechanism, and that the test's own teardown caused it. Not proven: the rate — zero local reproductions, so the finding was filed as `not_reproduced` with `cause_basis: inferred` and the rate left unmeasured.

Two hypotheses (a WAL shared-memory sidecar problem) came before the decode, cost two failed experiments, and were filed in the first version of the report. The code was in the panic the whole time.

## What a resolved code does not give you

- **Not a rate.** Decoding is Phase 0, not Phase 2. A code that names the mechanism does not measure how often it happens, and non-negotiable 1 still applies.
- **Not permission to skip the path.** The code says which class of failure occurred; you still have to show how *this* test reached it, by reading the code that emits it.
- **Not proof your story is right.** Codes get reused across versions and across `Error` variants. Confirm the number means what you think before you build a mechanism on it.
- **Not a finished report.** A filed issue is read by someone who will act on it. Every structured field — cause, evidence, proposed fix — must be something you checked, not something you inferred. If you cannot quote the line that emits the value, the field says `hypothesis`, not `confirmed`.