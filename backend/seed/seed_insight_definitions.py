"""Idempotent CLI that upserts insight_definitions rows into the agent's own
Postgres. Add one entry per insight_type here as new insights are configured.

Usage:
    uv run python -m seed.seed_insight_definitions
"""

import asyncio

from sqlalchemy import select

from app.db.models import InsightDefinition
from app.db.session import AgentSessionLocal
from app.logging_conf import configure_logging, get_logger

logger = get_logger(__name__)

INSIGHT_DEFINITIONS = [
    {
        "insight_type": "clients_by_balance_city",
        "target_type": "clients",
        "from_table_name": "clients",
        "config_yaml_path": "clients_by_balance_city.yaml",
        # Fixed where-clause shape for this insight type -- AND/OR, columns,
        # and operators are authored here and never change per request. Only
        # each :slot_name's bound value changes, based on the user's input
        # (or the slot's `default` below when the user didn't mention it).
        "where_clause_template": "account_balance >= :acct_bal AND city = :city",
        "slot_definitions": {
            "slots": [
                {
                    "slot_name": "acct_bal",
                    "column_name": "account_balance",
                    "expected_type": "numeric",
                    "allowed_operators": ["gt", "gte", "lt", "lte", "eq"],
                    "required": False,
                    "default": {"operator": "gte", "value": 10000},
                },
                {
                    "slot_name": "city",
                    "column_name": "city",
                    "expected_type": "string",
                    "allowed_operators": ["eq", "like"],
                    "required": False,
                    "default": {"operator": "eq", "value": "ny"},
                },
            ]
        },
    },
    {
        "insight_type": "accounts_by_brokerage_sweep_cash",
        "target_type": "accounts",
        "from_table_name": "accounts",
        "config_yaml_path": "accounts_by_brokerage_sweep_cash.yaml",
        # curr_asset threshold is a plain numeric slot; brkg_sweep_cash is
        # compared against a *percentage* of curr_asset -- the multiplication
        # is fixed template SQL, only the percentage's bound value (0-1
        # fraction) changes per request. brkg_sweep_cash_rank binds an
        # expanding IN list.
        "where_clause_template": (
            "curr_asset >= :curr_asset AND brkg_sweep_cash >= (curr_asset * :brkg_sweep_pct) "
            "AND brkg_sweep_cash_rank IN :brkg_sweep_cash_rank"
        ),
        "slot_definitions": {
            "slots": [
                {
                    "slot_name": "curr_asset",
                    "column_name": "curr_asset",
                    "expected_type": "numeric",
                    "allowed_operators": ["gt", "gte", "lt", "lte", "eq"],
                    "required": False,
                    "default": {"operator": "gte", "value": 10000},
                },
                {
                    "slot_name": "brkg_sweep_pct",
                    "column_name": "brkg_sweep_cash",
                    "expected_type": "percentage",
                    "allowed_operators": ["gte"],
                    "required": False,
                    "default": {"operator": "gte", "value": 0.02},
                },
                {
                    "slot_name": "brkg_sweep_cash_rank",
                    "column_name": "brkg_sweep_cash_rank",
                    "expected_type": "numeric_list",
                    "allowed_operators": ["in"],
                    "required": False,
                    "default": {"operator": "in", "value": [1, 2, 3, 4]},
                },
            ]
        },
    },
]


async def seed() -> None:
    async with AgentSessionLocal() as session:
        for definition in INSIGHT_DEFINITIONS:
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
                existing.where_clause_template = definition["where_clause_template"]
            else:
                session.add(
                    InsightDefinition(
                        insight_type=definition["insight_type"],
                        target_type=definition["target_type"],
                        from_table_name=definition["from_table_name"],
                        config_yaml_path=definition["config_yaml_path"],
                        slot_definitions=definition["slot_definitions"],
                        where_clause_template=definition["where_clause_template"],
                    )
                )
            logger.info("seeded_insight_definition", insight_type=definition["insight_type"])
        await session.commit()


def main() -> None:
    configure_logging()
    asyncio.run(seed())


if __name__ == "__main__":
    main()
