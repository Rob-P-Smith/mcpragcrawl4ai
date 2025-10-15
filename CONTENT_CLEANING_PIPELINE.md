# Content Cleaning Pipeline - Complete Flow

**Purpose:** Remove navigation, boilerplate, and low-value content before embedding to improve RAG search quality.

---

## Pipeline Overview

```
Web Page → Crawl4AI → ContentCleaner (2 stages) → Chunks → Filter → Embeddings
```

### Stage 1: Initial Crawl (Crawl4AI)
### Stage 2: Content Cleaning (ContentCleaner)
### Stage 3: Chunk Filtering (ContentCleaner)

---

## Stage 1: Initial Crawl (Crawl4AI Server)

**Location:** External Crawl4AI service at `http://localhost:11235`

**What Happens:**
1. Fetches HTML from URL
2. Removes structural elements (`<nav>`, `<header>`, `<footer>`, `<aside>`, `<script>`, `<style>`)
3. Removes forms
4. Converts to markdown using `fit_markdown` (cleaned) or `raw_markdown`
5. Returns both `cleaned_html` and `markdown`

**Configuration in crawler.py (line 186):**
```python
response = requests.post(
    f"{self.crawl4ai_url}/crawl",
    json={
        "urls": [url],
        "word_count_threshold": 10,      # Minimum words per block
        "excluded_tags": ['nav', 'header', 'footer', 'aside', 'script', 'style', 'noscript'],
        "remove_forms": True,
        "only_text": True
    },
    timeout=30
)
```

**Output:**
```python
{
    "cleaned_html": "...",     # HTML with excluded tags removed
    "markdown": {
        "fit_markdown": "...",  # Cleaned markdown (preferred)
        "raw_markdown": "..."   # Raw markdown (fallback)
    },
    "metadata": {
        "title": "...",
        "status_code": 200
    }
}
```

---

## Stage 2: Content Cleaning (ContentCleaner)

**Location:** `core/data/content_cleaner.py`

**Called From:**
1. **crawler.py:213** (during crawl for LLM response)
2. **storage.py:280** (before storing to database)

### 2.1 In Crawler (crawler.py:212-214)

```python
# Clean the markdown content to remove navigation/boilerplate
cleaned_result = ContentCleaner.clean_and_validate(content, markdown, url)
cleaned_markdown = cleaned_result["cleaned_content"]
```

**Purpose:** Clean content for display to LLM (truncated to 5000 chars)

**Method:** `ContentCleaner.clean_and_validate(content, markdown, url)`

**Process:**
1. Calls `clean_content()` to remove navigation lines
2. Calculates quality metrics
3. Warns if mostly navigation (>70% reduction or >10 nav keywords)

**Input:** Raw markdown from Crawl4AI
**Output:**
```python
{
    "cleaned_content": "...",           # Cleaned markdown
    "original_lines": 450,
    "cleaned_lines": 280,
    "reduction_ratio": 0.38,            # (450-280)/450 = 38% removed
    "navigation_indicators": 5,         # Count of nav keywords
    "quality_warning": None,            # Or warning message
    "is_clean": True                    # False if mostly navigation
}
```

### 2.2 In Storage (storage.py:280-281)

```python
# Clean content FIRST before storing
cleaned_result = ContentCleaner.clean_and_validate(content, markdown, url)
cleaned_content = cleaned_result["cleaned_content"]
```

**Purpose:** Clean content before storage and embedding

**Same Process:** Uses `clean_and_validate()` again (ensures database has clean content)

**Important:** Both `content` and `markdown` fields in database are set to `cleaned_content`:
```python
# Line 336-340 in storage.py
cursor = self.execute_with_retry('''
    INSERT OR REPLACE INTO crawled_content
    (url, title, content, markdown, ...)
    VALUES (?, ?, ?, ?, ...)
''', (url, title, cleaned_content, cleaned_content, ...))
```

---

