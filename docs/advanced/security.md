# Security Layer

## Overview

The Crawl4AI RAG MCP Server implements a comprehensive multi-layered security system to protect against SQL injection, malicious input, and inappropriate content. The security layer is implemented in `core/data/dbdefense.py` and integrated throughout the application.

## Architecture

### Security Layers

```
┌─────────────────────────────────────────┐
│         User Input                      │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│    Input Sanitization Layer             │
│  (SQLInjectionDefense class)            │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  String Sanitization              │  │
│  │  - SQL keyword detection          │  │
│  │  - Pattern matching               │  │
│  │  - Length validation              │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  URL Sanitization                 │  │
│  │  - Structure validation           │  │
│  │  - Content filtering              │  │
│  │  - Adult content blocking         │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  Type Validation                  │  │
│  │  - Integer ranges                 │  │
│  │  - Boolean parsing                │  │
│  │  - Enum validation                │  │
│  └───────────────────────────────────┘  │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      Domain Blocking Layer              │
│  (blocked_domains table)                │
│                                         │
│  - Wildcard pattern matching            │
│  - Keyword filtering                    │
│  - Exact domain matching                │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│     Application Layer                   │
│  (Parameterized queries only)           │
└─────────────────────────────────────────┘
```

## SQL Injection Defense

### SQLInjectionDefense Class

The core security component that provides comprehensive input sanitization:

```python
# From core/data/dbdefense.py
class SQLInjectionDefense:
    """SQL Injection defense middleware with comprehensive input sanitization"""

    # Dangerous SQL keywords and patterns
    DANGEROUS_SQL_KEYWORDS = [
        # SQL Commands
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
        'TRUNCATE', 'EXEC', 'EXECUTE', 'UNION', 'JOIN', 'MERGE',

        # SQL Functions
        'CHAR', 'CONCAT', 'SUBSTRING', 'ASCII', 'HEX', 'UNHEX',
        'LOAD_FILE', 'INTO OUTFILE', 'INTO DUMPFILE',

        # SQL Injection Patterns
        'OR 1=1', 'OR 1=0', 'AND 1=1', 'AND 1=0',
        "' OR '1'='1", '" OR "1"="1',

        # Comments and terminators
        '--', '/*', '*/', '#', ';--', '/**/', 'COMMENT',

        # Database introspection
        'INFORMATION_SCHEMA', 'SYSOBJECTS', 'SYSCOLUMNS',

        # Script injection
        '<SCRIPT', 'JAVASCRIPT:', 'ONERROR=', 'ONLOAD=',

        # Time-based attacks
        'SLEEP(', 'BENCHMARK(', 'WAITFOR DELAY',

        # Stacked queries
        '; DROP', '; DELETE', '; UPDATE', '; INSERT',
    ]
```

### String Sanitization

Comprehensive string input validation:

```python
# From core/data/dbdefense.py
@staticmethod
def sanitize_string(value: str, max_length: Optional[int] = None,
                   field_name: str = "input") -> str:
    """
    Sanitize a string input to prevent SQL injection

    Args:
        value: Input string to sanitize
        max_length: Maximum allowed length
        field_name: Name of the field (for error messages)

    Returns:
        Sanitized string

    Raises:
        ValueError: If input contains dangerous patterns
    """
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")

    # Check for NULL bytes and dangerous characters
    for char in DANGEROUS_CHARS:
        if char in value:
            raise ValueError(f"{field_name} contains dangerous characters")

    # Convert to uppercase for keyword checking
    value_upper = value.upper()

    # Check for dangerous SQL keywords
    for keyword in DANGEROUS_SQL_KEYWORDS:
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, value_upper):
            raise ValueError(f"{field_name} contains potentially dangerous SQL pattern: {keyword}")

    # Check for SQL injection patterns
    if re.search(r"['\";].*(\bOR\b|\bAND\b).*['\";=]", value_upper):
        raise ValueError(f"{field_name} contains SQL injection pattern")

    # Check for stacked queries
    if re.search(r';[\s]*\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b', value_upper):
        raise ValueError(f"{field_name} contains stacked query pattern")

    # Check maximum length
    if max_length and len(value) > max_length:
        raise ValueError(f"{field_name} exceeds maximum length of {max_length} characters")

    # Normalize unicode characters
    value = value.encode('utf-8', errors='ignore').decode('utf-8')

    return value
```

