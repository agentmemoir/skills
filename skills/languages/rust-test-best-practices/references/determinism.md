# Determinism and Replayability

A test is deterministic when it produces the same result on every run, on every machine. A test is replayable when you can reproduce a specific failure exactly. These are separate properties, and a test needs both.

## The clock

Reading the system clock in a test is a bug. The result depends on when the suite ran, which timezone the runner is in, and whether the machine was suspended.

```rust
// BAD
let now = SystemTime::now();
let is_stale = now.duration_since(mtime).unwrap() > Duration::from_secs(3600);

// GOOD
trait Clock {
    fn now(&self) -> Instant;
}

struct FakeClock(Instant);
impl Clock for FakeClock {
    fn now(&self) -> Instant { self.0 }
}
```

A `FakeClock` is a few lines and makes every time-dependent test instant, deterministic, and readable. It is also the only way to test expiry, retries, and backoff without sleeping.

Keep the production seam narrow — a `Clock` trait passed into the component — so tests get control without the component knowing it is under test.

`tokio::time::pause()` covers the *Tokio* clock inside async code. It does not cover `std::time::SystemTime::now()` in your own code. If the component reads the system clock directly, pause time will not help; you need injection.

## Randomness

Unseeded randomness produces different inputs every run, which means a failure you cannot reproduce.

```rust
// BAD
let mut rng = rand::thread_rng();          // different every run
let data = random_payload(1024, &mut rng);

// GOOD
let seed = env_seed();
let mut rng = SmallRng::seed_from_u64(seed);
let data = random_payload(1024, &mut rng);
if check(&data).is_err() {
    eprintln!("replay with: SEED={seed}");   // make the failure reproducible
}
```

```rust
fn env_seed() -> u64 {
    std::env::var("SEED")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(0x5EED_0000_0000_0001)
}
```

The important part is the **replay instruction in the failure message**. A failing property test that does not tell you the seed has cost you the entire investigation.

Default the seed to a constant so ordinary runs are reproducible, and let CI sweep it deliberately — a scheduled job that runs the suite across many seeds finds far more than a single run does.

`proptest` handles this for you if you use `proptest-regressions`: a found counterexample is written to a file under `proptest-regressions/` and replayed on every subsequent run. Without that crate, the failure is a one-time report you will never see again.

## Hash iteration order

Rust's `HashMap` and `HashSet` use a randomly seeded hasher. The iteration order differs between processes. This is a deliberate denial-of-service defence, and it means any assertion on iteration order is flaky by construction.

```rust
// BAD - different order every process
assert_eq!(map.keys().collect::<Vec<_>>(), vec!["a", "b", "c"]);

// GOOD - sort first
let mut keys: Vec<_> = map.keys().collect();
keys.sort_unstable();
assert_eq!(keys, vec!["a", "b", "c"]);

// GOOD - order is irrelevant, compare the maps
assert_eq!(map, HashMap::from([("a", 1), ("b", 2), ("c", 3)]));

// GOOD - order is semantically meaningful, use an ordered map
let map: BTreeMap<_, _> = ...;
```

This one is worth a lint pass across an existing suite. It is a common source of "passes on my machine" reports that turn out to be order-dependent rather than machine-dependent.

The same applies anywhere iteration order leaks into output: serialized JSON from a `HashMap`, a formatted list built by iterating a set, a checksum computed over unordered keys. If the output is user-visible, the nondeterminism is a product bug, not just a test problem.

## Floating point

`assert_eq!` on floats is exact comparison, and the computed value is not exact the same way twice across machines. Transcendental functions (`sqrt`, `exp`, `ln`, `powf`), decimal parsing, and accumulation all differ slightly between platforms, optimisation levels, and architectures — and accumulation order changes with thread count, so a parallel sum differs from a serial one in the last digits.

Floating-point operations are one of the standard root-cause categories in the flaky-test literature (Luo et al., ICSE 2014; Lam et al., FaTB 2020), so this is a known source rather than an exotic one.

```rust
// BAD - a few ULPs of difference between machines is a failure here
assert_eq!(mean(&samples), 0.3);

// GOOD - assert the invariant that actually matters
assert!((mean(&samples) - 0.3).abs() <= 1e-9, "mean was {}", mean(&samples));

// GOOD - or a crate built for it
approx::assert_relative_eq!(mean(&samples), 0.3, max_relative = 1e-9);

// GOOD - or compare a quantized value when only the digits matter
assert_eq!((mean(&samples) * 100.0).round(), 30.0);
```

