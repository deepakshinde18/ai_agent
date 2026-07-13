"""Idempotent CLI that upserts insight_definitions rows into the agent's own
Postgres. Add one entry per insight_type here as new insights are configured.

Usage:
    uv run python -m seed.seed_insight_definitions
"""

import asyncio

from sqlalchemy import select

from app.db.models import InsightDefinition
from app.db.session import AgentSessionLocal
from app.graph.sql_builder import generate_generic_where_template
from app.logging_conf import configure_logging, get_logger

logger = get_logger(__name__)

INSIGHT_DEFINITIONS = [
    {
        "insight_type": "clients_by_balance_city",
        "target_type": "clients",
        "from_table_name": "clients",
        "config_yaml_path": "clients_by_balance_city.yaml",
        "slot_definitions": {
            "slots": [
                {
                    "slot_name": "acct_bal",
                    "column_name": "account_balance",
                    "expected_type": "numeric",
                    "allowed_operators": ["gt", "gte", "lt", "lte", "eq"],
                    "required": False,
                },
                {
                    "slot_name": "city",
                    "column_name": "city",
                    "expected_type": "string",
                    "allowed_operators": ["eq", "like"],
                    "required": False,
                },
            ]
        },
    },
]


async def seed() -> None:
    async with AgentSessionLocal() as session:
        for definition in INSIGHT_DEFINITIONS:
            slot_names = [s["slot_name"] for s in definition["slot_definitions"]["slots"]]
            where_template = generate_generic_where_template(slot_names)

            existing = await session.scalar(
                select(InsightDefinition).where(
                    InsightDefinition.insight_type == definition["insight_type"]
                )
            )
            if existing:
                existing.target_type = definition["target_type"]
                existing.from_table_name = definition["from_table_name"]
                existing.config_yaml_path = definition["config_yaml_path"]
                existing.slot_definitions = definition["slot_definitions"]
                existing.where_clause_template = where_template
            else:
                session.add(
                    InsightDefinition(
                        insight_type=definition["insight_type"],
                        target_type=definition["target_type"],
                        from_table_name=definition["from_table_name"],
                        config_yaml_path=definition["config_yaml_path"],
                        slot_definitions=definition["slot_definitions"],
                        where_clause_template=where_template,
                    )
                )
            logger.info("seeded_insight_definition", insight_type=definition["insight_type"])
        await session.commit()


def main() -> None:
    configure_logging()
    asyncio.run(seed())


if __name__ == "__main__":
    main()
