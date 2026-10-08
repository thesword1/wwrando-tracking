
import urllib.request
import ssl
import certifi
import json
import traceback

from version import VERSION

LATEST_RELEASE_DOWNLOAD_PAGE_URL = "https://github.com/thesword1/wwrando-tracking/releases/latest"
LATEST_RELEASE_API_URL = "https://api.github.com/repos/thesword1/wwrando-tracking/releases/latest"

def string_to_version(string: str):
  string = string.removeprefix('v')
  if "-BETA" in string:
    string = string.split("-BETA")[0]
  if "_" in string:
    string = string.split("_")[0]
  # Tracking edition versions look like "2.5.2-tracking" or "2.5.2-tracking.3": the base
  # version followed by a build number (0 when absent).
  build = 0
  if "-tracking" in string:
    string, tracking_suffix = string.split("-tracking", 1)
    if tracking_suffix:
      build = int(tracking_suffix.removeprefix('.'))
  version = tuple(int(e) for e in string.split('.')) + (build,)
  return version

def check_for_updates():
  try:
    with urllib.request.urlopen(LATEST_RELEASE_API_URL, context=ssl.create_default_context(cafile=certifi.where())) as page:
      data = json.loads(page.read().decode())
      
      curr_version = string_to_version(VERSION)
      latest_version = string_to_version(data["tag_name"])
      latest_version_name = data["tag_name"].removeprefix('v')
      
      if "-BETA" in VERSION:
        print(latest_version >= curr_version)
        if latest_version >= curr_version:
          return latest_version_name
        else:
          return None
      else:
        if latest_version > curr_version:
          return latest_version_name
        else:
          return None
  except Exception as e:
    stack_trace = traceback.format_exc()
    error_message = "Error when checking for updates:\n" + str(e) + "\n\n" + stack_trace
    print(error_message)
    return "error"
