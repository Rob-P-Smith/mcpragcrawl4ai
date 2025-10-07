import pytest
import asyncio
from unittest.mock import patch, MagicMock
from operations.crawler import (
    validate_url, validate_string_length, validate_integer_range,
    validate_deep_crawl_params, validate_float_range, DeepCrawlManager,
    QueueManager, Crawl4AIRAG
)

# Test validate_url function
def test_validate_url_valid_http():
    assert validate_url("http://example.com") is True

def test_validate_url_valid_https():
    assert validate_url("https://example.com") is True

def test_validate_url_invalid_scheme():
    assert validate_url("ftp://example.com") is False

def test_validate_url_invalid_hostname():
    assert validate_url("http://") is False

def test_validate_url_localhost():
    assert validate_url("http://localhost") is False

def test_validate_url_127_0_0_1():
    assert validate_url("http://127.0.0.1") is False

def test_validate_url_loopback_ipv6():
    assert validate_url("http://[::1]") is False

def test_validate_url_private_ip():
    assert validate_url("http://192.168.1.1") is False

def test_validate_url_link_local():
    assert validate_url("http://169.254.169.254") is False

def test_validate_url_internal_domain():
    assert validate_url("http://example.internal") is False

def test_validate_url_corp_domain():
    assert validate_url("http://example.corp") is False

def test_validate_url_metadata_ip():
    assert validate_url("http://169.254.169.254") is False

def test_validate_url_invalid_url():
    assert validate_url("not-a-url") is False

# Test validate_string_length function
def test_validate_string_length_valid():
    result = validate_string_length("hello", 10, "test")
    assert result == "hello"

def test_validate_string_length_truncation():
    result = validate_string_length("hello world", 5, "test")
    assert result == "hello"
    # Note: This should print a warning to stderr

def test_validate_string_length_invalid_type():
    with pytest.raises(ValueError, match="test must be a string"):
        validate_string_length(123, 10, "test")

# Test validate_integer_range function
def test_validate_integer_range_valid():
    result = validate_integer_range(5, 1, 10, "test")
    assert result == 5

def test_validate_integer_range_invalid():
    with pytest.raises(ValueError, match="test must be between 1 and 10"):
        validate_integer_range(15, 1, 10, "test")

def test_validate_integer_range_string():
    result = validate_integer_range("5", 1, 10, "test")
    assert result == 5

def test_validate_integer_range_invalid_string():
    with pytest.raises(ValueError, match="test must be an integer"):
        validate_integer_range("not_a_number", 1, 10, "test")

# Test validate_deep_crawl_params function
def test_validate_deep_crawl_params_valid():
    result = validate_deep_crawl_params(2, 10)
    assert result == (2, 10)

def test_validate_deep_crawl_params_invalid_max_depth():
    with pytest.raises(ValueError, match="max_depth must be between 1 and 5"):
        validate_deep_crawl_params(6, 10)

def test_validate_deep_crawl_params_invalid_max_pages():
    with pytest.raises(ValueError, match="max_pages must be between 1 and 250"):
        validate_deep_crawl_params(2, 300)

# Test validate_float_range function
def test_validate_float_range_valid():
    result = validate_float_range(5.5, 1.0, 10.0, "test")
    assert result == 5.5

def test_validate_float_range_invalid():
    with pytest.raises(ValueError, match="test must be between 1.0 and 10.0"):
        validate_float_range(15.0, 1.0, 10.0, "test")

def test_validate_float_range_string():
    result = validate_float_range("5.5", 1.0, 10.0, "test")
    assert result == 5.5

def test_validate_float_range_invalid_string():
    with pytest.raises(ValueError, match="test must be a number"):
        validate_float_range("not_a_number", 1.0, 10.0, "test")

# Test DeepCrawlManager class
def test_deep_crawl_manager_init():
    manager = DeepCrawlManager()
    assert isinstance(manager.active_crawls, dict)
    assert isinstance(manager.crawl_queue, list)

def test_deep_crawl_manager_create_crawl_session():
    manager = DeepCrawlManager()
    session_id = manager.create_crawl_session("http://example.com")
    assert session_id is not None
    assert session_id in manager.active_crawls
    assert manager.active_crawls[session_id]["url"] == "http://example.com"
    assert manager.active_crawls[session_id]["max_depth"] == 2
    assert manager.active_crawls[session_id]["max_pages"] == 10

