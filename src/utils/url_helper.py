import re
from urllib.parse import urlparse

def is_valid_url(url: str) -> bool:
    """
    Validate the URL format.

    Args:
        url (str): The URL to validate.

    Returns:
        bool: True if valid, False otherwise.
    """
    url_regex = re.compile(
        r'^(https?://)?'  # http:// or https://
        r'((([A-Za-z0-9-]+\.)+[A-Za-z]{2,})|'  # Domain...
        r'localhost|'  # localhost...
        r'(\d{1,3}\.){3}\d{1,3})'  # ...or IPv4
        r'(:\d+)?'  # Optional port
        r'(/[\w./?%&=-]*)?$'  # Optional path
    )
    return re.match(url_regex, url) is not None

def normalize_url(url: str) -> str:
    """
    Normalize URL to avoid duplication.

    :param url: The URL to normalize.

    :return: Normalized URL as string.
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or '/'
    # Remove query parameters and fragments
    normalized_url = f"{scheme}://{netloc}{path}"
    return normalized_url