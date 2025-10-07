import pytest
import sqlite3
import tempfile
import os
from unittest.mock import patch, MagicMock
from data.storage import RAGDatabase, GLOBAL_DB, log_error

# Test RAGDatabase class
@pytest.fixture
def temp_db():
    """Create a temporary database file for testing"""
    db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    db_file.close()
    yield db_file.name
    os.unlink(db_file.name)

@pytest.fixture
def rag_db(temp_db):
    """Create a RAGDatabase instance with a temporary database"""
    db = RAGDatabase(db_path=temp_db)
    yield db
    db.close()

def test_rag_database_init(temp_db):
    db = RAGDatabase(db_path=temp_db)
    assert db.db_path == temp_db
    assert db.session_id is not None
    assert db.embedder is not None
    assert db._connection_closed is False
    db.close()

def test_rag_database_init_with_default_path():
    db = RAGDatabase()
    assert db.db_path == "crawl4ai_rag.db"
    db.close()

def test_rag_database_init_with_app_data_path():
    with patch('os.path.exists', return_value=True):
        with patch('os.path.dirname', return_value='/app/data'):
            db = RAGDatabase()
            assert db.db_path == "/app/data/crawl4ai_rag.db"
            db.close()

def test_rag_database_get_db_connection(rag_db):
    with rag_db.get_db_connection() as conn:
        assert conn is not None
        assert conn.execute("SELECT 1").fetchone()[0] == 1

def test_rag_database_transaction(rag_db):
    with rag_db.transaction():
        rag_db.db.execute("INSERT INTO sessions (session_id, last_active) VALUES (?, CURRENT_TIMESTAMP)", (rag_db.session_id,))
        rag_db.db.commit()
    
    # Verify the session was inserted
    with rag_db.get_db_connection() as conn:
        result = conn.execute("SELECT session_id FROM sessions WHERE session_id = ?", (rag_db.session_id,)).fetchone()
        assert result is not None
        assert result[0] == rag_db.session_id

def test_rag_database_execute_with_retry_success(rag_db):
    # Test successful execution
    result = rag_db.execute_with_retry("SELECT 1")
    assert result.fetchone()[0] == 1

def test_rag_database_execute_with_retry_failure_with_retry(rag_db):
    # Simulate a failure that will be retried
    with patch.object(rag_db.db, 'execute', side_effect=[sqlite3.OperationalError("test"), None]):
        result = rag_db.execute_with_retry("SELECT 1")
        assert result.fetchone()[0] == 1

def test_rag_database_execute_with_retry_failure_without_retry(rag_db):
    # Simulate a failure that won't be retried
    with patch.object(rag_db.db, 'execute', side_effect=sqlite3.OperationalError("test")):
        with pytest.raises(sqlite3.OperationalError):
            rag_db.execute_with_retry("SELECT 1", max_retries=1)

def test_rag_database_load_sqlite_vec(rag_db):
    # Test that the extension is loaded
    with rag_db.get_db_connection() as conn:
        # Check if the extension is loaded
        result = conn.execute("SELECT name FROM sqlite_master WHERE type='module' AND name='vec0'").fetchone()
        assert result is not None

def test_rag_database_init_database(rag_db):
    # Verify tables were created
    with rag_db.get_db_connection() as conn:
        # Check if tables exist
        result = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='crawled_content'").fetchone()
        assert result is not None
        
        result = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'").fetchone()
        assert result is not None
        
        result = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='content_vectors'").fetchone()
        assert result is not None

def test_rag_database_chunk_content():
    db = RAGDatabase()
    content = "This is a test content with multiple words to test chunking functionality"
    chunks = db.chunk_content(content, chunk_size=10, overlap=2)
    
    assert len(chunks) == 3
    assert chunks[0] == "This is a test content with"
    assert chunks[1] == "content with multiple words to"
    assert chunks[2] == "words to test chunking functionality"

def test_rag_database_chunk_content_with_overlap():
    db = RAGDatabase()
    content = "This is a test content with multiple words to test chunking functionality"
    chunks = db.chunk_content(content, chunk_size=15, overlap=5)
    
    assert len(chunks) == 3
    assert chunks[0] == "This is a test content with multiple"
    assert chunks[1] == "multiple words to test chunking"
    assert chunks[2] == "chunking functionality"

def test_rag_database_store_content_new_content(rag_db):
    url = "http://example.com"
    title = "Example Title"
    content = "This is the content"
    markdown = "# Title\nContent"
    
    content_id = rag_db.store_content(url, title, content, markdown, "permanent", "test_tag")
    
    assert content_id > 0
    
    # Verify the content was stored
    with rag_db.get_db_connection() as conn:
        result = conn.execute("SELECT url, title, content, markdown, content_hash, retention_policy, tags FROM crawled_content WHERE id = ?", (content_id,)).fetchone()
        assert result is not None
        assert result[0] == url
        assert result[1] == title
        assert result[2] == content
        assert result[3] == markdown
        assert result[4] is not None
        assert result[5] == "permanent"
        assert result[6] == "test_tag"