def test_deep_crawl_manager_get_crawl_status():
    manager = DeepCrawlManager()
    session_id = manager.create_crawl_session("http://example.com")
    status = manager.get_crawl_status(session_id)
    assert status["session_id"] == session_id
    assert status["url"] == "http://example.com"
    assert status["status"] == "running"
    assert status["pages_crawled"] == 0
    assert status["total_pages"] == 10

def test_deep_crawl_manager_get_crawl_status_not_found():
    manager = DeepCrawlManager()
    status = manager.get_crawl_status("nonexistent")
    assert status["error"] == "Crawl session not found"

def test_deep_crawl_manager_update_progress():
    manager = DeepCrawlManager()
    session_id = manager.create_crawl_session("http://example.com")
    manager.update_progress(session_id, 5)
    assert manager.active_crawls[session_id]["progress"]["pages_crawled"] == 5

def test_deep_crawl_manager_add_to_queue():
    manager = DeepCrawlManager()
    page_data = {"url": "http://example.com", "title": "Example"}
    manager.add_to_queue(page_data)
    assert len(manager.crawl_queue) == 1
    assert manager.crawl_queue[0] == page_data

def test_deep_crawl_manager_get_queue_status():
    manager = DeepCrawlManager()
    assert manager.get_queue_status() == {"queue_size": 0, "total_pages": 0}

def test_deep_crawl_manager_clear_crawl_session():
    manager = DeepCrawlManager()
    session_id = manager.create_crawl_session("http://example.com")
    manager.clear_crawl_session(session_id)
    assert session_id not in manager.active_crawls

# Test QueueManager class
def test_queue_manager_init():
    manager = QueueManager()
    assert isinstance(manager.ingestion_queue, list)

def test_queue_manager_add_to_queue():
    manager = QueueManager()
    page_data = {"url": "http://example.com", "title": "Example"}
    manager.add_to_queue(page_data)
    assert len(manager.ingestion_queue) == 1
    assert manager.ingestion_queue[0] == page_data

def test_queue_manager_get_batch():
    manager = QueueManager()
    page_data = {"url": "http://example.com", "title": "Example"}
    manager.add_to_queue(page_data)
    batch = manager.get_batch(1)
    assert len(batch) == 1
    assert batch[0] == page_data

def test_queue_manager_get_batch_larger_than_queue():
    manager = QueueManager()
    page_data = {"url": "http://example.com", "title": "Example"}
    manager.add_to_queue(page_data)
    batch = manager.get_batch(10)
    assert len(batch) == 1
    assert batch[0] == page_data

def test_queue_manager_remove_batch():
    manager = QueueManager()
    page_data = {"url": "http://example.com", "title": "Example"}
    manager.add_to_queue(page_data)
    manager.remove_batch([page_data])
    assert len(manager.ingestion_queue) == 0

def test_queue_manager_get_status():
    manager = QueueManager()
    assert manager.get_status() == {"queue_size": 0}

def test_queue_manager_clear_queue():
    manager = QueueManager()
    page_data = {"url": "http://example.com", "title": "Example"}
    manager.add_to_queue(page_data)
    manager.clear_queue()
    assert len(manager.ingestion_queue) == 0

# Test Crawl4AIRAG class
@pytest.mark.asyncio
async def test_crawl4airag_init():
    rag = Crawl4AIRAG()
    assert rag.crawl4ai_url == "http://localhost:11235"
    assert isinstance(rag.deep_crawl_manager, DeepCrawlManager)
    assert isinstance(rag.queue_manager, QueueManager)

def test_crawl4airag_crawl_url_success():
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "success": True,
            "results": [{
                "cleaned_html": "This is the content",
                "markdown": {"raw_markdown": "# Title\nContent"},
                "metadata": {"title": "Example Title"}
            }]
        }
        mock_post.return_value = mock_response

        rag = Crawl4AIRAG()
        result = rag.crawl_url("http://example.com")
        
        assert result["success"] is True
        assert result["url"] == "http://example.com"
        assert result["title"] == "Example Title"
        assert result["content_preview"] == "This is the content"
        assert result["content_length"] == 19  # Fixed to match actual content length
        assert "Crawled 'Example Title' - 19 characters" in result["message"]