## Stage 3: Chunk Filtering (ContentCleaner)

**Location:** `core/data/content_cleaner.py::filter_chunks()`

**Called From:** `storage.py:401` (during embedding generation)

```python
def generate_embeddings(self, content_id: int, content: str):
    chunks = self.chunk_content(content)  # Split into 500-word chunks

    # Filter out navigation chunks before embedding
    filtered_chunks = ContentCleaner.filter_chunks(chunks)

    if len(filtered_chunks) == 0:
        # Use original chunks if filtering removes everything
        filtered_chunks = chunks[:3] if len(chunks) > 0 else chunks

    # Generate embeddings only for filtered chunks
    embeddings = self.embedder.encode(filtered_chunks)
```

**Purpose:** Remove low-quality chunks after splitting but before embedding

---

## ContentCleaner Class Details

### Method 1: `clean_content(markdown, url)`

**What It Removes:**

#### 1. Navigation Keywords (line 59-60)
```python
NAV_KEYWORDS = [
    'navigation', 'menu', 'sidebar', 'breadcrumb', 'skip to',
    'table of contents', 'on this page', 'quick links',
    'sign in', 'log in', 'subscribe', 'newsletter',
    'follow us', 'social media', 'share on', 'tweet',
    'copyright ©', 'all rights reserved', '© 20',
    'privacy policy', 'terms of service', 'cookie policy',
    'back to top', 'scroll to top', 'go to top'
]
```

**Example:**
```markdown
# Documentation

Table of contents:
- Introduction    ← REMOVED
- Getting Started ← REMOVED

Welcome to FastAPI...  ← KEPT
```

#### 2. Social Media Links (line 62-63)
```python
SOCIAL_DOMAINS = [
    'facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com',
    'youtube.com', 'github.com', 'discord.', 'reddit.com',
    'x.com', 'bsky.app', 'bluesky'
]
```

**Example:**
```markdown
Follow us on Twitter: https://twitter.com/...  ← REMOVED
Visit our GitHub: https://github.com/...      ← REMOVED

FastAPI is a modern framework...               ← KEPT
```

#### 3. Markdown Link Patterns (line 65-69)
```python
# Removes lines like:
# - [Link text](url)
# * [Documentation](https://...)
# - Learn [more](...)
```

**Example:**
```markdown
- [API Reference](https://docs.example.com/api)  ← REMOVED
* [Community](https://community.example.com)    ← REMOVED

The API provides the following endpoints...     ← KEPT
```

#### 4. Empty Lines (consolidated) (line 75)
```python
# Reduces multiple newlines to max 2
cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
```

**Processing Flow:**
```python
for line in markdown.split('\n'):
    line_lower = line.lower().strip()

    if not line_lower:
        continue  # Skip empty lines

    if any(keyword in line_lower for keyword in NAV_KEYWORDS):
        continue  # Skip navigation

    if any(domain in line_lower for domain in SOCIAL_DOMAINS):
        continue  # Skip social links

    if re.match(r'^[\s\*\-]+\[.*?\]\s*\(.*?\)\s*$', line):
        continue  # Skip markdown link lines

    cleaned_lines.append(line)  # Keep line
```

---

### Method 2: `filter_chunks(chunks)`

**What It Filters:**

#### 1. Navigation-Heavy Chunks (line 95-97)
```python
nav_count = sum(1 for keyword in NAV_KEYWORDS if keyword in chunk_lower)
if nav_count >= 3:
    continue  # Skip chunk with 3+ navigation keywords
```

**Example:**
```
Chunk: "Navigation menu: Home | About | Contact | Privacy Policy | Terms of Service"
       → nav_count = 5 (navigation, menu, privacy policy, terms of service, contact)
       → FILTERED OUT
```

#### 2. Link-Heavy Chunks (line 99-102)
```python
link_count = chunk.count('[') + chunk.count('](')
word_count = len(chunk.split())
if word_count > 0 and link_count / word_count > 0.3:
    continue  # Skip if >30% links
```

