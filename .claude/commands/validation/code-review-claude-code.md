---
description: Technical code review for quality and bugs that runs pre-commit
---

Perform comprehensive technical code review on recently changed files.

## Philosophy

**Core Principles:**
- Simplicity is the ultimate sophistication - every line should justify its existence
- Code is read far more often than it's written - optimize for readability
- The best code is often the code you don't write
- Elegance emerges from clarity of intent and economy of expression
- Security by default - assume all input is hostile
- YAGNI ruthlessly - don't build what you don't need today

**Review Mindset:**
- Be thorough, not pedantic
- Suggest fixes, don't just complain
- Verify suspicions, don't assume
- Consider context, not just code in isolation
- Find bugs that matter, ignore trivial style

## Pre-flight Validation

Before code review, verify basic quality gates pass:

```bash
# Level 1: Syntax & Style
ruff check . && ruff format --check .

# Level 2: Type Safety
mypy app/ && pyright app/
```

**If failures:**
- Report which checks failed with exact output
- List failing files
- STOP review and ask: "Fix pre-flight issues first, or continue anyway?"

**Rationale:** Don't waste time reviewing code that fails basic checks. But allow override for WIP reviews.

## Context Gathering

Understand the codebase before judging code.

### 1. Read Project Standards

```bash
# Core documentation
cat CLAUDE.md 2>/dev/null || echo "No CLAUDE.md found"
cat README.md 2>/dev/null || echo "No README.md found"
```

Focus on:
- Type checking standards (mypy/pyright strictness)
- Logging patterns (structured logging format)
- Testing standards (unit vs integration, fixtures)
- Architecture patterns (vertical slice, shared utilities)
- API conventions (error responses, pagination)

### 2. Examine Existing Patterns

Look at similar code already in the codebase:
- `app/core/` - Infrastructure patterns (database, logging, config)
- `app/shared/` - Shared utilities (when to extract, when to duplicate)
- `app/features/*/` - Feature slice structure and conventions

**Key question:** How does existing code solve similar problems?

### 3. Understand Recent Reviews (Learning from History)

```bash
# Check if previous reviews exist
ls -lt .claude/code-reviews/*.md 2>/dev/null | head -5
```

If previous reviews exist, read the most recent one. Look for:
- **Repeat issues** - Same problem in new code?
- **Patterns** - Common mistakes to watch for?
- **Standards evolution** - New rules established?

### 4. Identify Changed Files

```bash
# Show what changed
git status

# Stats overview
git diff --stat HEAD

# Full diff
git diff HEAD
```

**Parse the output:**
- Modified files: `M path/to/file.py`
- New files: `?? path/to/file.py`
- Deleted files: `D path/to/file.py`

**List untracked files explicitly:**

```bash
git ls-files --others --exclude-standard
```

### 5. Read Full Context

For EACH changed or new file:
- **Read the ENTIRE file** (not just the diff)
- **Read related test files** (understand expected behavior)
- **Check git blame for context** (why was old code written that way?)

```bash
# Example for a changed file
git blame app/features/products/service.py | head -20
```

**Why full files?** A line might look fine in a 5-line diff, wrong in 200-line context.

## Analysis Framework

For each changed/new file, analyze across 7 dimensions:

### 1. Logic Errors & Bugs

**Look for:**
- **Off-by-one errors** - Array indexing, loop boundaries, pagination
- **Incorrect conditionals** - Wrong operators (`and` vs `or`), missing edge cases
- **Missing error handling** - Uncaught exceptions, unhandled `None`, no validation
- **Race conditions** - Concurrent access without locks, async/await mistakes
- **Type coercion bugs** - Implicit conversions (str→int, None→default)
- **State management errors** - Invalid state transitions, inconsistent state
- **Incorrect assumptions** - About input, environment, data shape

**AI-specific logic errors:**
- Mocking the function being tested (test validates nothing)
- Happy-path bias (only tests success, ignores errors)
- Missing null checks after operations that can fail

**Verification:**
```bash
# Run specific test to confirm bug
pytest tests/path/to/test_file.py::test_specific_function -v
```

### 2. Security Vulnerabilities

**ALWAYS flag as CRITICAL:**

