"""The project imports and the package is installed correctly."""

import ops_agent


def test_package_imports() -> None:
    assert ops_agent is not None