def test_rag_database_store_content_existing_content(rag_db):
    # First store content
    url = "http://example.com"
    title = "Example Title"
    content = "This is the content"
    markdown = "# Title\nContent"
    
    content_id = rag_db.store_content(url, title, content, markdown, "permanent", "test_tag")
    assert content_id > 0
    
    # Store the same content again (should replace)
    new_content = "This is new content"
    new_content_id = rag_db.store_content(url, title, new_content, markdown, "permanent", "test_tag")
    
    assert new_content_id == content_id  # Should be the same ID
    
    # Verify the content was replaced
    with rag_db.get_db_connection() as conn:
        result = conn.execute("SELECT content FROM crawled_content WHERE id = ?", (new_content_id,)).fetchone()
        assert result is not None
        assert result[0] == new_content

def test_rag_database_store_content_with_session_only(rag_db):
    url = "http://example.com"
    title = "Example Title"
    content = "This is the content"
    markdown = "# Title\nContent"
    
    content_id = rag_db.store_content(url, title, content, markdown, "session_only", "test_tag")
    
    assert content_id > 0
    
    # Verify the content was stored with session_only policy
    with rag_db.get_db_connection() as conn:
        result = conn.execute("SELECT retention_policy FROM crawled_content WHERE id = ?", (content_id,)).fetchone()
        assert result is not None
        assert result[0] == "session_only"

def test_rag_database_store_content_with_invalid_url(rag_db):
    url = "not-a-url"
    title = "Example Title"
    content = "This is the content"
    markdown = "# Title\nContent"
    
    with pytest.raises(ValueError, match="Invalid or unsafe URL provided"):
        rag_db.store_content(url, title, content, markdown, "permanent", "test_tag")

def test_rag_database_generate_embeddings(rag_db):
    # First store content
    url = "http://example.com"
    title = "Example Title"
    content = "This is the content"
    markdown = "# Title\nContent"
    
    content_id = rag_db.store_content(url, title, content, markdown, "permanent", "test_tag")
    
    # Verify embeddings were generated
    with rag_db.get_db_connection() as conn:
        result = conn.execute("SELECT COUNT(*) FROM content_vectors WHERE content_id = ?", (content_id,)).fetchone()
        assert result is not None
        assert result[0] > 0

def test_rag_database_search_similar_success(rag_db):
    # Store some content first
    url = "http://example.com"
    title = "Example Title"
    content = "This is the content"
    markdown = "# Title\nContent"
    
    content_id = rag_db.store_content(url, title, content, markdown, "permanent", "test_tag")
    
    # Search for similar content
    results = rag_db.search_similar("test content", limit=5)
    
    assert len(results) == 1
    assert results[0]["url"] == url
    assert results[0]["title"] == title
    assert results[0]["content"] == "This is the content"
    assert results[0]["similarity_score"] > 0.0

def test_rag_database_search_similar_no_results(rag_db):
    # Search for content that doesn't exist
    results = rag_db.search_similar("nonexistent query", limit=5)
    
    assert len(results) == 0

def test_rag_database_search_similar_with_limit(rag_db):
    # Store multiple content items
    for i in range(3):
        url = f"http://example.com/{i}"
        title = f"Example Title {i}"
        content = f"This is content {i}"
        markdown = f"# Title {i}\nContent {i}"
        
        rag_db.store_content(url, title, content, markdown, "permanent", "test_tag")
    
    # Search for similar content
    results = rag_db.search_similar("test content", limit=2)
    
    assert len(results) == 2

def test_rag_database_list_content_all(rag_db):
    # Store some content
    for i in range(3):
        url = f"http://example.com/{i}"
        title = f"Example Title {i}"
        content = f"This is content {i}"
        markdown = f"# Title {i}\nContent {i}"
        
        rag_db.store_content(url, title, content, markdown, "permanent", "test_tag")
    
    # List all content
    results = rag_db.list_content()
    
    assert len(results) == 3
    assert results[0]["url"] == "http://example.com/2"
    assert results[0]["title"] == "Example Title 2"
    assert results[0]["retention_policy"] == "permanent"
    assert results[0]["tags"] == "test_tag"

def test_rag_database_list_content_with_filter(rag_db):
    # Store content with different retention policies
    rag_db.store_content("http://example.com/1", "Title 1", "Content 1", "# Title 1\nContent 1", "permanent", "test_tag")
    rag_db.store_content("http://example.com/2", "Title 2", "Content 2", "# Title 2\nContent 2", "session_only", "test_tag")
    
    # List content with filter
    results = rag_db.list_content("permanent")
    
    assert len(results) == 1
    assert results[0]["url"] == "http://example.com/1"
    assert results[0]["retention_policy"] == "permanent"

