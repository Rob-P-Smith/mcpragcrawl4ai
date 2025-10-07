import pytest
import asyncio
from unittest.mock import patch, MagicMock
from core.rag_processor import MCPServer, IS_CLIENT_MODE, GLOBAL_RAG

# Test MCPServer class
@pytest.fixture
def mock_rag():
    """Create a mock RAG instance"""
    with patch('core.rag_processor.Crawl4AIRAG') as mock_crawl_rag:
        mock_crawl_rag.return_value = MagicMock()
        yield mock_crawl_rag.return_value

@pytest.fixture
def mock_api_client():
    """Create a mock API client"""
    with patch('core.rag_processor.api_client') as mock_client:
        mock_client.crawl_url = MagicMock()
        mock_client.crawl_and_store = MagicMock()
        mock_client.crawl_temp = MagicMock()
        mock_client.search_knowledge = MagicMock()
        mock_client.list_memory = MagicMock()
        mock_client.forget_url = MagicMock()
        mock_client.clear_temp_memory = MagicMock()
        mock_client.deep_crawl_dfs = MagicMock()
        mock_client.deep_crawl_and_store = MagicMock()
        yield mock_client

@pytest.fixture
def mcps_server():
    """Create a MCPServer instance"""
    server = MCPServer()
    yield server

def test_mcp_server_init():
    server = MCPServer()
    assert server.rag is not None
    assert isinstance(server.tools, list)
    assert len(server.tools) == 10

def test_mcp_server_handle_request_initialize():
    server = MCPServer()
    request = {"method": "initialize", "id": 1}
    response = server.handle_request(request)
    
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert response["result"]["protocolVersion"] == "2025-06-18"
    assert response["result"]["serverInfo"]["name"] == "crawl4ai-rag"
    assert response["result"]["serverInfo"]["version"] == "1.0.0"

def test_mcp_server_handle_request_tools_list():
    server = MCPServer()
    request = {"method": "tools/list", "id": 1}
    response = server.handle_request(request)
    
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert response["result"]["tools"] == server.tools

def test_mcp_server_handle_request_tools_call_crawl_url_success():
    with patch('core.rag_processor.validate_url', return_value=True):
        with patch('core.rag_processor.Crawl4AIRAG') as mock_crawl_rag:
            mock_crawl_rag.return_value.crawl_url = MagicMock(return_value={
                "success": True,
                "url": "http://example.com",
                "title": "Example Title",
                "content_preview": "This is the content",
                "content_length": 20,
                "message": "Crawled 'Example Title' - 20 characters"
            })
            
            server = MCPServer()
            request = {
                "method": "tools/call",
                "id": 1,
                "params": {
                    "name": "crawl_url",
                    "arguments": {"url": "http://example.com"}
                }
            }
            response = server.handle_request(request)
            
            assert response["jsonrpc"] == "2.0"
            assert response["id"] == 1
            assert response["result"]["content"][0]["text"] == '{"success": true, "url": "http://example.com", "title": "Example Title", "content_preview": "This is the content", "content_length": 20, "message": "Crawled \'Example Title\' - 20 characters"}'

def test_mcp_server_handle_request_tools_call_crawl_url_invalid_url():
    with patch('core.rag_processor.validate_url', return_value=False):
        server = MCPServer()
        request = {
            "method": "tools/call",
            "id": 1,
            "params": {
                "name": "crawl_url",
                "arguments": {"url": "http://example.com"}
            }
        }
        response = server.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["result"]["content"][0]["text"] == '{"success": false, "error": "Invalid or unsafe URL provided"}'

def test_mcp_server_handle_request_tools_call_crawl_and_remember_success():
    with patch('core.rag_processor.validate_url', return_value=True):
        with patch('core.rag_processor.validate_string_length', return_value="test_tag"):
            with patch('core.rag_processor.Crawl4AIRAG') as mock_crawl_rag:
                mock_crawl_rag.return_value.crawl_and_store = MagicMock(return_value={
                    "success": True,
                    "url": "http://example.com",
                    "title": "Example Title",
                    "content_preview": "This is the content",
                    "content_length": 20,
                    "stored": True,
                    "retention_policy": "permanent",
                    "message": "Successfully crawled and stored 'Example Title' (20 characters)"
                })
                
                server = MCPServer()
                request = {
                    "method": "tools/call",
                    "id": 1,
                    "params": {
                        "name": "crawl_and_remember",
                        "arguments": {"url": "http://example.com", "tags": "test_tag"}
                    }
                }
                response = server.handle_request(request)
                
                assert response["jsonrpc"] == "2.0"
                assert response["id"] == 1
                assert response["result"]["content"][0]["text"] == '{"success": true, "url": "http://example.com", "title": "Example Title", "content_preview": "This is the content", "content_length": 20, "stored": true, "retention_policy": "permanent", "message": "Successfully crawled and stored \'Example Title\' (20 characters)"}'