### URL Sanitization

Advanced URL validation with content filtering:

```python
# From core/data/dbdefense.py
@staticmethod
def sanitize_url(url: str) -> str:
    """
    Sanitize and validate a URL input

    Args:
        url: URL to sanitize

    Returns:
        Sanitized URL

    Raises:
        ValueError: If URL is invalid or dangerous
    """
    # Length check
    if len(url) > MAX_LENGTHS['url']:
        raise ValueError(f"URL exceeds maximum length of {MAX_LENGTHS['url']}")

    # Check for dangerous characters
    for char in DANGEROUS_CHARS:
        if char in url:
            raise ValueError("URL contains dangerous characters")

    # Adult content filter
    ADULT_CONTENT_WORDS = [
        'dick', 'pussy', 'cock', 'tits', 'boobs', 'slut', 'cunt', 'fuck',
        'anal', 'cum', 'throat', 'deepthroat', 'rape', 'incest', 'porn',
        'xxx', 'nsfw', 'nude', 'naked', 'sex', 'hentai', 'milf', ...
    ]

    # Check for adult content
    url_lower = url.lower()
    for word in ADULT_CONTENT_WORDS:
        if word in url_lower:
            raise ValueError(f"URL contains inappropriate content keyword: {word}")

    # Check for SQL injection in query parameters
    sql_in_params_pattern = r'[?&=][^&]*\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|EXEC)\b'
    if re.search(sql_in_params_pattern, url.upper()):
        raise ValueError("URL contains SQL keywords in query parameters")

    # Validate URL structure
    if '://' in url:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid URL structure")

    return url
```

## Domain Blocking

### Database-Backed Blocklist

The system maintains a database table of blocked domains:

```sql
-- From core/data/storage.py - init_database()
CREATE TABLE IF NOT EXISTS blocked_domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Pattern Matching

Three types of blocking patterns are supported:

1. **Wildcard TLD**: `*.ru` blocks all .ru domains
2. **Keyword Matching**: `*porn*` blocks any URL containing "porn"
3. **Exact Domain**: `example.com` blocks exactly that domain

```python
# From core/data/storage.py
def is_domain_blocked(self, url: str) -> Dict[str, Any]:
    """
    Check if a URL matches any blocked domain patterns.
    Supports wildcard patterns (*.ru) and keyword matching (*porn*)
    """
    parsed = urlparse(url.lower())
    domain = parsed.netloc or parsed.path
    full_url = url.lower()

    patterns = self.execute_with_retry('SELECT pattern, description FROM blocked_domains').fetchall()

    for pattern, description in patterns:
        pattern_lower = pattern.lower()

        # Handle wildcard at start: *.ru matches anything ending with .ru
        if pattern_lower.startswith('*.'):
            suffix = pattern_lower[1:]  # Remove the *
            if domain.endswith(suffix):
                return {"blocked": True, "pattern": pattern, "reason": description}

        # Handle wildcards on both sides: *porn* matches anywhere
        elif pattern_lower.startswith('*') and pattern_lower.endswith('*'):
            keyword = pattern_lower[1:-1]  # Remove both *
            if keyword in full_url or keyword in domain:
                return {"blocked": True, "pattern": pattern, "reason": description}

        # Exact domain match
        elif pattern_lower == domain:
            return {"blocked": True, "pattern": pattern, "reason": description}

    return {"blocked": False, "url": url}
