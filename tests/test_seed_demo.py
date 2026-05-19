from __future__ import annotations

from uuid import uuid4

import pytest

from scripts.seed_demo import reset_demo_data


class _ScalarResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _ExecuteResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return _ScalarResult(self._values)


class _FakeSession:
    def __init__(self, select_results):
        self.select_results = list(select_results)
        self.statements = []
        self.committed = False

    async def execute(self, statement):
        self.statements.append(statement)
        if getattr(statement, "__visit_name__", "") == "select":
            return _ExecuteResult(self.select_results.pop(0))
        return _ExecuteResult([])

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_reset_demo_data_deletes_agent_and_approval_rows_before_users():
    session = _FakeSession(
        select_results=[
            [uuid4()],  # user ids
            [uuid4()],  # agent run ids
            [uuid4()],  # approval request ids
        ]
    )

    await reset_demo_data(session)

    delete_tables = [
        statement.table.name for statement in session.statements if getattr(statement, "__visit_name__", "") == "delete"
    ]

    assert delete_tables.index("approval_steps") < delete_tables.index("approval_requests")
    assert delete_tables.index("action_drafts") < delete_tables.index("approval_requests")
    assert delete_tables.index("approval_requests") < delete_tables.index("users")
    assert delete_tables.index("agent_steps") < delete_tables.index("agent_runs")
    assert delete_tables.index("agent_runs") < delete_tables.index("users")
    assert session.committed is True