- **SQL injection** - Unsanitized input in queries (f-strings in SQL, concatenation)
- **XSS vulnerabilities** - Unescaped user input in templates/responses
- **Command injection** - Shell execution with user input (`os.system`, `subprocess` without sanitization)
- **Path traversal** - File access without validation (`open(user_input)`)
- **Secrets exposure** - API keys, passwords, tokens in code
- **Insecure data handling** - Plaintext passwords, unencrypted sensitive data
- **Missing authentication** - Public endpoints that should be protected
- **Missing authorization** - Authenticated users accessing unauthorized resources
- **CORS misconfiguration** - Overly permissive origins (`*` in production)
- **Unsafe deserialization** - Pickle, eval, exec with untrusted data

**Verification:**
```bash
# Check for exposed secrets
git diff HEAD | grep -iE "(api_key|password|secret|token)" | grep -v "example"
```

### 3. Performance Issues

**Look for:**

- **N+1 queries** - Database calls in loops
  ```python
  # BAD: N+1 pattern
  for product in products:
      reviews = db.query(Review).filter(Review.product_id == product.id).all()
  ```

- **Missing database indexes** - Queries on unindexed columns
- **Inefficient algorithms** - O(n²) when O(n log n) exists
- **Memory leaks** - Unclosed files/connections, unbounded caches
- **Unnecessary computations** - Repeated calculations in loops
- **Missing pagination** - Unbounded result sets from database
- **Synchronous blocking** - Blocking I/O in async context
- **Missing caching** - Repeated expensive operations without memoization