def test_crawl4airag_crawl_url_failure():
    with patch('requests.post') as mock_post:
        mock_post.side_effect = Exception("Connection error")
        
        rag = Crawl4AIRAG()
        result = rag.crawl_url("http://example.com")
        
        assert result["success"] is False
        assert "Connection error" in result["error"]  # Fixed to match actual error message

def test_crawl4airag_crawl_and_store_success():
    with patch.object(Crawl4AIRAG, 'crawl_url') as mock_crawl_url:
        mock_crawl_url.return_value = {
            "success": True,
            "url": "http://example.com",
            "title": "Example Title",
            "content": "This is the content",
            "markdown": "# Title\nContent"
        }

        rag = Crawl4AIRAG()
        result = rag.crawl_and_store("http://example.com", "permanent", "test_tag")
        
        assert result["success"] is True
        assert result["url"] == "http://example.com"
        assert result["title"] == "Example Title"
        assert result["content_preview"] == "This is the content"
        assert result["content_length"] == 19  # Fixed to match actual content length
        assert result["stored"] is True
        assert result["retention_policy"] == "permanent"
        assert "Successfully crawled and stored 'Example Title' (19 characters)" in result["message"]

@pytest.mark.asyncio
async def test_crawl4airag_crawl_and_store_failure():
    with patch.object(Crawl4AIRAG, 'crawl_url') as mock_crawl_url:
        mock_crawl_url.return_value = {"success": False, "error": "Crawl failed"}
        
        rag = Crawl4AIRAG()
        result = await rag.crawl_and_store("http://example.com")
        
        assert result["success"] is False
        assert result["error"] == "Crawl failed"

def test_crawl4airag_deep_crawl_and_store():
    with patch.object(Crawl4AIRAG, '_call_mcp_deep_crawl_and_store') as mock_call:
        mock_call.return_value = {
            "success": True,
            "pages_crawled": 5,
            "pages_stored": 3,
            "pages_failed": 2,
            "stored_pages": ["http://example.com/page1", "http://example.com/page2", "http://example.com/page3"],
            "failed_pages": ["http://example.com/page4", "http://example.com/page5"]
        }

        rag = Crawl4AIRAG()
        result = rag.deep_crawl_and_store(
            "http://example.com", "permanent", "test_tag", 2, 10, False, 0.0
        )
        
        assert result["success"] is True
        assert result["starting_url"] == "http://example.com"
        assert result["pages_crawled"] == 5
        assert result["pages_stored"] == 3
        assert result["pages_failed"] == 2
        assert result["stored_pages"] == ["http://example.com/page1", "http://example.com/page2", "http://example.com/page3"]
        assert result["failed_pages"] == ["http://example.com/page4", "http://example.com/page5"]
        assert "Deep crawl completed: 3 pages stored, 2 failed" in result["message"]

def test_crawl4airag_deep_crawl_and_store_failure():
    with patch.object(Crawl4AIRAG, '_call_mcp_deep_crawl_and_store') as mock_call:
        mock_call.return_value = {"success": False, "error": "Deep crawl failed"}
        
        rag = Crawl4AIRAG()
        result = rag.deep_crawl_and_store("http://example.com")
        
        assert result["success"] is False
        assert result["error"] == "Deep crawl failed"

def test_crawl4airag_get_crawl_status():
    rag = Crawl4AIRAG()
    session_id = rag.deep_crawl_manager.create_crawl_session("http://example.com")
    status = rag.get_crawl_status(session_id)
    assert status["session_id"] == session_id
    assert status["url"] == "http://example.com"
    assert status["status"] == "running"
    assert status["pages_crawled"] == 0
    assert status["total_pages"] == 10

def test_crawl4airag_get_queue_status():
    rag = Crawl4AIRAG()
    status = rag.get_queue_status()
    assert status["queue_size"] == 0

def test_crawl4airag_process_ingestion_batch():
    rag = Crawl4AIRAG()
    page_data = {"url": "http://example.com", "title": "Example"}
    rag.queue_manager.add_to_queue(page_data)
    
    result = rag.process_ingestion_batch(1)
    
    assert result["success"] is True
    assert result["processed_count"] == 1
    assert result["remaining_in_queue"] == 0
    assert "Processed 1 pages from ingestion queue" in result["message"]
