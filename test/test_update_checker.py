from wwr_ui.update_checker import string_to_version

def test_tracking_versions_compare_by_build_number():
  assert string_to_version("2.5.2-tracking") == (2, 5, 2, 0)
  assert string_to_version("v2.5.2-tracking.1") == (2, 5, 2, 1)
  assert string_to_version("2.5.2-tracking.1_abc1234") == (2, 5, 2, 1)
  assert string_to_version("v2.5.2-tracking.2") > string_to_version("2.5.2-tracking.1")
  assert string_to_version("v2.5.3-tracking") > string_to_version("2.5.2-tracking.9")

def test_plain_versions_still_parse():
  assert string_to_version("v1.10.0") == (1, 10, 0, 0)