**Verification:**
```bash
# For N+1 queries, check if SQLAlchemy query logging reveals multiple queries
# Add this to a test:
# import logging
# logging.basicConfig()
# logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

**Performance profiling (for claims):**
If claiming inefficiency, measure it:
```python
import time
start = time.perf_counter()
result = expensive_function()
duration_ms = (time.perf_counter() - start) * 1000
print(f"Duration: {duration_ms:.2f}ms")
```

### 4. Code Quality Issues

**Look for:**

- **DRY violations** - Duplicated logic (3+ instances suggest extraction)
- **Overly complex functions** - >50 lines, >3 levels of nesting, >5 parameters
- **Poor naming** - Vague (`data`, `tmp`, `x`), misleading, inconsistent
- **Missing type annotations** - Untyped parameters, `Any` without justification
- **Incomplete docstrings** - Missing Args/Returns/Raises in public APIs
- **Magic numbers** - Unexplained constants (`if x > 86400:` vs `SECONDS_PER_DAY`)
- **Dead code** - Unused imports, unreachable branches, commented-out code
- **God objects** - Classes with too many responsibilities
- **Deeply nested code** - >3 levels suggests extraction or early returns

**Complexity metrics:**
- Function length: >50 lines is suspect
- Cyclomatic complexity: >10 suggests splitting
- Parameter count: >5 suggests bundling

### 5. Test Quality Assessment

**This is critical and often missed!**

For each test file, check:

**Test Coverage:**
```bash
# Run coverage on changed files
pytest --cov=app/features/products --cov-report=term-missing tests/
```

**Test Quality Issues:**

- **Over-mocking** - Mocking the function being tested
  ```python
  # BAD: This test is useless
  def test_calculate_total(mocker):
      mocker.patch('calculate_total', return_value=100)
      assert calculate_total([]) == 100  # Tests the mock, not the function!
  ```

- **Under-assertion** - Tests that don't verify enough
  ```python
  # BAD: Only checks it doesn't crash
  def test_create_product():
      product = create_product("test")
      assert product  # Should verify properties!
  ```

- **Brittle tests** - Tests that break with unrelated changes (over-specified mocks)
- **Missing edge cases** - Only tests happy path, ignores errors/boundaries
- **Integration tests as unit tests** - Tests that hit database/network in unit tests
- **No assertions** - Test runs code but verifies nothing
- **Flaky tests** - Tests that depend on timing, random data, external state

**Good test patterns:**
- Arrange-Act-Assert structure
- Descriptive test names (`test_create_product_with_duplicate_name_raises_error`)
- Minimal mocks (only external dependencies)
- Test behavior, not implementation
- Fast (<100ms per unit test)

### 6. Breaking Changes

**Check for:**

- **API contract changes** - Modified request/response schemas
  ```python
  # BREAKING: Removed required field
  class ProductResponse(BaseModel):
      id: int
      name: str
      # price: Decimal  ← Removed! Breaks clients!
  ```

- **Database migration safety**
  - Dropping columns without deprecation period
  - Changing column types without backwards compatibility
  - Missing rollback logic

- **Function signature changes** - Added required parameters, changed return types
- **Exception changes** - New exceptions thrown, removed exception handling
- **Dependency version bumps** - Major version changes in requirements

**Verification:**
```bash
# Check for API schema changes
git diff HEAD -- "*/schemas.py" "*/models.py"
```

### 7. Codebase Standards Adherence

**Check against project-specific patterns:**

**Architecture:**
- Vertical slice structure (`app/features/*/models.py`, `routes.py`, etc.)
- Shared utilities only when used by 3+ features
- Core infrastructure in `app/core/`

**Logging:**
```python
# GOOD: Structured logging
logger.info("product.create_completed", product_id=product.id, duration_ms=42)

# BAD: String formatting
logger.info(f"Created product {product.id} in 42ms")
```

**Type checking:**
- All functions have type annotations
- No `Any` without justification
- No `# type: ignore` without explanation
- Strict mypy/pyright compliance

**Testing:**
- Unit tests in `tests/unit/`
- Integration tests marked `@pytest.mark.integration`
- Fixtures in `conftest.py`
- Test names describe behavior

**API patterns:**
- Use `PaginationParams` for list endpoints
- Use `ErrorResponse` schema for errors
- Router prefixes for feature namespacing
- Consistent HTTP status codes

### 8. AI-Specific Failure Modes

**AI agents have predictable mistakes humans don't make:**

**Over-abstraction:**
```python
# AI loves creating base classes with 1 implementation
class BaseProductProcessor(ABC):  # YAGNI!
    @abstractmethod
    def process(self) -> None: ...

class ProductProcessor(BaseProductProcessor):  # Only implementation!
    def process(self) -> None: ...
```
**Fix:** Implement directly. Extract when 2nd implementation appears.

**Unnecessary complexity:**
```python
# AI over-engineers simple problems
class ConfigurationManagerFactory:  # For reading 3 env vars!
    def create_manager(self) -> ConfigurationManager: ...
```
**Fix:** Just use `os.getenv()` or Pydantic Settings.

**Missing error context:**
```python
# AI catches but doesn't log
try:
    result = process()
except Exception:
    raise  # No context! Debugging nightmare!
```
**Fix:** Add structured logging before re-raising.

**Type suppressions without justification:**
```python
result: dict = api_call()  # type: ignore  ← Why?
```
**Fix:** Either fix the type or document why it's unavoidable.

**Premature optimization:**
```python
# Caching for function called once per request
@lru_cache(maxsize=10000)  # YAGNI!
def get_user_name(user_id: int) -> str: ...
```
**Fix:** Optimize when profiling shows it's slow.

**Missing type narrowing:**
```python
def process(value: str | None) -> str:
    if value is not None:
        return value.upper()
    # Missing else case! Implicitly returns None!
```
**Fix:** Explicit else or raise.

## Verification Requirements

Don't just report potential issues - verify them!

**For each issue category:**

| Category | Verification Method |
|----------|-------------------|
| Logic errors | Run specific test, show failure |
| Security | Show exploit vector or static analysis |
| Performance | Profile and show metrics (queries, duration) |
| Type errors | Run mypy/pyright on file, show output |
| Test quality | Run tests, show coverage report |
| Breaking changes | Show API diff or migration risk |

**Verification levels:**
- ✅ **Verified** - Ran test/check, confirmed issue exists
- ⚠️ **Probable** - Strong evidence but not confirmed (design smell)
- ❓ **Needs testing** - Hypothesis requiring human verification

**Example verification:**
```bash
# For claimed N+1 query
pytest tests/test_products.py::test_list_products_with_reviews -v --log-cli-level=INFO

# Check output for multiple queries:
# SELECT * FROM products;
# SELECT * FROM reviews WHERE product_id = 1;  ← N+1!
# SELECT * FROM reviews WHERE product_id = 2;
```

## Output Format

### File Location

Save to: `.claude/code-reviews/review-{YYYYMMDD-HHMMSS}.md`

Example: `.claude/code-reviews/review-20250116-143022.md`

### Structure

```markdown
# Code Review - {Date}

## Summary Stats

- **Commit:** {git rev-parse --short HEAD}
- **Files Modified:** X
- **Files Added:** X
- **Files Deleted:** X
- **Lines Added:** +X
- **Lines Deleted:** -X
- **Pre-flight:** ✅ Passed / ❌ Failed (details below)

## Pre-flight Results

### Level 1: Syntax & Style
{output from ruff}

### Level 2: Type Safety
{output from mypy/pyright}

## Issues Found: X

{If 0: "✅ Code review passed. No technical issues detected."}

---

### Issue #1

**Severity:** critical | high | medium | low
**Category:** Logic | Security | Performance | Quality | Tests | Breaking | Standards | AI-Specific
**File:** `path/to/file.py:42`
**Verified:** ✅ yes | ⚠️ probable | ❓ needs-testing

**Issue:**
{One-line description}

**Detail:**
{2-3 sentences explaining:
- Why this is a problem
- What the impact is
- What could go wrong}

**Current Code:**
```python
{Show the problematic code}
```

**Suggested Fix:**
```python
{Show the corrected code}
```

**Verification:**
{If verified, show the verification method and output:
- Test command that failed
- Type checker output
- Profiling results
- Coverage gaps}

---

{Repeat for each issue}

## Test Coverage Analysis

{If test files were changed/added:}

Coverage report:
```
{pytest --cov output}
```

**Gaps:**
- {List uncovered lines or missing test scenarios}

## Cross-cutting Concerns

**Pattern Analysis:**
{If same issue appears in multiple files:}
- Issue "{pattern}" found in X files: {list files}
- Suggest: {Add pattern to CLAUDE.md or create linting rule}

**Historical Issues:**
{If similar to previous reviews:}
- Similar to review {date}: {link to file}
- This is the {n}th occurrence of {pattern}
- Action: Update standards to prevent recurrence

## Recommendations

### Critical (Fix before merge)
- {List critical/high severity issues}

### Important (Fix soon)
- {List medium severity issues}

### Nice-to-have (Consider for future)
- {List low severity issues}

### Process Improvements
{If patterns suggest process changes:}
- Add linting rule for {pattern}
- Document standard in CLAUDE.md: {what}
- Create test fixture for {common setup}
```

## Severity Guidelines

**Critical** (Ship-blocking):
- Security vulnerabilities (injection, XSS, exposed secrets)
- Data loss risks (incorrect deletions, missing transactions)
- Crashes or exceptions in core flows
- Breaking changes without migration path

**High** (Fix before merge):
- Logic bugs affecting correctness
- Race conditions or async/await errors
- N+1 queries or severe performance issues
- Type safety violations
- Missing critical error handling

**Medium** (Fix or document):
- Code smells (DRY violations, complexity)
- Maintainability issues (poor naming, missing docs)
- Test quality issues (over-mocking, missing cases)
- Minor performance concerns
- Standards violations

**Low** (Nice-to-have):
- Style inconsistencies (that passed linting)
- Minor naming improvements
- Micro-optimizations
- Subjective architecture suggestions

## Final Checklist

Before submitting the review, verify:

- [ ] Read CLAUDE.md and project standards
- [ ] Read full context of each changed file (not just diffs)
- [ ] Ran pre-flight checks (linting, type checking)
- [ ] Verified critical/high severity issues (ran tests, checks)
- [ ] Provided specific file:line references for all issues
- [ ] Suggested concrete fixes with code examples
- [ ] Checked for repeat issues from previous reviews
- [ ] Analyzed test quality (not just code quality)
- [ ] Checked for AI-specific failure modes
- [ ] Flagged all security issues as CRITICAL
- [ ] Considered breaking changes and migration safety
- [ ] Assessed cross-cutting patterns (same issue in multiple files)
- [ ] Ran test coverage on changed areas
- [ ] Suggested process improvements if patterns emerge

## Review Complete

Save the review file and provide a summary to the user:

```
Code review complete!

Summary:
- X files reviewed
- X issues found (Critical: X, High: X, Medium: X, Low: X)
- Pre-flight: {Passed/Failed}
- Test coverage: X%

Review saved to: .claude/code-reviews/review-{timestamp}.md

{If critical/high issues:}
⚠️ Address critical/high severity issues before merging.

{If patterns detected:}
💡 Consider updating CLAUDE.md with new standards based on findings.
```
