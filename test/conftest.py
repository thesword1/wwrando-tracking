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


@pytest.fixture(scope="session")
def tracker_host_library(tmp_path_factory) -> Path:
  from tracker_c_host import build_host_library
  return build_host_library(tmp_path_factory.mktemp("tracker_c"))

@pytest.fixture
def tracker(tracker_host_library):
  """The tracker C runtime built for the host, with cleared mock RAM and no tables."""
  from tracker_c_host import TrackerHost
  host = TrackerHost(tracker_host_library)
  host.reset_ram()
  return host
