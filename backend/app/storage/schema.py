"""Database schema (SQLAlchemy Core). Alembic migrations in backend/migrations are generated from this metadata.

Postgres in production (DATABASE_URL), SQLite locally. Timestamps are ISO-8601 UTC strings, as in the frozen
results snapshot. JSON columns hold answers, traces and validated case and drug records.
"""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    false,
)

metadata = MetaData()

runs = Table(
    "runs", metadata,
    Column("id", String(64), primary_key=True),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40)),
    Column("label", String(80), nullable=False, server_default=""),
    Column("provider", String(40), nullable=False),
    Column("model", String(120), nullable=False),
    Column("prompt_version", String(20), nullable=False),
    Column("conditions", JSON, nullable=False),
    Column("case_ids", JSON, nullable=False),
    Column("interview", Boolean, nullable=False, server_default=false()),
    Column("force", Boolean, nullable=False, server_default=false()),
    Column("status", String(30), nullable=False, server_default="running"),
    Column("n_total", Integer, nullable=False),
    Column("n_done", Integer, nullable=False, server_default="0"),
    Column("finished_at", String(40)),
    Column("temperature", Float),
    Column("benchmark_version", String(40)),
    Column("benchmark_hash", String(64)),
)

results = Table(
    "results", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", String(64), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
    Column("case_id", String(40), nullable=False),
    Column("condition", String(4), nullable=False),
    Column("interview", Boolean, nullable=False, server_default=false()),
    Column("status", String(20), nullable=False),
    Column("answer", JSON),
    Column("error", Text),
    Column("rules_fired", JSON, nullable=False),
    Column("owner_questions", JSON, nullable=False),
    Column("steps", Integer, nullable=False, server_default="0"),
    Column("tokens_in", Integer, nullable=False, server_default="0"),
    Column("tokens_out", Integer, nullable=False, server_default="0"),
    Column("cost_usd", Float),
    Column("latency_ms", Integer, nullable=False, server_default="0"),
    Column("cached", Boolean, nullable=False, server_default=false()),
    Column("cache_key", String(64)),
    Column("created_at", String(40), nullable=False),
    Index("results_run", "run_id"),
    Index("results_case_condition", "case_id", "condition"),
)

# One trace (the list of agent steps) per result, kept apart so list queries stay small.
traces = Table(
    "traces", metadata,
    Column("result_id", Integer, ForeignKey("results.id", ondelete="CASCADE"), primary_key=True),
    Column("steps", JSON, nullable=False),
)

cache = Table(
    "cache", metadata,
    Column("key", String(64), primary_key=True),
    Column("provider", String(40), nullable=False),
    Column("model", String(120), nullable=False),
    Column("condition", String(4), nullable=False),
    Column("case_id", String(40), nullable=False),
    Column("prompt_version", String(20), nullable=False),
    Column("interview", Boolean, nullable=False),
    Column("payload", JSON, nullable=False),
    Column("created_at", String(40), nullable=False),
)

reviews = Table(
    "reviews", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("result_id", Integer, ForeignKey("results.id", ondelete="CASCADE"), nullable=False),
    Column("reviewer", String(80), nullable=False),
    Column("rating", String(20), nullable=False),
    Column("note", Text, nullable=False, server_default=""),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    UniqueConstraint("result_id", "reviewer", name="reviews_result_reviewer"),
    Index("reviews_result", "result_id"),
)

# The benchmark data. `data` is the validated record (Case / DrugRow, JSON mode); `position` keeps file order.
cases = Table(
    "cases", metadata,
    Column("case_id", String(40), primary_key=True),
    Column("position", Integer, nullable=False),
    Column("data", JSON, nullable=False),
    Column("updated_at", String(40), nullable=False),
)

drug_rows = Table(
    "drug_rows", metadata,
    Column("key", String(160), primary_key=True),  # "species|drug" (drug lower-cased)
    Column("position", Integer, nullable=False),
    Column("data", JSON, nullable=False),
    Column("updated_at", String(40), nullable=False),
)

# SVTG passages with page numbers, loaded by the seed script from a local copy of the PDF. Never committed.
svtg_chunks = Table(
    "svtg_chunks", metadata,
    Column("chunk_id", String(40), primary_key=True),
    Column("ord", Integer, nullable=False),
    Column("page", Integer, nullable=False),
    Column("printed_page", Integer),
    Column("section", Text, nullable=False),
    Column("text", Text, nullable=False),
    Index("svtg_chunks_page", "page"),
)

# Small key/value table: data revision counters and SVTG source details.
meta = Table(
    "meta", metadata,
    Column("key", String(40), primary_key=True),
    Column("value", Text, nullable=False),
)

# Non-secret settings saved from the Settings page (override environment variables).
app_settings = Table(
    "app_settings", metadata,
    Column("key", String(40), primary_key=True),
    Column("value", JSON),
)

# Fixed one-minute windows per client IP.
rate_limits = Table(
    "rate_limits", metadata,
    Column("ip", String(64), primary_key=True),
    Column("minute", Integer, primary_key=True),  # epoch minute
    Column("hits", Integer, nullable=False),
)

# Wrong access codes ("*" = all IPs together) and active lockouts.
auth_failures = Table(
    "auth_failures", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ip", String(64), nullable=False),
    Column("ts", Float, nullable=False),
    Index("auth_failures_ip_ts", "ip", "ts"),
)

auth_lockouts = Table(
    "auth_lockouts", metadata,
    Column("ip", String(64), primary_key=True),
    Column("locked_until", Float, nullable=False),
)

# Live-model tokens per UTC day (MAX_DAILY_TOKENS).
budget_usage = Table(
    "budget_usage", metadata,
    Column("day", String(10), primary_key=True),
    Column("tokens", Integer, nullable=False),
)
