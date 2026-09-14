"""Generate the initial Alembic migration file from the ORM metadata."""

import io
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import types

from libflow.storage.models import Base

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "alembic" / "versions" / "0001_initial_schema.py"


def column_type(c) -> str:
    t = c.type
    if isinstance(t, types.DateTime):
        return "sa.DateTime()"
    if isinstance(t, types.JSON):
        if type(t).__name__ == "JSONB":
            return "postgresql.JSONB()"
        return "sa.JSON()"
    base = type(t).__name__
    length = getattr(t, "length", None)
    if length is not None:
        return f"sa.{base}({length})"
    return f"sa.{base}()"


def render_table(t) -> str:
    lines = [f"op.create_table({t.name!r},"]
    for c in t.columns:
        parts = [f"    sa.Column({c.name!r},"]
        parts.append(f"        {column_type(c)},")
        parts.append(f"        nullable={c.nullable},")
        if c.primary_key:
            parts.append("        primary_key=True,")
        parts.append("    ),")
        lines.append("".join(parts))
    for fk in sorted(t.foreign_keys, key=lambda fk: fk.parent.name):
        ondelete = f", ondelete={fk.ondelete!r}" if fk.ondelete else ""
        lines.append(
            "    sa.ForeignKeyConstraint("
            f"[{fk.parent.name!r}], [{str(fk.target_fullname)!r}]{ondelete}),"
        )
    lines.append(")")
    return "\n".join(lines)


def main() -> None:
    buf = io.StringIO()
    buf.write('"""initial schema\n\n')
    buf.write("Revision ID: 0001\nRevises:\nCreate Date: 2026-09-14\n")
    buf.write('"""\n')
    buf.write("import sqlalchemy as sa\n")
    buf.write("from sqlalchemy.dialects import postgresql\n")
    buf.write("from alembic import op\n\n")
    buf.write("revision = '0001'\n")
    buf.write("down_revision = None\n")
    buf.write("branch_labels = None\n")
    buf.write("depends_on = None\n\n\n")
    buf.write("def upgrade() -> None:\n")
    blocks = [render_table(t) for t in Base.metadata.sorted_tables]
    body = "\n\n".join(blocks) + "\n"
    body = "\n".join("    " + line for line in body.split("\n"))
    buf.write(body)
    buf.write("\n\ndef downgrade() -> None:\n")
    for t in reversed(Base.metadata.sorted_tables):
        buf.write(f"    op.drop_table({t.name!r})\n")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(buf.getvalue(), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()