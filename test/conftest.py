import pytest
from pathlib import Path

def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]):
  for item in items:
    if Path(item.fspath).parts[-1] == "test_save.py":
      mark = pytest.mark.saving
      item.add_marker(mark)

  # Dolphin tests open emulator windows and need a local ISO, so only run them on request.
  if "dolphin" not in (config.getoption("markexpr") or ""):
    selected = [item for item in items if item.get_closest_marker("dolphin") is None]
    deselected = [item for item in items if item.get_closest_marker("dolphin") is not None]
    if deselected:
      config.hook.pytest_deselected(items=deselected)
      items[:] = selected