def test_rag_database_remove_content_by_url(rag_db):
    # Store content
    url = "http://example.com"
    title = "Example Title"
    content = "This is the content"
    markdown = "# Title\nContent"
    
    content_id = rag_db.store_content(url, title, content, markdown, "permanent", "test_tag")
    
    # Remove content by URL
    removed_count = rag_db.remove_content(url=url)
    
    assert removed_count == 1
    
    # Verify content was removed
    with rag_db.get_db_connection() as conn:
        result = conn.execute("SELECT COUNT(*) FROM crawled_content WHERE url = ?", (url,)).fetchone()
        assert result is not None
        assert result[0] == 0

def test_rag_database_remove_content_session_only(rag_db):
    # Store content with session_only policy
    url = "http://example.com"
    title = "Example Title"
    content = "This is the content"
    markdown = "# Title\nContent"
    
    content_id = rag_db.store_content(url, title, content, markdown, "session_only", "test_tag")
    
    # Remove content with session_only flag
    removed_count = rag_db.remove_content(session_only=True)
    
    assert removed_count == 1
    
    # Verify content was removed
    with rag_db.get_db_connection() as conn:
        result = conn.execute("SELECT COUNT(*) FROM crawled_content WHERE url = ?", (url,)).fetchone()
        assert result is not None
        assert result[0] == 0

def test_rag_database_remove_content_no_filter(rag_db):
    # Store content
    url = "http://example.com"
    title = "Example Title"
    content = "This is the content"
    markdown = "# Title\nContent"
    
    content_id = rag_db.store_content(url, title, content, markdown, "permanent", "test_tag")
    
    # Remove content with no filter (should return 0)
    removed_count = rag_db.remove_content()
    
    assert removed_count == 0

def test_rag_database_remove_content_nonexistent_url(rag_db):
    # Remove content that doesn't exist
    removed_count = rag_db.remove_content(url="http://nonexistent.com")
    
    assert removed_count == 0

def test_rag_database_log_error(rag_db):
    # Test that log_error is called
    with patch('data.storage.log_error') as mock_log_error:
        log_error("test_function", Exception("Test error"), "http://example.com", "TEST_CODE")
        
        mock_log_error.assert_called_once_with("test_function", Exception("Test error"), "http://example.com", "TEST_CODE")

# Test helper functions
def test_validate_url():
    # Test the validate_url function from storage.py
    from data.storage import validate_url
    
    assert validate_url("http://example.com") is True
    assert validate_url("https://example.com") is True
    assert validate_url("ftp://example.com") is False
    assert validate_url("http://localhost") is False
    assert validate_url("http://127.0.0.1") is False
    assert validate_url("http://192.168.1.1") is False
    assert validate_url("http://169.254.169.254") is False
    assert validate_url("http://example.internal") is False
    assert validate_url("http://example.corp") is False
    assert validate_url("not-a-url") is False

def test_validate_string_length():
    # Test the validate_string_length function from storage.py
    from data.storage import validate_string_length
    
    assert validate_string_length("hello", 10, "test") == "hello"
    assert validate_string_length("hello world", 5, "test") == "hello"
    with pytest.raises(ValueError, match="test must be a string"):
        validate_string_length(123, 10, "test")

def test_validate_integer_range():
    # Test the validate_integer_range function from storage.py
    from data.storage import validate_integer_range
    
    assert validate_integer_range(5, 1, 10, "test") == 5
    with pytest.raises(ValueError, match="test must be between 1 and 10"):
        validate_integer_range(15, 1, 10, "test")
    assert validate_integer_range("5", 1, 10, "test") == 5
    with pytest.raises(ValueError, match="test must be an integer"):
        validate_integer_range("not_a_number", 1, 10, "test")

def test_validate_deep_crawl_params():
    # Test the validate_deep_crawl_params function from storage.py
    from data.storage import validate_deep_crawl_params
    
    assert validate_deep_crawl_params(2, 10) == (2, 10)
    with pytest.raises(ValueError, match="max_depth must be between 1 and 5"):
        validate_deep_crawl_params(6, 10)
    with pytest.raises(ValueError, match="max_pages must be between 1 and 250"):
        validate_deep_crawl_params(2, 300)

def test_validate_float_range():
    # Test the validate_float_range function from storage.py
    from data.storage import validate_float_range
    
    assert validate_float_range(5.5, 1.0, 10.0, "test") == 5.5
    with pytest.raises(ValueError, match="test must be between 1.0 and 10.0"):
        validate_float_range(15.0, 1.0, 10.0, "test")
    assert validate_float_range("5.5", 1.0, 10.0, "test") == 5.5
    with pytest.raises(ValueError, match="test must be a number"):
        validate_float_range("not_a_number", 1.0, 10.0, "test")