def test_mcp_server_handle_request_tools_call_crawl_and_remember_invalid_url():
    with patch('core.rag_processor.validate_url', return_value=False):
        server = MCPServer()
        request = {
            "method": "tools/call",
            "id": 1,
            "params": {
                "name": "crawl_and_remember",
                "arguments": {"url": "http://example.com", "tags": "test_tag"}
            }
        }
        response = server.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["result"]["content"][0]["text"] == '{"success": false, "error": "Invalid or unsafe URL provided"}'

def test_mcp_server_handle_request_tools_call_crawl_temp_success():
    with patch('core.rag_processor.validate_url', return_value=True):
        with patch('core.rag_processor.validate_string_length', return_value="test_tag"):
            with patch('core.rag_processor.Crawl4AIRAG') as mock_crawl_rag:
                mock_crawl_rag.return_value.crawl_and_store = MagicMock(return_value={
                    "success": True,
                    "url": "http://example.com",
                    "title": "Example Title",
                    "content_preview": "This is the content",
                    "content_length": 20,
                    "stored": True,
                    "retention_policy": "session_only",
                    "message": "Successfully crawled and stored 'Example Title' (20 characters)"
                })
                
                server = MCPServer()
                request = {
                    "method": "tools/call",
                    "id": 1,
                    "params": {
                        "name": "crawl_temp",
                        "arguments": {"url": "http://example.com", "tags": "test_tag"}
                    }
                }
                response = server.handle_request(request)
                
                assert response["jsonrpc"] == "2.0"
                assert response["id"] == 1
                assert response["result"]["content"][0]["text"] == '{"success": true, "url": "http://example.com", "title": "Example Title", "content_preview": "This is the content", "content_length": 20, "stored": true, "retention_policy": "session_only", "message": "Successfully crawled and stored \'Example Title\' (20 characters)"}'

def test_mcp_server_handle_request_tools_call_crawl_temp_invalid_url():
    with patch('core.rag_processor.validate_url', return_value=False):
        server = MCPServer()
        request = {
            "method": "tools/call",
            "id": 1,
            "params": {
                "name": "crawl_temp",
                "arguments": {"url": "http://example.com", "tags": "test_tag"}
            }
        }
        response = server.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["result"]["content"][0]["text"] == '{"success": false, "error": "Invalid or unsafe URL provided"}'

def test_mcp_server_handle_request_tools_call_search_memory_success():
    with patch('core.rag_processor.validate_string_length', return_value="test query"):
        with patch('core.rag_processor.validate_integer_range', return_value=5):
            with patch('core.rag_processor.Crawl4AIRAG') as mock_crawl_rag:
                mock_crawl_rag.return_value.search_knowledge = MagicMock(return_value=[
                    {
                        'url': 'http://example.com',
                        'title': 'Example Title',
                        'content': 'This is the content',
                        'timestamp': '2023-01-01T00:00:00',
                        'tags': 'test_tag',
                        'similarity_score': 0.85
                    }
                ])
                
                server = MCPServer()
                request = {
                    "method": "tools/call",
                    "id": 1,
                    "params": {
                        "name": "search_memory",
                        "arguments": {"query": "test query", "limit": 5}
                    }
                }
                response = server.handle_request(request)
                
                assert response["jsonrpc"] == "2.0"
                assert response["id"] == 1
                assert response["result"]["content"][0]["text"] == '[{"url": "http://example.com", "title": "Example Title", "content": "This is the content", "timestamp": "2023-01-01T00:00:00", "tags": "test_tag", "similarity_score": 0.85}]'

