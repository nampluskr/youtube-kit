import re
import urllib.parse
from youtube_kit.errors import InvalidInput

_VIDEO_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{11}$")
# The list ID becomes a file name (<list-id>.playlist.json), so only the
# characters allowed in file names are accepted (no '..', '/', ':').
_PLAYLIST_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]+$")


def parse_and_normalize_url(url: str) -> tuple[str, str, str]:
    """Parse and normalize input URL or video ID.

    Returns:
        tuple of (url_type, standard_url, item_id)
        where url_type is 'video' or 'playlist'.

    Raises:
        InvalidInput: if url format is invalid or playlist ID was given without URL scheme.
    """
    if not isinstance(url, str):
        raise InvalidInput(f"URL must be a string, got {type(url).__name__}")

    url = url.strip()
    if not url:
        raise InvalidInput("URL cannot be empty")

    # Bare 11-character video ID
    if _VIDEO_ID_REGEX.match(url):
        video_id = url
        return "video", f"https://www.youtube.com/watch?v={video_id}", video_id

    # If it doesn't look like a URL (no scheme / netloc), reject it
    if "://" not in url and not url.startswith("//"):
        # e.g., bare playlist ID or random text like 'abc'
        raise InvalidInput(f"Invalid YouTube URL or video ID: {url!r}")

    parsed = urllib.parse.urlparse(url)
    hostname = (parsed.hostname or "").lower()

    # Supported hostnames
    valid_hosts = (
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
    )

    if not any(hostname == h or hostname.endswith("." + h) for h in valid_hosts):
        raise InvalidInput(f"Not a recognized YouTube domain: {hostname!r}")

    # Case 1: youtu.be/<video_id>
    if hostname == "youtu.be" or hostname.endswith(".youtu.be"):
        path = parsed.path.strip("/")
        parts = path.split("/")
        if parts and _VIDEO_ID_REGEX.match(parts[0]):
            video_id = parts[0]
            return "video", f"https://www.youtube.com/watch?v={video_id}", video_id
        raise InvalidInput(f"Invalid youtu.be URL: {url!r}")

    # Case 2: youtube.com
    path = parsed.path.rstrip("/")
    query_params = urllib.parse.parse_qs(parsed.query)

    # Check for watch URL: /watch?v=<video_id>
    if path == "/watch" or path.endswith("/watch"):
        v_list = query_params.get("v")
        if v_list and _VIDEO_ID_REGEX.match(v_list[0]):
            video_id = v_list[0]
            return "video", f"https://www.youtube.com/watch?v={video_id}", video_id
        raise InvalidInput(f"Invalid or missing video ID in watch URL: {url!r}")

    # Check for /shorts/<video_id>
    if "/shorts/" in path:
        parts = path.split("/shorts/")
        if len(parts) > 1:
            candidate = parts[1].split("/")[0]
            if _VIDEO_ID_REGEX.match(candidate):
                return "video", f"https://www.youtube.com/watch?v={candidate}", candidate
        raise InvalidInput(f"Invalid shorts URL: {url!r}")

    # Check for /live/<video_id>
    if "/live/" in path:
        parts = path.split("/live/")
        if len(parts) > 1:
            candidate = parts[1].split("/")[0]
            if _VIDEO_ID_REGEX.match(candidate):
                return "video", f"https://www.youtube.com/watch?v={candidate}", candidate
        raise InvalidInput(f"Invalid live URL: {url!r}")

    # Check for /playlist?list=<list_id>
    if path == "/playlist" or path.endswith("/playlist"):
        list_items = query_params.get("list")
        if list_items and _PLAYLIST_ID_REGEX.match(list_items[0]):
            list_id = list_items[0]
            return "playlist", f"https://www.youtube.com/playlist?list={list_id}", list_id
        raise InvalidInput(f"Missing or invalid playlist ID in playlist URL: {url!r}")

    raise InvalidInput(f"Unrecognized YouTube URL path or format: {url!r}")
