import re

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