def test_mcp_server_handle_request_tools_call_search_memory_invalid_query():
    with patch('core.rag_processor.validate_string_length', return_value=""):
        server = MCPServer()
        request = {
            "method": "tools/call",
            "id": 1,
            "params": {
                "name": "search_memory",
                "arguments": {"query": "", "limit": 5}
            }
        }
        response = server.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["result"]["content"][0]["text"] == '{"success": false, "error": "query must be a string"}'

def test_mcp_server_handle_request_tools_call_list_memory_success():
    with patch('core.rag_processor.validate_string_length', return_value="permanent"):
        with patch('core.rag_processor.Crawl4AIRAG') as mock_crawl_rag:
            mock_crawl_rag.return_value.search_knowledge = MagicMock(return_value=[
                {
                    'url': 'http://example.com',
                    'title': 'Example Title',
                    'content': 'This is the content',
                    'timestamp': '2023-01-01T00:00:00',
                    'tags': 'test_tag',
                    'similarity_score': 0.85
                }
            ])
            
            server = MCPServer()
            request = {
                "method": "tools/call",
                "id": 1,
                "params": {
                    "name": "list_memory",
                    "arguments": {"filter": "permanent"}
                }
            }
            response = server.handle_request(request)
            
            assert response["jsonrpc"] == "2.0"
            assert response["id"] == 1
            assert response["result"]["content"][0]["text"] == '{"success": true, "content": [{"url": "http://example.com", "title": "Example Title", "timestamp": "2023-01-01T00:00:00", "retention_policy": "permanent", "tags": "test_tag"}]}'

def test_mcp_server_handle_request_tools_call_list_memory_invalid_filter():
    with patch('core.rag_processor.validate_string_length', return_value="invalid_filter"):
        server = MCPServer()
        request = {
            "method": "tools/call",
            "id": 1,
            "params": {
                "name": "list_memory",
                "arguments": {"filter": "invalid_filter"}
            }
        }
        response = server.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["result"]["content"][0]["text"] == '{"success": false, "error": "filter must be a string"}'

def test_mcp_server_handle_request_tools_call_forget_url_success():
    with patch('core.rag_processor.validate_url', return_value=True):
        with patch('core.rag_processor.RAGDatabase') as mock_rag_db:
            mock_rag_db.return_value.remove_content = MagicMock(return_value=1)
            
            server = MCPServer()
            request = {
                "method": "tools/call",
                "id": 1,
                "params": {
                    "name": "forget_url",
                    "arguments": {"url": "http://example.com"}
                }
            }
            response = server.handle_request(request)
            
            assert response["jsonrpc"] == "2.0"
            assert response["id"] == 1
            assert response["result"]["content"][0]["text"] == '{"success": true, "removed_count": 1, "url": "http://example.com"}'

def test_mcp_server_handle_request_tools_call_forget_url_invalid_url():
    with patch('core.rag_processor.validate_url', return_value=False):
        server = MCPServer()
        request = {
            "method": "tools/call",
            "id": 1,
            "params": {
                "name": "forget_url",
                "arguments": {"url": "http://example.com"}
            }
        }
        response = server.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["result"]["content"][0]["text"] == '{"success": false, "error": "Invalid or unsafe URL provided"}'

def test_mcp_server_handle_request_tools_call_clear_temp_memory_success():
    with patch('core.rag_processor.RAGDatabase') as mock_rag_db:
        mock_rag_db.return_value.remove_content = MagicMock(return_value=1)
        
        server = MCPServer()
        request = {
            "method": "tools/call",
            "id": 1,
            "params": {
                "name": "clear_temp_memory",
                "arguments": {}
            }
        }
        response = server.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["result"]["content"][0]["text"] == '{"success": true, "removed_count": 1, "session_id": "some_session_id"}'

