from __future__ import annotations

import os
from typing import TYPE_CHECKING

import daytona
import pytest
from langchain_tests.integration_tests import SandboxIntegrationTests

from langchain_daytona import DaytonaSandbox

if TYPE_CHECKING:
    from collections.abc import Iterator

    from deepagents.backends.protocol import SandboxBackendProtocol


class TestDaytonaSandboxStandard(SandboxIntegrationTests):
    @pytest.fixture(scope="class")
    def sandbox(self) -> Iterator[SandboxBackendProtocol]:
        # Skip if API key not available
        if not os.environ.get("DAYTONA_API_KEY") and not os.environ.get("DAYTONA_JWT_TOKEN"):
            pytest.skip(
                "DAYTONA_API_KEY or DAYTONA_JWT_TOKEN not set; skipping Daytona integration tests"
            )

        sdk = daytona.Daytona()
        sandbox = sdk.create()
        backend = DaytonaSandbox(sandbox=sandbox)
        try:
            yield backend
        finally:
            sandbox.delete()
