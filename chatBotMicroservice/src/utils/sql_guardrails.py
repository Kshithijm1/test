"""
sql_guardrails.py — Hard guardrails for SQL queries and plan text.

This module is the single enforcement point for SQL safety. It is applied:
  1. In controller.py on the HITL resume path (user-edited SQL)
  2. In controller.py on the HITL resume path (user-edited plan text)
  3. In researcher_sql_exec before any query reaches BigQuery

Rules: Only read-only SQL is permitted. Any statement or clause that could
mutate, define, control, or administer the database is rejected.
Plan text is scanned for embedded SQL injection attempts before it is
used as LLM prompt context for SQL generation.
"""

import re
import logging
from typing import Tuple

log = logging.getLogger("agent")

# ── Banned top-level statement keywords ───────────────────────────────────────
# These can never appear as the first meaningful keyword of a statement.
BANNED_STATEMENT_TYPES = [
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
    "REPLACE",
    "UPSERT",
    "TRUNCATE",
    "DROP",
    "CREATE",
    "ALTER",
    "RENAME",
    "GRANT",
    "REVOKE",
    "CALL",
    "EXECUTE",
    "EXEC",
    "BEGIN",
    "COMMIT",
    "ROLLBACK",
    "SAVEPOINT",
    "SET",
    "USE",
    "ATTACH",
    "DETACH",
    "LOAD",
    "COPY",
    "EXPORT",
]

# ── Banned clause / construct patterns ────────────────────────────────────────
# These are dangerous even when embedded inside a SELECT (e.g. subqueries,
# CTEs that write, or BigQuery scripting constructs).
BANNED_CLAUSE_PATTERNS: list[Tuple[str, str]] = [
    # DML inside CTEs or subqueries
    (r"\bINSERT\b", "INSERT"),
    (r"\bUPDATE\b", "UPDATE"),
    (r"\bDELETE\b", "DELETE"),
    (r"\bMERGE\b", "MERGE"),
    (r"\bTRUNCATE\b", "TRUNCATE"),
    # DDL anywhere
    (r"\bDROP\b", "DROP"),
    (r"\bCREATE\b", "CREATE"),
    (r"\bALTER\b", "ALTER"),
    # BigQuery-specific write constructs
    (r"\bINTO\s+\w", "INTO <table>"),          # INSERT INTO / SELECT INTO
    (r"\bOVERWRITE\b", "OVERWRITE"),
    (r"\bSCRIPT\b", "SCRIPT"),
    # Privilege / session control
    (r"\bGRANT\b", "GRANT"),
    (r"\bREVOKE\b", "REVOKE"),
    (r"\bSET\s+\w", "SET <var>"),
    # Multi-statement separators
    (r";.{0,20}(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|MERGE)", "multiple statements"),
]

# ── Allowed statement openers ─────────────────────────────────────────────────
# A valid query must start with one of these (after stripping comments/whitespace).
ALLOWED_OPENERS = re.compile(
    r"^\s*(?:--[^\n]*\n\s*)*(WITH|SELECT)\b",
    re.IGNORECASE,
)


class SQLGuardrailError(ValueError):
    """Raised when a SQL query violates a hard guardrail."""
    pass


def _strip_comments(sql: str) -> str:
    """Remove SQL line comments and block comments."""
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return sql