def test_mcp_server_handle_request_tools_call_deep_crawl_dfs_success():
    with patch('core.rag_processor.validate_url', return_value=True):
        with patch('core.rag_processor.validate_deep_crawl_params', return_value=(2, 10)):
            with patch('core.rag_processor.validate_float_range', return_value=0.0):
                with patch('core.rag_processor.Crawl4AIRAG') as mock_crawl_rag:
                    mock_crawl_rag.return_value.deep_crawl_dfs = MagicMock(return_value={
                        "success": True,
                        "pages_crawled": 5,
                        "pages_stored": 3,
                        "pages_failed": 2,
                        "stored_pages": ["http://example.com/page1", "http://example.com/page2", "http://example.com/page3"],
                        "failed_pages": ["http://example.com/page4", "http://example.com/page5"]
                    })
                    
                    server = MCPServer()
                    request = {
                        "method": "tools/call",
                        "id": 1,
                        "params": {
                            "name": "deep_crawl_dfs",
                            "arguments": {
                                "url": "http://example.com",
                                "max_depth": 2,
                                "max_pages": 10,
                                "include_external": False,
                                "score_threshold": 0.0
                            }
                        }
                    }
                    response = server.handle_request(request)
                    
                    assert response["jsonrpc"] == "2.0"
                    assert response["id"] == 1
                    assert response["result"]["content"][0]["text"] == '{"success": true, "pages_crawled": 5, "pages_stored": 3, "pages_failed": 2, "stored_pages": ["http://example.com/page1", "http://example.com/page2", "http://example.com/page3"], "failed_pages": ["http://example.com/page4", "http://example.com/page5"]}'

def test_mcp_server_handle_request_tools_call_deep_crawl_dfs_invalid_url():
    with patch('core.rag_processor.validate_url', return_value=False):
        server = MCPServer()
        request = {
            "method": "tools/call",
            "id": 1,
            "params": {
                "name": "deep_crawl_dfs",
                "arguments": {
                    "url": "http://example.com",
                    "max_depth": 2,
                    "max_pages": 10,
                    "include_external": False,
                    "score_threshold": 0.0
                }
            }
        }
        response = server.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["result"]["content"][0]["text"] == '{"success": false, "error": "Invalid or unsafe URL provided"}'

def test_mcp_server_handle_request_tools_call_deep_crawl_and_store_success():
    with patch('core.rag_processor.validate_url', return_value=True):
        with patch('core.rag_processor.validate_deep_crawl_params', return_value=(2, 10)):
            with patch('core.rag_processor.validate_string_length', return_value="test_tag"):
                with patch('core.rag_processor.validate_float_range', return_value=0.0):
                    with patch('core.rag_processor.Crawl4AIRAG') as mock_crawl_rag:
                        mock_crawl_rag.return_value.deep_crawl_and_store = MagicMock(return_value={
                            "success": True,
                            "starting_url": "http://example.com",
                            "pages_crawled": 5,
                            "pages_stored": 3,
                            "pages_failed": 2,
                            "stored_pages": ["http://example.com/page1", "http://example.com/page2", "http://example.com/page3"],
                            "failed_pages": ["http://example.com/page4", "http://example.com/page5"],
                            "retention_policy": "permanent",
                            "message": "Deep crawl completed: 3 pages stored, 2 failed"
                        })
                        
                        server = MCPServer()
                        request = {
                            "method": "tools/call",
                            "id": 1,
                            "params": {
                                "name": "deep_crawl_and_store",
                                "arguments": {
                                    "url": "http://example.com",
                                    "max_depth": 2,
                                    "max_pages": 10,
                                    "retention_policy": "permanent",
                                    "tags": "test_tag",
                                    "include_external": False,
                                    "score_threshold": 0.0
                                }
                            }
                        }
                        response = server.handle_request(request)
                        
                        assert response["jsonrpc"] == "2.0"
                        assert response["id"] == 1
                        assert response["result"]["content"][0]["text"] == '{"success": true, "starting_url": "http://example.com", "pages_crawled": 5, "pages_stored": 3, "pages_failed": 2, "stored_pages": ["http://example.com/page1", "http://example.com/page2", "http://example.com/page3"], "failed_pages": ["http://example.com/page4", "http://example.com/page5"], "retention_policy": "permanent", "message": "Deep crawl completed: 3 pages stored, 2 failed"}'

def test_mcp_server_handle_request_tools_call_deep_crawl_and_store_invalid_url():
    with patch('core.rag_processor.validate_url', return_value=False):
        server = MCPServer()
        request = {
            "method": "tools/call",
            "id": 1,
            "params": {
                "name": "deep_crawl_and_store",
                "arguments": {
                    "url": "http://example.com",
                    "max_depth": 2,
                    "max_pages": 10,
                    "retention_policy": "permanent",
                    "tags": "test_tag",
                    "include_external": False,
                    "score_threshold": 0.0
                }
            }
        }
        response = server.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["result"]["content"][0]["text"] == '{"success": false, "error": "Invalid or unsafe URL provided"}'

