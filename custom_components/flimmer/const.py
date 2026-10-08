"""Flimmer: constants."""

DOMAIN = "flimmer"
CONF_URL = "url"
CONF_KEY = "api_key"

# Read again at least this often; changes are pushed in between.
SCAN_SECONDS = 60
# The event fired on Home Assistant's bus for every change the server tells.
EVENT_CHANGE = "flimmer_change"
# What the server tells about, and what Home Assistant reads again for.
REFRESH_ON = {"playing", "playback", "library", "channels", "workers", "peers", "hello", "resume"}
