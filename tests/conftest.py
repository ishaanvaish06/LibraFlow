"""
Shared pytest fixtures.

Every test builds a fresh in-memory container, seeds it via ``libflow.seed``,
and — for API tests — installs it onto the app instance. No tests touch a
real database.
"""

from __future__ import annotations

import pytest

from libflow.api.app import app
from libflow.api.dependencies import LibraFlowContainer, build_in_memory_container
from libflow.seed import seed_library


@pytest.fixture
def container() -> LibraFlowContainer:
    c = build_in_memory_container()
    seed_library(c)
    yield c
    c.dispose()


@pytest.fixture
def alice(container: LibraFlowContainer):
    return container.user_repo.get_user("STU-ALICE")


@pytest.fixture
def admin_token(container: LibraFlowContainer) -> str:
    from libflow.api.auth import create_access_token

    admin = container.user_repo.get_user("ADMIN-01")
    assert admin is not None
    return create_access_token(admin)


@pytest.fixture
def student_token(container: LibraFlowContainer) -> str:
    from libflow.api.auth import create_access_token

    student = container.user_repo.get_user("STU-ALICE")
    assert student is not None
    return create_access_token(student)


@pytest.fixture
def client(container: LibraFlowContainer):
    from fastapi.testclient import TestClient

    # NOTE: not entered as a context manager, so the app lifespan (which would
    # build a Postgres container) never runs; the in-memory container below is
    # the one used for the request lifetime.
    app.state.container = container
    return TestClient(app)


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