**Example:**
```
Chunk: "[Docs](url1) [API](url2) [Tutorial](url3) Some text here"
       → 6 link chars, ~7 words → 6/7 = 85% → FILTERED OUT
```

#### 3. Too Short (line 104-105)
```python
if word_count < 10:
    continue  # Skip chunks with <10 words
```

#### 4. Excessive Brackets (line 107-108)
```python
if chunk.count('[') > word_count / 3:
    continue  # Skip if brackets > 1/3 of words
```

**Fallback Safety (storage.py:407-409):**
```python
if len(filtered_chunks) == 0:
    # Use original chunks if filtering removes everything
    filtered_chunks = chunks[:3] if len(chunks) > 0 else chunks
```

---

### Method 3: `clean_and_validate(content, markdown, url)`

**Combines cleaning + quality metrics**

**Output:**
```python
{
    "cleaned_content": "...",
    "original_lines": 450,
    "cleaned_lines": 280,
    "reduction_ratio": 0.38,              # 38% removed
    "navigation_indicators": 5,           # Nav keyword count
    "quality_warning": "...",             # Warning if mostly nav
    "is_clean": True                      # False if >70% reduction
}
```

**Quality Check:**
```python
is_mostly_navigation = reduction_ratio > 0.7 or nav_count > 10

if is_mostly_navigation:
    warning = "Content appears to be mostly navigation/boilerplate"
```

---

### Method 4: `extract_main_content(markdown)`

**Purpose:** Remove headers and footers (not currently used in pipeline)

**Process:**
1. Find first heading or paragraph with 20+ words
2. Find last occurrence of copyright/footer text
3. Return content between these markers

---

## Complete Pipeline Flow

### Example Document Processing:

#### Input (from Crawl4AI):
```markdown
Navigation: Home | Docs | API | Community

Follow us on Twitter | LinkedIn | GitHub

# FastAPI Documentation

Table of contents:
- Introduction
- Quick Start
- Advanced Usage

FastAPI is a modern, fast web framework for building APIs with Python 3.7+.

It's based on Starlette for the web parts and Pydantic for the data parts.

Key features include automatic API documentation and type validation.

Back to top | Privacy Policy | Terms of Service

© 2024 FastAPI. All rights reserved.
```

#### After Stage 2 (clean_content):
```markdown
# FastAPI Documentation

FastAPI is a modern, fast web framework for building APIs with Python 3.7+.

It's based on Starlette for the web parts and Pydantic for the data parts.

Key features include automatic API documentation and type validation.
```

**Removed:**
- Navigation menu (line 1)
- Social links (line 3)
- Table of contents (lines 7-10)
- Footer links (line 17)
- Copyright (line 19)

#### After Chunking (500 words):
```python
Chunk 0: "# FastAPI Documentation\n\nFastAPI is a modern..."
Chunk 1: "It's based on Starlette for the web parts..."
Chunk 2: "Key features include automatic API..."
```

#### After Stage 3 (filter_chunks):
```python
All chunks pass filtering:
✓ Chunk 0: nav_count=0, word_count=12, link_ratio=0%
✓ Chunk 1: nav_count=0, word_count=15, link_ratio=0%
✓ Chunk 2: nav_count=0, word_count=8, link_ratio=0%  (but >= 10 words with context)
```

#### Final Embeddings:
- 3 chunks embedded
- All high-quality content
- Navigation/boilerplate removed

---

## Benefits of Multi-Stage Cleaning

1. **Stage 1 (Crawl4AI):** Removes structural HTML elements
2. **Stage 2 (clean_content):** Removes navigation text and keywords
3. **Stage 3 (filter_chunks):** Ensures each chunk is high-quality

**Result:**
- Higher quality embeddings
- Better search relevance
- Reduced storage for low-value content
- Improved RAG performance