```

### Default Blocklist

Initial blocked patterns are populated on first run:

```python
# From core/data/storage.py - init_database()
if blocked_count == 0:
    initial_blocks = [
        ("*.ru", "Block all Russian domains"),
        ("*.cn", "Block all Chinese domains"),
        ("*porn*", "Block URLs containing 'porn'"),
        ("*sex*", "Block URLs containing 'sex'"),
        ("*escort*", "Block URLs containing 'escort'"),
        ("*massage*", "Block URLs containing 'massage'")
    ]
    self.db.executemany(
        "INSERT OR IGNORE INTO blocked_domains (pattern, description) VALUES (?, ?)",
        initial_blocks
    )
```

### Managing Blocked Domains

#### Add Blocked Domain

```python
# From core/data/storage.py
def add_blocked_domain(self, pattern: str, description: str = "") -> Dict[str, Any]:
    """Add a domain pattern to the blocklist"""
    try:
        with self.transaction():
            self.execute_with_retry(
                'INSERT INTO blocked_domains (pattern, description) VALUES (?, ?)',
                (pattern, description)
            )
        return {"success": True, "pattern": pattern, "description": description}
    except sqlite3.IntegrityError:
        return {"success": False, "error": f"Pattern '{pattern}' already exists"}
```

#### Remove Blocked Domain (Protected)

Requires authorization keyword from environment variable:

```python
# From core/data/storage.py
def remove_blocked_domain(self, pattern: str, keyword: str = "") -> Dict[str, Any]:
    """Remove a domain pattern from the blocklist (requires authorization keyword)"""
    # Authorization check
    REQUIRED_KEYWORD = os.getenv("BLOCKED_DOMAIN_KEYWORD", "")
    if not REQUIRED_KEYWORD or keyword != REQUIRED_KEYWORD:
        return {"success": False, "error": "Unauthorized"}

    with self.transaction():
        cursor = self.execute_with_retry(
            'DELETE FROM blocked_domains WHERE pattern = ?',
            (pattern,)
        )

        if cursor.rowcount == 0:
            return {"success": False, "error": f"Pattern '{pattern}' not found"}

        return {"success": True, "pattern": pattern, "removed": True}
```

#### List Blocked Domains

```python
# From core/data/storage.py
def list_blocked_domains(self) -> Dict[str, Any]:
    """List all blocked domain patterns"""
    results = self.execute_with_retry(
        'SELECT pattern, description, created_at FROM blocked_domains ORDER BY created_at DESC'
    ).fetchall()

    blocked_list = [
        {"pattern": pattern, "description": description, "created_at": created_at}
        for pattern, description, created_at in results
    ]

    return {"success": True, "blocked_domains": blocked_list, "count": len(blocked_list)}
```

## Type Validation

### Integer Validation

```python
# From core/data/dbdefense.py
@staticmethod
def sanitize_integer(value: Any, min_val: Optional[int] = None,
                    max_val: Optional[int] = None, field_name: str = "value") -> int:
    """
    Sanitize and validate an integer input

    Args:
        value: Value to convert to integer
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        field_name: Name of the field (for error messages)

    Returns:
        Validated integer

    Raises:
        ValueError: If value is not a valid integer or out of range
    """
    try:
        int_value = int(value)
    except (ValueError, TypeError):
        raise ValueError(f"{field_name} must be a valid integer")

    if min_val is not None and int_value < min_val:
        raise ValueError(f"{field_name} must be at least {min_val}")

    if max_val is not None and int_value > max_val:
        raise ValueError(f"{field_name} must be at most {max_val}")

    return int_value
```

### Boolean Validation

```python
# From core/data/dbdefense.py
@staticmethod
def sanitize_boolean(value: Any, field_name: str = "value") -> bool:
    """
    Sanitize and validate a boolean input

    Args:
        value: Value to convert to boolean
        field_name: Name of the field (for error messages)

    Returns:
        Boolean value

    Raises:
        ValueError: If value cannot be converted to boolean
    """
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        value_lower = value.lower()
        if value_lower in ('true', '1', 'yes', 'on'):
            return True
        elif value_lower in ('false', '0', 'no', 'off'):
            return False

    raise ValueError(f"{field_name} must be a boolean value")