Choose the tolerance deliberately: an absolute epsilon is wrong at both ends of the range (`f64::EPSILON` rejects legitimate large values, and a fixed absolute tolerance passes far too much at small magnitudes), so prefer relative or ULP-based comparison — `approx`'s `assert_relative_eq!`, `float_eq`'s `assert_float_eq!`. When the exact digits do matter, assert the property (monotonic, in range, correctly ordered) instead of a literal, and seed the inputs so the case is reproducible.

## Directory iteration order

`std::fs::read_dir` returns entries in whatever order the filesystem feels like, and macOS APFS is documented as returning them in hash order rather than lexicographic. It is the same class of bug as `HashMap` iteration order, with a longer fuse.

```rust
// BAD - order is unspecified on every filesystem
let names: Vec<_> = read_dir(dir)?.map(|e| e?.file_name()).collect();
assert_eq!(names, ["a.txt", "b.txt", "c.txt"]);

// GOOD - sort first
let mut names: Vec<_> = read_dir(dir)?.map(|e| e?.file_name()).collect();
names.sort();
assert_eq!(names, ["a.txt", "b.txt", "c.txt"]);
```

## Environment and platform

Anything that varies by machine is a source of nondeterminism:

| Varies | Assert on instead |
|---|---|
| Locale | an explicit `Locale` parameter |
| Timezone | a UTC timestamp |
| Current directory | an absolute path from `tempfile`, or one from `CARGO_MANIFEST_DIR` |
| Hostname | a fixed value or a lookup mock |
| Line endings | normalized text |
| Available ports | port `0` |
| CPU count | an explicit `worker_threads` |
| Filesystem case sensitivity | a content difference, never a case-differentiated path |
| Path byte representation | a canonicalized path, not the literal string |
| Filename length limits | short ASCII fixture names |

Locale deserves special mention. Formatting and parsing a date or number produces different results under different locales, so a test that round-trips a formatted string can pass in one timezone and fail in another. Pass the locale in. The filesystem rows deserve the same caution for the opposite reason: macOS defaults to a case-insensitive, normalization-insensitive volume where Linux is case-sensitive, so a test whose *reason to exist* is two similarly named files can pass on one platform and fail on another. `isolation-and-resources.md` has the details.

## Machine and build configuration

Two sources of "works on my machine" that are not the code:

- **Build profile.** Debug code is often 10-50x slower. Any test whose correctness depends on finishing within a deadline can pass in release and fail in debug. If that is the situation, the deadline is the bug.
- **Core count.** A test that needs a specific number of concurrent workers to expose a race will hide on a many-core machine and appear on a 2-core CI runner. Set `worker_threads` explicitly so the test sees the same parallelism everywhere.

When a test only fails in CI, compare these four before anything else: core count, available memory, filesystem type of the target directory, and outbound network availability.

## Making failures replayable

A deterministic test that fails is easy to debug. A nondeterministic one is not. Every mechanism here serves replay:

1. **Seeded RNG**, with the seed printed on failure.
2. **`proptest-regressions`** to persist counterexamples.
3. **nextest stress runs** to reproduce the failure on demand: `cargo nextest run -E 'test(name)' --stress-count 200 --no-fail-fast`. Always `--no-fail-fast`, or the loop aborts at the first failure and you lose the rest of the sample.
4. **Shuffle seeds** for order dependence. On nightly, `cargo +nightly test -- -Z unstable-options --test-threads 1 --shuffle` prints a seed; replay it with `--shuffle-seed <N>`. Note that `--shuffle` does not change parallelism — combine with `--test-threads 1` for the useful random-sequential ordering.
5. **Under load, for timing bugs.** A timing flake often only appears on a loaded machine. `stress-ng --cpu "$(nproc)" --io 4` alongside the run turns a rare failure into a frequent one, and a rare failure you can reproduce on demand is worth more than a common one you cannot.

## Checklist

- [ ] No `SystemTime::now()` or `Instant::now()` in test or component code; a clock is injected.
- [ ] Any RNG is seeded, and the seed is printed on failure.
- [ ] `proptest-regressions` enabled for property tests.
- [ ] No assertion on `HashMap`/`HashSet` iteration order; data is sorted first.
- [ ] No assertion on `read_dir` order either; directory listings are sorted first.
- [ ] No `assert_eq!` on floats; a relative or ULP tolerance, or a quantized value.
- [ ] Locale, timezone, and working directory are explicit, not ambient.
- [ ] `worker_threads` set explicitly if concurrency matters.
- [ ] Failure messages carry everything needed to replay: seed, input, config.