---

## Configuration & Tuning

### Adjusting Navigation Keywords

**File:** `core/data/content_cleaner.py:19-27`

```python
# Add custom keywords:
NAV_KEYWORDS = [
    'navigation', 'menu', ...
    'your_custom_keyword',  # Add here
]
```

### Adjusting Filter Thresholds

**File:** `core/data/content_cleaner.py`

```python
# Line 96: Navigation keyword threshold
if nav_count >= 3:  # Change 3 to higher/lower

# Line 101: Link ratio threshold
if link_count / word_count > 0.3:  # Change 0.3 to higher/lower

# Line 104: Minimum word count
if word_count < 10:  # Change 10 to higher/lower
```

### Disabling Cleaning (NOT RECOMMENDED)

To skip cleaning (for debugging):

**In storage.py:**
```python
# Comment out cleaning:
# cleaned_result = ContentCleaner.clean_and_validate(content, markdown, url)
# cleaned_content = cleaned_result["cleaned_content"]

# Use raw content instead:
cleaned_content = markdown if markdown else content
```

---

## Logging & Monitoring

### Quality Warnings (storage.py:284-287)

```python
if cleaned_result.get("quality_warning"):
    print(f"⚠️  {cleaned_result['quality_warning']}: {url}")
    print(f"   Reduced from {cleaned_result['original_lines']} to "
          f"{cleaned_result['cleaned_lines']} lines")
```

**Example Output:**
```
⚠️  Content appears to be mostly navigation/boilerplate: https://example.com/nav
   Reduced from 450 to 80 lines
```

### Chunk Filtering Stats (storage.py:411-412)

```python
if len(filtered_chunks) < len(chunks):
    print(f"   Filtered {len(chunks)} chunks → {len(filtered_chunks)} quality chunks")
```

**Example Output:**
```
   Filtered 25 chunks → 18 quality chunks
```

---

## Impact on Knowledge Graph

### Chunk Boundaries (KG Integration)

**Important:** Chunk boundaries are calculated AFTER cleaning but BEFORE filtering:

```python
# storage.py:387-388
chunk_metadata = kg_queue.calculate_chunk_boundaries(content, filtered_chunks)
```

**This means:**
- Entity extraction uses filtered, high-quality chunks
- Character positions are accurate (relative to cleaned markdown)
- Navigation content excluded from KG processing
- Entities only extracted from meaningful content

### Benefits for KG:

1. **Cleaner Entities:** No "Home", "Menu", "Copyright" entities
2. **Better Relationships:** Only between real concepts
3. **Accurate Boundaries:** Positions relative to cleaned text
4. **Higher Confidence:** GLiNER and vLLM work on quality content

---

## Testing Cleaning Quality

### Manual Test:

```python
from core.data.content_cleaner import ContentCleaner

markdown = """
Navigation: Home | Docs

# My Article

This is the real content.

© 2024
"""

result = ContentCleaner.clean_and_validate("", markdown, "")

print(f"Original: {result['original_lines']} lines")
print(f"Cleaned: {result['cleaned_lines']} lines")
print(f"Reduction: {result['reduction_ratio']*100:.1f}%")
print(f"Nav indicators: {result['navigation_indicators']}")
print(f"\nCleaned content:\n{result['cleaned_content']}")
```

**Expected Output:**
```
Original: 7 lines
Cleaned: 3 lines
Reduction: 57.1%
Nav indicators: 2

Cleaned content:
# My Article

This is the real content.
```

---

## Summary

**3-Stage Cleaning Process:**

1. **Crawl4AI** → Removes HTML structure
2. **ContentCleaner.clean_content()** → Removes navigation text
3. **ContentCleaner.filter_chunks()** → Filters low-quality chunks

**Result:** High-quality embeddings from meaningful content only.

**For KG:** Entities and relationships extracted from cleaned, filtered content with accurate character boundaries.