def test_mcp_server_handle_request_tools_call_unknown_tool():
    server = MCPServer()
    request = {
        "method": "tools/call",
        "id": 1,
        "params": {
            "name": "unknown_tool",
            "arguments": {}
        }
    }
    response = server.handle_request(request)
    
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert response["result"]["content"][0]["text"] == '{"success": false, "error": "Unknown tool: unknown_tool"}'

def test_mcp_server_handle_request_tools_call_validation_error():
    with patch('core.rag_processor.validate_url', return_value=True):
        with patch('core.rag_processor.Crawl4AIRAG') as mock_crawl_rag:
            mock_crawl_rag.return_value.crawl_url = MagicMock(side_effect=ValueError("Invalid URL"))
            
            server = MCPServer()
            request = {
                "method": "tools/call",
                "id": 1,
                "params": {
                    "name": "crawl_url",
                    "arguments": {"url": "http://example.com"}
                }
            }
            response = server.handle_request(request)
            
            assert response["jsonrpc"] == "2.0"
            assert response["id"] == 1
            assert response["result"]["content"][0]["text"] == '{"success": false, "error": "Invalid URL"}'

def test_mcp_server_handle_request_tools_call_internal_error():
    with patch('core.rag_processor.validate_url', return_value=True):
        with patch('core.rag_processor.Crawl4AIRAG') as mock_crawl_rag:
            mock_crawl_rag.return_value.crawl_url = MagicMock(side_effect=Exception("Internal error"))
            
            server = MCPServer()
            request = {
                "method": "tools/call",
                "id": 1,
                "params": {
                    "name": "crawl_url",
                    "arguments": {"url": "http://example.com"}
                }
            }
            response = server.handle_request(request)
            
            assert response["jsonrpc"] == "2.0"
            assert response["id"] == 1
            assert response["error"]["message"] == "Internal error: Internal error"

def test_mcp_server_handle_request_method_not_found():
    server = MCPServer()
    request = {"method": "unknown_method", "id": 1}
    response = server.handle_request(request)
    
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert response["error"]["code"] == -32601
    assert response["error"]["message"] == "Method not found"

# Test helper functions
def test_validate_url():
    # Test the validate_url function from rag_processor.py
    from core.rag_processor import validate_url
    
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
    # Test the validate_string_length function from rag_processor.py
    from core.rag_processor import validate_string_length
    
    assert validate_string_length("hello", 10, "test") == "hello"
    assert validate_string_length("hello world", 5, "test") == "hello"
    with pytest.raises(ValueError, match="test must be a string"):
        validate_string_length(123, 10, "test")

def test_validate_integer_range():
    # Test the validate_integer_range function from rag_processor.py
    from core.rag_processor import validate_integer_range
    
    assert validate_integer_range(5, 1, 10, "test") == 5
    with pytest.raises(ValueError, match="test must be between 1 and 10"):
        validate_integer_range(15, 1, 10, "test")
    assert validate_integer_range("5", 1, 10, "test") == 5
    with pytest.raises(ValueError, match="test must be an integer"):
        validate_integer_range("not_a_number", 1, 10, "test")

def test_validate_deep_crawl_params():
    # Test the validate_deep_crawl_params function from rag_processor.py
    from core.rag_processor import validate_deep_crawl_params
    
    assert validate_deep_crawl_params(2, 10) == (2, 10)
    with pytest.raises(ValueError, match="max_depth must be between 1 and 5"):
        validate_deep_crawl_params(6, 10)
    with pytest.raises(ValueError, match="max_pages must be between 1 and 250"):
        validate_deep_crawl_params(2, 300)

def test_validate_float_range():
    # Test the validate_float_range function from rag_processor.py
    from core.rag_processor import validate_float_range
    
    assert validate_float_range(5.5, 1.0, 10.0, "test") == 5.5
    with pytest.raises(ValueError, match="test must be between 1.0 and 10.0"):
        validate_float_range(15.0, 1.0, 10.0, "test")
    assert validate_float_range("5.5", 1.0, 10.0, "test") == 5.5
    with pytest.raises(ValueError, match="test must be a number"):
        validate_float_range("not_a_number", 1.0, 10.0, "test")
