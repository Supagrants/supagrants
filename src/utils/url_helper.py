# utils/url_helper.py

import re
from urllib.parse import urlparse, urlunparse, quote, unquote
import logging

logger = logging.getLogger(__name__)

def is_valid_url(url: str) -> bool:
    """
    Validate the URL format.

    Args:
        url (str): The URL to validate.

    Returns:
        bool: True if valid, False otherwise.
    """
    # Comprehensive URL regex pattern
    url_regex = re.compile(
        r'^(https?://)'  # http:// or https://
        r'('
            r'('
                r'([A-Za-z0-9-]+\.)+[A-Za-z]{2,}'  # Domain...
            r')'
            r'|'
            r'(localhost)'  # localhost...
            r'|'
            r'(\[?[A-Fa-f0-9:]+\]?)'  # IPv6 or IPv4
        r')'
        r'(:\d{1,5})?'  # Optional port (1-65535)
        r'(/[\w\-.~:/?#\[\]@!$&\'()*+,;=%]*)?'  # Optional path and query
        r'$', re.IGNORECASE
    )

    match = re.match(url_regex, url)
    if match:
        port = match.group(5)
        if port:
            port_num = int(port.lstrip(':'))
            if not (1 <= port_num <= 65535):
                logger.debug(f"Invalid port number: {port_num}")
                return False
        logger.debug(f"URL '{url}' is valid.")
        return True
    else:
        logger.debug(f"URL '{url}' is invalid.")
        return False

def normalize_url(url: str) -> str:
    """
    Normalize URL to avoid duplication by:
    - Lowercasing the scheme and network location.
    - Removing default ports.
    - Removing fragments and query parameters.
    - Resolving redundant path segments.
    - Ensuring consistent trailing slashes.
    - Converting Unicode domain names to punycode.

    Args:
        url (str): The URL to normalize.

    Returns:
        str: Normalized URL as string.
    """
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        # Handle Internationalized Domain Names (IDN)
        if 'xn--' not in netloc:
            hostname = parsed.hostname.encode('idna').decode('ascii') if parsed.hostname else ''
            if parsed.port:
                netloc = f"{hostname}:{parsed.port}"
            else:
                netloc = hostname

        # Remove default ports
        if (scheme == 'http' and parsed.port == 80) or (scheme == 'https' and parsed.port == 443):
            netloc = parsed.hostname.encode('idna').decode('ascii') if parsed.hostname else netloc

        # Normalize path
        path = unquote(parsed.path)  # Decode percent-encoded characters
        path = re.sub(r'/+', '/', path)  # Replace multiple slashes with single slash
        path = re.sub(r'/\./', '/', path)  # Remove /./
        path = re.sub(r'/[^/]+/\.\./', '/', path)  # Remove /something/../
        path = re.sub(r'/$', '/', path)  # Ensure single trailing slash

        # Re-encode path
        path = quote(path, safe="/-_.~")

        # Reconstruct the URL without query and fragment
        normalized_url = urlunparse((scheme, netloc, path, '', '', ''))
        
        logger.debug(f"Normalized URL: Original='{url}' | Normalized='{normalized_url}'")
        return normalized_url
    except Exception as e:
        logger.error(f"Error normalizing URL '{url}': {e}")
        return url  # Return the original URL if normalization fails

def get_domain(url: str) -> str:
    """
    Extract the domain from a URL.

    Args:
        url (str): The URL to extract the domain from.

    Returns:
        str: The domain of the URL.
    """
    try:
        parsed = urlparse(url)
        domain = parsed.hostname.lower() if parsed.hostname else ''
        logger.debug(f"Extracted domain '{domain}' from URL '{url}'.")
        return domain
    except Exception as e:
        logger.error(f"Error extracting domain from URL '{url}': {e}")
        return ''

def strip_query_and_fragment(url: str) -> str:
    """
    Remove query parameters and fragments from a URL.

    Args:
        url (str): The URL to strip.

    Returns:
        str: The URL without query and fragment.
    """
    try:
        parsed = urlparse(url)
        stripped_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
        logger.debug(f"Stripped URL: Original='{url}' | Stripped='{stripped_url}'")
        return stripped_url
    except Exception as e:
        logger.error(f"Error stripping query and fragment from URL '{url}': {e}")
        return url

def ensure_trailing_slash(url: str) -> str:
    """
    Ensure that the URL ends with a trailing slash.

    Args:
        url (str): The URL to modify.

    Returns:
        str: The URL with a trailing slash.
    """
    if not url.endswith('/'):
        logger.debug(f"Adding trailing slash to URL '{url}'.")
        return url + '/'
    return url
