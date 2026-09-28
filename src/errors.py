class YoutubeKitError(Exception):
    """Base class for all youtube-kit errors (exit code 1)."""
    exit_code = 1


class InvalidInput(YoutubeKitError):
    """Invalid URL, ID, or argument; detected before network lookup (exit code 2)."""
    exit_code = 2


class VideoUnavailable(YoutubeKitError):
    """Private, deleted, non-existent ID, or restricted video (exit code 3)."""
    exit_code = 3


class NotAvailable(YoutubeKitError):
    """Format, track, or container not available for this video, or video is live (exit code 4)."""
    exit_code = 4


class MissingDependency(YoutubeKitError):
    """Required external dependency (ffmpeg) is missing (exit code 5)."""
    exit_code = 5


class Cancelled(YoutubeKitError):
    """The caller cancelled the operation; no partial file is left (exit code 130)."""
    exit_code = 130
