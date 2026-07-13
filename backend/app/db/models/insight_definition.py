import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InsightDefinition(Base):
    """Metadata row for one insight_type: which target table/where-clause
    template/slots to use when building the SQL query for that intent.

    `slot_definitions` shape (developer-authored, trusted -- `column_name` here
    is the whitelist that RAG-resolved columns are cross-checked against
    before ever being interpolated into SQL)::

        {
          "slots": [
            {
              "slot_name": "acct_bal",
              "column_name": "account_balance",
              "expected_type": "numeric",
              "allowed_operators": ["gt", "gte", "lt", "lte", "eq"],
              "required": false
            },
            ...
          ]
        }
    """

    __tablename__ = "insight_definitions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    insight_type: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    from_table_name: Mapped[str] = mapped_column(String(200), nullable=False)
    where_clause_template: Mapped[str] = mapped_column(Text, nullable=False)
    slot_definitions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    config_yaml_path: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
