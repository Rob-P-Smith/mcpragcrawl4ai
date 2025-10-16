"""
Content cleaning and post-processing for crawled web pages
Removes navigation, boilerplate, and low-value content before embedding
"""

import re
from typing import List, Dict, Any


class ContentCleaner:
    """Clean and filter web content for better embedding quality"""

    NAVIGATION_PATTERNS = [
        r'\[.*?\]\(.*?\)',
        r'^[\s\*\-]+\[.*?\].*$',
        r'^\s*[\*\-]\s+\[.*?\]\s*\(.*?\)\s*$',
    ]

    NAV_KEYWORDS = [
        'navigation', 'menu', 'sidebar', 'breadcrumb', 'skip to',
        'table of contents', 'on this page', 'quick links',
        'sign in', 'log in', 'subscribe', 'newsletter',
        'follow us', 'social media', 'share on', 'tweet',
        'copyright ©', 'all rights reserved', '© 20',
        'privacy policy', 'terms of service', 'cookie policy',
        'back to top', 'scroll to top', 'go to top'
    ]

    SOCIAL_DOMAINS = [
        'facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com',
        'youtube.com', 'github.com', 'discord.', 'reddit.com',
        'x.com', 'bsky.app', 'bluesky'
    ]

    @staticmethod
    def clean_content(markdown: str, url: str = "") -> str:
        """
        Clean markdown content by removing navigation and boilerplate

        Args:
            markdown: Raw markdown content from crawler
            url: URL of the page (for context)

        Returns:
            Cleaned markdown with navigation removed
        """
        if not markdown:
            return ""

        lines = markdown.split('\n')
        cleaned_lines = []

        for line in lines:
            line_lower = line.lower().strip()

            if not line_lower:
                continue

            if any(keyword in line_lower for keyword in ContentCleaner.NAV_KEYWORDS):
                continue

            if any(domain in line_lower for domain in ContentCleaner.SOCIAL_DOMAINS):
                continue

            if re.match(r'^[\s\*\-]+\[.*?\]\s*\(.*?\)\s*$', line):
                continue

            if re.match(r'^\s*[\*\-]\s+(Learn|Reference|API|Community|Blog|Docs?)\s*\[', line):
                continue

            cleaned_lines.append(line)

        cleaned = '\n'.join(cleaned_lines)

        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

        return cleaned.strip()

    @staticmethod
    def filter_chunks(chunks: List[str]) -> List[str]:
        """
        Filter out low-quality chunks before embedding

        Args:
            chunks: List of content chunks

        Returns:
            Filtered list with navigation chunks removed
        """
        filtered = []

        for chunk in chunks:
            chunk_lower = chunk.lower()

            nav_count = sum(1 for keyword in ContentCleaner.NAV_KEYWORDS if keyword in chunk_lower)
            if nav_count >= 3:
                continue

            link_count = chunk.count('[') + chunk.count('](')
            word_count = len(chunk.split())
            if word_count > 0 and link_count / word_count > 0.3:
                continue

            if word_count < 10:
                continue

            if chunk.count('[') > word_count / 3:
                continue

            filtered.append(chunk)

        return filtered

    @staticmethod
    def clean_and_validate(content: str, markdown: str, url: str = "") -> Dict[str, Any]:
        """
        Clean content and validate quality

        Args:
            content: HTML content
            markdown: Markdown content
            url: Page URL

        Returns:
            Dict with cleaned content and quality metrics
        """
        text_to_clean = markdown if markdown else content

        cleaned = ContentCleaner.clean_content(text_to_clean, url)

        original_lines = len(text_to_clean.split('\n'))
        cleaned_lines = len(cleaned.split('\n'))
        reduction_ratio = (original_lines - cleaned_lines) / original_lines if original_lines > 0 else 0

        nav_count = sum(1 for keyword in ContentCleaner.NAV_KEYWORDS
                       if keyword in text_to_clean.lower())

        is_mostly_navigation = reduction_ratio > 0.7 or nav_count > 10

        return {
            "cleaned_content": cleaned,
            "original_lines": original_lines,
            "cleaned_lines": cleaned_lines,
            "reduction_ratio": reduction_ratio,
            "navigation_indicators": nav_count,
            "quality_warning": "Content appears to be mostly navigation/boilerplate" if is_mostly_navigation else None,
            "is_clean": not is_mostly_navigation
        }

    @staticmethod
    def is_error_page(content: str, title: str = "", status_code: int = 200) -> Dict[str, Any]:
        """
        Detect if page is an error/empty/rate-limited page

        Args:
            content: Page content (markdown or HTML)
            title: Page title
            status_code: HTTP status code

        Returns:
            Dict with is_error flag and reason
        """
        if not content or len(content.strip()) < 50:
            return {"is_error": True, "reason": "Empty or too short content"}

        content_lower = content.lower()
        title_lower = title.lower() if title else ""

        # Check HTTP status code
        if status_code >= 400:
            return {"is_error": True, "reason": f"HTTP {status_code} error"}

        # Error indicators in title (strong signal)
        title_error_patterns = [
            '404', 'not found', 'page not found', 'error',
            'access denied', 'forbidden', '403', '401',
            'unauthorized', 'unavailable', 'does not exist'
        ]
        if any(pattern in title_lower for pattern in title_error_patterns):
            return {"is_error": True, "reason": f"Error in title: {title}"}

        # Rate limiting / bot detection patterns
        rate_limit_patterns = [
            'rate limit', 'too many requests', 'please slow down',
            'bot detection', 'captcha', 'human verification',
            'access denied', 'blocked', 'suspicious activity',
            'verify you are human', 'security check'
        ]

        # Check for rate limiting in first 500 chars (usually appears early)
        content_sample = content_lower[:500]
        for pattern in rate_limit_patterns:
            if pattern in content_sample:
                return {"is_error": True, "reason": f"Rate limiting/bot detection: '{pattern}'"}

        # Error page patterns (but be more careful - check context)
        # Only flag if multiple indicators or if content is very short
        word_count = len(content.split())

        if word_count < 100:
            # For very short content, be more aggressive
            short_error_patterns = [
                'page not found', '404', 'not found', 'error occurred',
                'something went wrong', 'page does not exist',
                'reach this site in error', 'reached this page in error'
            ]
            if any(pattern in content_lower for pattern in short_error_patterns):
                return {"is_error": True, "reason": "Error page (short content)"}

        # For longer content, require multiple error indicators
        error_keywords = [
            'page not found', '404 error', 'page does not exist',
            'something went wrong', 'error occurred', 'cannot find',
            'reach this site in error', 'reached this page in error',
            'page you are looking for', 'page has been removed'
        ]

        error_count = sum(1 for keyword in error_keywords if keyword in content_lower)

        if error_count >= 2 and word_count < 300:
            return {"is_error": True, "reason": f"Multiple error indicators ({error_count})"}

        # Check for redirect/moved pages
        redirect_patterns = [
            'permanently moved', 'page has moved', 'redirecting',
            'this page has been moved to'
        ]
        if any(pattern in content_lower for pattern in redirect_patterns) and word_count < 200:
            return {"is_error": True, "reason": "Redirect/moved page"}

        return {"is_error": False, "reason": None}

    @staticmethod
    def extract_main_content(markdown: str) -> str:
        """
        Extract main article content, removing headers/footers

        Args:
            markdown: Full markdown content

        Returns:
            Main content section
        """
        lines = markdown.split('\n')

        start_idx = 0
        for i, line in enumerate(lines):
            if line.startswith('#') or len(line.split()) >= 20:
                start_idx = i
                break

        end_idx = len(lines)
        for i in range(len(lines) - 1, -1, -1):
            line_lower = lines[i].lower()
            if any(pattern in line_lower for pattern in ['copyright', '©', 'all rights reserved', 'privacy policy']):
                end_idx = i
                break

        main_content = '\n'.join(lines[start_idx:end_idx])

        return main_content.strip()