```

### Retention Policy Validation

```python
# From core/data/dbdefense.py
@staticmethod
def sanitize_retention_policy(policy: str) -> str:
    """
    Validate retention policy against whitelist

    Args:
        policy: Retention policy string

    Returns:
        Validated policy

    Raises:
        ValueError: If policy is not in whitelist
    """
    VALID_POLICIES = {'permanent', 'session_only', '30_days'}

    if not isinstance(policy, str):
        raise ValueError("Retention policy must be a string")

    policy_lower = policy.lower()

    if policy_lower not in VALID_POLICIES:
        raise ValueError(f"Invalid retention policy. Must be one of: {', '.join(VALID_POLICIES)}")

    return policy_lower
```

### Tag Sanitization

```python
# From core/data/dbdefense.py
@staticmethod
def sanitize_tags(tags: str) -> str:
    """
    Sanitize comma-separated tags

    Args:
        tags: Comma-separated tag string

    Returns:
        Sanitized tags string

    Raises:
        ValueError: If tags contain dangerous patterns
    """
    if not tags:
        return ""

    # Check overall length
    sanitized = SQLInjectionDefense.sanitize_string(
        tags,
        max_length=MAX_LENGTHS['tags'],
        field_name="tags"
    )

    # Split and validate individual tags
    tag_list = [tag.strip() for tag in sanitized.split(',')]

    for tag in tag_list:
        if tag and len(tag) > MAX_LENGTHS['tag']:
            raise ValueError(f"Individual tag exceeds maximum length of {MAX_LENGTHS['tag']}")

        # Tags: alphanumeric, spaces, hyphens, underscores only
        if tag and not re.match(r'^[a-zA-Z0-9\s\-_]+$', tag):
            raise ValueError(f"Tag contains invalid characters: {tag}")

    return sanitized
```

## Convenience Functions

Pre-configured sanitization for common operations:

```python
# From core/data/dbdefense.py

def sanitize_search_params(query: str, limit: int = 5, tags: Optional[str] = None) -> Dict[str, Any]:
    """Sanitize search parameters"""
    result = {
        'query': SQLInjectionDefense.sanitize_string(query, max_length=1000, field_name='query'),
        'limit': SQLInjectionDefense.sanitize_integer(limit, min_val=1, max_val=1000, field_name='limit')
    }

    if tags:
        result['tags'] = SQLInjectionDefense.sanitize_tags(tags)

    return result

def sanitize_crawl_params(url: str, tags: Optional[str] = None,
                         retention_policy: Optional[str] = None) -> Dict[str, Any]:
    """Sanitize crawl parameters"""
    result = {'url': SQLInjectionDefense.sanitize_url(url)}

    if tags:
        result['tags'] = SQLInjectionDefense.sanitize_tags(tags)

    if retention_policy:
        result['retention_policy'] = SQLInjectionDefense.sanitize_retention_policy(retention_policy)

    return result

def sanitize_block_domain_params(pattern: str, description: Optional[str] = None,
                                 keyword: Optional[str] = None) -> Dict[str, Any]:
    """Sanitize block domain parameters"""
    result = {'pattern': SQLInjectionDefense.sanitize_pattern(pattern)}

    if description:
        result['description'] = SQLInjectionDefense.sanitize_string(
            description, max_length=1000, field_name='description'
        )

    if keyword:
        result['keyword'] = SQLInjectionDefense.sanitize_string(
            keyword, max_length=100, field_name='keyword'
        )

    return result
```

## API Integration

All API endpoints use sanitization before processing:

```python
# From api/api.py

@app.post("/api/v1/crawl/store")
async def crawl_and_store(request: CrawlStoreRequest, session_info: Dict = Depends(verify_api_key)):
    try:
        # Sanitize all inputs
        sanitized = sanitize_crawl_params(
            url=request.url,
            tags=request.tags,
            retention_policy=request.retention_policy
        )

        result = await rag_system.crawl_and_store(
            sanitized['url'],
            retention_policy=sanitized.get('retention_policy', 'permanent'),
            tags=sanitized.get('tags', '')
        )
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

## Maximum Lengths

Enforced limits prevent buffer overflow and denial of service:

```python
# From core/data/dbdefense.py
MAX_LENGTHS = {
    'url': 2048,           # Maximum URL length
    'query': 1000,         # Search query
    'tag': 100,            # Individual tag
    'tags': 500,           # Comma-separated tags
    'description': 1000,   # Domain block description
    'pattern': 200,        # Domain block pattern
    'keyword': 100,        # Authorization keyword
    'filter': 100,         # Filter parameter
    'title': 500,          # Page title
}
```

## Best Practices

### 1. Always Sanitize User Input

Never trust user input. All data from users, API calls, or external sources must be sanitized:

```python
# ❌ Bad - Direct use of user input
url = request.url
result = database.crawl(url)

# ✅ Good - Sanitize first
sanitized_url = SQLInjectionDefense.sanitize_url(request.url)
result = database.crawl(sanitized_url)
```

### 2. Use Parameterized Queries

Always use parameterized queries, never string concatenation:

```python
# ❌ Bad - SQL injection vulnerability
query = f"SELECT * FROM content WHERE url = '{url}'"
db.execute(query)

# ✅ Good - Parameterized query
db.execute("SELECT * FROM content WHERE url = ?", (url,))
```

### 3. Validate Before Storage

Sanitize data before storing, not just before querying:

```python
# Sanitize on the way in
sanitized_tags = SQLInjectionDefense.sanitize_tags(user_tags)
database.store_content(url, tags=sanitized_tags)
```

### 4. Configure Domain Blocking

Set up appropriate domain blocks for your use case:

```bash
# Add your own blocked patterns
curl -X POST http://localhost:8080/api/v1/blocked-domains \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"pattern": "*.spam-domain.com", "description": "Known spam domain"}'
```

### 5. Protect Unblock Operations

Set authorization keyword in environment:

```bash
# In .env file
BLOCKED_DOMAIN_KEYWORD=your-secure-keyword-here
```

## Troubleshooting

### Issue: Legitimate URLs Being Blocked

**Symptoms**: Valid URLs are rejected with "dangerous pattern" error

**Solutions:**
1. Check if URL contains SQL keywords in legitimate context
2. Review URL content filter words
3. Adjust pattern matching in `sanitize_url()`
4. Whitelist specific domains if needed

### Issue: Domain Block Not Working

**Symptoms**: Blocked URLs are still being crawled

**Solutions:**
1. Verify pattern syntax (*.ru for TLD, *keyword* for content)
2. Check pattern is in database: `GET /api/v1/blocked-domains`
3. Ensure `is_domain_blocked()` is called before crawling
4. Check for case sensitivity issues

### Issue: Authorization Failure for Unblock

**Symptoms**: Cannot remove blocked domains

**Solutions:**
1. Verify `BLOCKED_DOMAIN_KEYWORD` is set in environment
2. Check keyword matches exactly (case-sensitive)
3. Restart server after environment changes
4. Check API logs for authorization errors

## Security Checklist

- [x] SQL injection protection via keyword detection
- [x] Parameterized queries throughout application
- [x] URL structure validation
- [x] Adult content filtering
- [x] Domain blocklist with wildcard support
- [x] Input length limits enforced
- [x] Type validation for all inputs
- [x] Tag format validation
- [x] Authorization for sensitive operations
- [x] Null byte and special character filtering
- [x] Unicode normalization
- [x] Stacked query detection
- [x] Comment injection prevention

## References

- **Implementation**: `/home/robiloo/Documents/mcpragcrawl4ai/core/data/dbdefense.py`
- **Domain Blocking**: `/home/robiloo/Documents/mcpragcrawl4ai/core/data/storage.py`
- **API Integration**: `/home/robiloo/Documents/mcpragcrawl4ai/api/api.py`
- **MCP Integration**: `/home/robiloo/Documents/mcpragcrawl4ai/core/rag_processor.py`

## See Also

- [API Endpoints](../api/endpoints.md)
- [Troubleshooting Guide](../guides/troubleshooting.md)
- [Deployment Guide](../guides/deployment.md)
