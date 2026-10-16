# Reference: Bug Review Pipeline Schemas & Examples

## File naming convention

All reports use today's date in `YYYY-MM-DD` format:
```
./issues/2025-03-15-report.md
./issues/2025-03-15-refutation.md
./issues/2025-03-15-final.md
```

Always create the `./issues/` directory before writing.

---

## Bug ID scheme

- Bug Finder assigns IDs sequentially: `BUG-001`, `BUG-002`, ...
- Adversary references the same IDs
- Arbiter uses the same IDs, may add `ARBITER-001` for newly discovered bugs
- IDs are consistent across all three reports

---

## Severity classification guide

### Critical (10 points)
Real-world impact is immediate and severe. Requires urgent remediation.

Examples:
- SQL injection with data exfiltration potential
- Authentication bypass (any user can access any account)
- Remote code execution vector
- Hardcoded production credentials
- Data loss on normal usage (not just edge case)
- Privilege escalation to admin

### Medium (5 points)
Real functional problem that affects correctness or performance under realistic conditions.

Examples:
- Off-by-one error that causes incorrect calculations
- Missing input validation that causes silent data corruption
- Race condition in high-traffic code paths
- N+1 query in a frequently-called endpoint
- Incorrect HTTP status codes causing client misbehavior
- Unhandled exception causing 500 errors for valid inputs
- Missing transaction on multi-step DB operations

### Low (1 point)
Minor issue, edge case, or code quality problem. Should be fixed but not urgent.

Examples:
- Division by zero only possible with invalid config
- Confusing variable name that could cause future bugs
- TODO/FIXME comment indicating acknowledged technical debt
- Unused import or dead code
- Missing error message detail (not a security risk)
- Inconsistent null handling that doesn't affect output

---

## Example: well-written bug report entry

```markdown
## BUG-007 — Unsanitized user input in search query

**Location:** `src/api/search.py:43`  
**Severity:** Critical  
**Points:** 10  

**Description:**  
The `search_users()` function constructs a SQL query using direct string 
interpolation of the `query` parameter from the HTTP request body. An 
attacker can inject arbitrary SQL to extract, modify, or delete data.

**Evidence:**  
```python
# search.py:43
sql = f"SELECT * FROM users WHERE name LIKE '%{query}%'"
cursor.execute(sql)
```

**Suggested Fix:**  
Use parameterized queries:
```python
sql = "SELECT * FROM users WHERE name LIKE %s"
cursor.execute(sql, (f"%{query}%",))
```

**Impact:** Full database access for any authenticated user.
```

---

## Example: well-written disproval entry

```markdown
## BUG-007 — Unsanitized user input in search query
**Original severity/points:** Critical / 10  

**Counter-argument:**  
The `search_users()` endpoint (search.py:43) is only accessible via the 
internal admin panel, which requires `ROLE=admin` (enforced at the Django 
middleware layer in `middleware/auth.py:88`). While the SQL construction 
is unsafe, the attack surface is limited to admin users who already have 
full DB access via the admin UI.

**Confidence:** 60%  
**Risk calculation:** EV = 0.60×10 − 0.40×20 = 6 − 8 = −2 → ACCEPT  

**Decision:** ACCEPT  
**Points:** 0  

*Note: Even with the admin restriction, the unsafe pattern should be fixed 
to prevent privilege escalation if auth is ever bypassed.*
```

---

## Example: well-written arbiter verdict

```markdown
## BUG-007 — Unsanitized user input in search query

**Severity:** Critical  
**Location:** `src/api/search.py:43`  

**Finder's claim:** Raw string interpolation into SQL query = SQL injection risk.  
**Skeptic's counter:** Endpoint only accessible to admins who already have DB access.  

**Arbiter's analysis:**  
The Finder is correct — the code is textbook SQL injection. The Adversary's 
counter has merit: the auth middleware *does* restrict this to admin users 
(confirmed at middleware/auth.py:88). However, defense in depth requires 
parameterized queries regardless of auth layer, and the admin restriction 
could be bypassed if a session token is stolen or auth middleware is 
misconfigured. The risk is real even if the attack surface is narrowed.

**VERDICT: REAL BUG**  
**Confidence:** High  
**Action required:** Replace string interpolation with parameterized query. 
Estimated fix: 5 minutes. No excuse to leave this unfixed.
```
