import unittest

from utils.url_helper import extract_valid_urls

class TestExtractValidUrls(unittest.TestCase):

    def test_full_url(self):
        # Full URL, valid
        content = "Check this out: https://example.com"
        result = extract_valid_urls(content)
        self.assertEqual(result, ["https://example.com"])

    def test_lazy_url_with_scheme(self):
        # URL with missing scheme, should be prepended with 'https://'
        content = "Visit www.example.com"
        result = extract_valid_urls(content)
        self.assertEqual(result, ["https://www.example.com"])

    def test_lazy_url_without_scheme(self):
        # URL with missing scheme, should be prepended with 'https://'
        content = "Visit example.com"
        result = extract_valid_urls(content)
        self.assertEqual(result, ["https://example.com"])

    def test_invalid_url(self):
        # Invalid URL, should be excluded
        content = "Check this invalid URL: example"
        result = extract_valid_urls(content)
        self.assertEqual(result, [])

    def test_email_address(self):
        # Email address should not be considered a URL
        content = "Contact me at test@example.com"
        result = extract_valid_urls(content)
        self.assertEqual(result, [])

    def test_email_like_substring(self):
        # String resembling an email should not be treated as URL
        content = "Check my site: test@example.com"
        result = extract_valid_urls(content)
        self.assertEqual(result, [])

    def test_malformed_url(self):
        # Malformed URL should be excluded
        content = "A malformed URL: http//example.com"
        result = extract_valid_urls(content)
        self.assertEqual(result, [])

    def test_url_with_trailing_punctuation(self):
        # URL with trailing punctuation should be cleaned
        content = "Check out this URL: https://example.com!"
        result = extract_valid_urls(content)
        self.assertEqual(result, ["https://example.com"])

    def test_duplicate_urls(self):
        # Duplicate URLs should be removed
        content = "Here are two URLs: https://example.com and https://example.com"
        result = extract_valid_urls(content)
        self.assertEqual(result, ["https://example.com"])

    def test_urls_from_entities(self):
        # If URLs are passed as entities, they should be included
        content = "Check this out!"
        entity_urls = ["https://example.com", "https://test.com"]
        result = extract_valid_urls(content, entity_urls)
        self.assertEqual(result, ["https://example.com", "https://test.com"])

    def test_multiple_valid_urls(self):
        # Test with multiple valid URLs
        content = "Visit https://example.com or www.test.com for more info"
        result = extract_valid_urls(content)
        self.assertEqual(result, ["https://example.com", "https://www.test.com"])

    def test_url_part_of_email(self):
        # URL-like string part of an email should not be extracted
        content = "Send an email to user@sub.example.com for more info"
        result = extract_valid_urls(content)
        self.assertEqual(result, [])

    def test_url_with_port(self):
        # URL with port number
        content = "Access the server at http://localhost:8080/dashboard"
        result = extract_valid_urls(content)
        self.assertEqual(result, ["http://localhost:8080/dashboard"])

    def test_ipv6_url(self):
        # URL with IPv6 address
        content = "Check the site at http://[2001:db8::1]/index.html"
        result = extract_valid_urls(content)
        self.assertEqual(result, ["http://[2001:db8::1]/index.html"])

    def test_url_with_query_parameters(self):
        # URL with query parameters
        content = "Search at https://www.example.com/search?q=openai"
        result = extract_valid_urls(content)
        self.assertEqual(result, ["https://www.example.com/search?q=openai"])

    def test_url_with_fragment(self):
        # URL with fragment
        content = "Navigate to https://example.com/page#section"
        result = extract_valid_urls(content)
        self.assertEqual(result, ["https://example.com/page#section"])

    def test_mixed_content(self):
        # Mixed valid and invalid URLs, and emails
        content = "Visit https://valid.com, invalid://invalid.com, and contact user@valid.com"
        result = extract_valid_urls(content)
        self.assertEqual(result, ["https://valid.com"])

if __name__ == "__main__":
    unittest.main()
