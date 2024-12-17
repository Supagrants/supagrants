# utils/url_helper.py

import re
from typing import List, Optional
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

def extract_valid_urls(content: str, entity_urls: Optional[List[str]] = None) -> List[str]:
    """
    Extract and validate URLs from message content and message entities.

    This function performs the following steps:
    1. Extracts potential URLs using a regex pattern.
    2. Incorporates URLs extracted from Telegram message entities.
    3. Cleans URLs by removing trailing punctuation.
    4. Prepends 'https://' to URLs missing a scheme.
    5. Validates URLs using the `is_valid_url` function.

    Args:
        content (str): The text content of the message.
        entity_urls (Optional[List[str]]): List of URLs extracted from message entities.

    Returns:
        List[str]: A list of validated and cleaned URLs.
    """
    # Initialize list to hold potential URLs
    potential_urls = []

    # Define a robust regex pattern to extract URLs with or without schemes
    # Added negative lookbehind to ensure URLs are not preceded by '@' (to ignore emails)
    url_pattern = re.compile(
        r'(?<![\w.-])'
        r'(?:https?://|www\.)?'
        r'([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'
        r'(?:/[^\s.,;!?)"\']*)?',
        re.IGNORECASE
    )

    # Extract URLs using regex
    regex_urls = re.findall(url_pattern, content)
    potential_urls.extend(regex_urls)
    logger.debug(f"URLs extracted via regex: {regex_urls}")

    # Incorporate URLs from message entities if provided
    if entity_urls:
        potential_urls.extend(entity_urls)
        logger.debug(f"URLs extracted from entities: {entity_urls}")

    # Initialize list to hold validated URLs
    extracted_urls = []

    for url in potential_urls:
        # Remove trailing punctuation
        cleaned_url = url.rstrip('.,;!?)"]\'')
        logger.debug(f"URL after stripping punctuation: '{cleaned_url}'")

        # If URL doesn't have a scheme, prepend 'https://'
        if not re.match(r'^https?://', cleaned_url, re.IGNORECASE):
            cleaned_url = 'https://' + cleaned_url
            logger.debug(f"URL after prepending scheme: '{cleaned_url}'")

        # Validate URL
        if is_valid_url(cleaned_url):
            # Additional check to ensure the URL is not part of an email
            # For example, ensure there's no '@' symbol immediately before the URL
            start_index = content.find(url)
            if start_index > 0 and content[start_index - 1] == '@':
                logger.debug(f"URL '{cleaned_url}' is part of an email and will be skipped.")
                continue  # Skip URLs that are part of an email address
            extracted_urls.append(cleaned_url)
            logger.debug(f"Valid URL added: '{cleaned_url}'")
        else:
            logger.debug(f"Invalid URL skipped: '{cleaned_url}'")

    # Remove duplicates while preserving order
    unique_urls = list(dict.fromkeys(extracted_urls))
    logger.debug(f"Unique validated URLs: {unique_urls}")

    return unique_urls

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