def validate_sql(sql: str, context: str = "") -> None:
    """
    Validate that a SQL query is strictly read-only.

    Raises SQLGuardrailError immediately on the first violation found.
    Passes silently if the query is safe.

    Args:
        sql:     The SQL string to validate.
        context: Optional label for logging (e.g. "HITL resume", "sql_exec").
    """
    if not sql or not sql.strip():
        raise SQLGuardrailError("SQL query is empty.")

    prefix = f"[GUARDRAIL{' ' + context if context else ''}]"

    # Work on a normalised, comment-stripped copy for pattern matching.
    # Keep the original for the opener check so indentation is preserved.
    normalised = _strip_comments(sql).upper()

    # ── Rule 1: Must start with SELECT or WITH ────────────────────────────────
    if not ALLOWED_OPENERS.match(sql):
        first_token = sql.strip().split()[0].upper() if sql.strip() else "(empty)"
        log.error(f"{prefix} Rejected — does not start with SELECT/WITH (got: {first_token})")
        raise SQLGuardrailError(
            f"Only SELECT or WITH...SELECT queries are permitted. "
            f"Your query starts with '{first_token}'."
        )

    # ── Rule 2: Banned clause patterns anywhere in the body ───────────────────
    for pattern, label in BANNED_CLAUSE_PATTERNS:
        if re.search(pattern, normalised):
            log.error(f"{prefix} Rejected — banned construct detected: {label}")
            raise SQLGuardrailError(
                f"Queries containing '{label}' are not permitted. "
                f"Only read-only SELECT queries are allowed."
            )

    log.info(f"{prefix} Query passed all guardrails ✓")


# ── Patterns that indicate embedded SQL injection in free-form plan text ──────
# These are DML/DDL keywords that have no legitimate place in a plain-text plan.
_PLAN_INJECTION_PATTERNS: list[Tuple[str, str]] = [
    (r"\bDELETE\s+FROM\b", "DELETE FROM"),
    (r"\bDROP\s+(TABLE|DATABASE|SCHEMA|VIEW|INDEX)\b", "DROP <object>"),
    (r"\bTRUNCATE\s+TABLE\b", "TRUNCATE TABLE"),
    (r"\bINSERT\s+INTO\b", "INSERT INTO"),
    (r"\bUPDATE\s+\w+\s+SET\b", "UPDATE ... SET"),
    (r"\bMERGE\s+INTO\b", "MERGE INTO"),
    (r"\bALTER\s+(TABLE|DATABASE|SCHEMA|VIEW)\b", "ALTER <object>"),
    (r"\bCREATE\s+(TABLE|DATABASE|SCHEMA|VIEW|INDEX)\b", "CREATE <object>"),
    (r"\bGRANT\s+\w+\s+ON\b", "GRANT ... ON"),
    (r"\bREVOKE\s+\w+\s+ON\b", "REVOKE ... ON"),
    (r"\bEXEC(UTE)?\s*\(", "EXEC(UTE)("),
]


def validate_plan_text(plan: str, context: str = "") -> None:
    """
    Scan user-edited plan text for embedded SQL injection attempts.

    This is applied at the HITL plan checkpoint before the plan text is
    written into state and used as prompt context for researcher_sql_gen.
    It does NOT reject normal financial vocabulary — it only triggers on
    multi-word DML/DDL constructs that have no place in a plain-text plan.

    Raises SQLGuardrailError if a suspicious pattern is found.
    Passes silently if the plan text is clean.

    Args:
        plan:    The plan text to scan.
        context: Optional label for logging.
    """
    if not plan or not plan.strip():
        return

    prefix = f"[GUARDRAIL PLAN{' ' + context if context else ''}]"
    normalised = plan.upper()

    for pattern, label in _PLAN_INJECTION_PATTERNS:
        if re.search(pattern, normalised):
            log.error(f"{prefix} Rejected — embedded SQL injection detected: {label}")
            raise SQLGuardrailError(
                f"Plan text contains a forbidden SQL construct ('{label}'). "
                f"Please remove any SQL statements from your plan edits."
            )

    log.info(f"{prefix} Plan text passed injection scan ✓")


def safe_sql_or_error(sql: str, context: str = "") -> Tuple[bool, str]:
    """
    Convenience wrapper that returns (is_safe, error_message) instead of raising.

    Returns:
        (True, "")           if the query is safe
        (False, "<reason>")  if a guardrail is violated
    """
    try:
        validate_sql(sql, context)
        return True, ""
    except SQLGuardrailError as e:
        return False, str(e)
