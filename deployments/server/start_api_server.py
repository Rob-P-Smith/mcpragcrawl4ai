#!/usr/bin/env python3
"""
Startup script for Crawl4AI RAG API Server
Configurable to run in either server mode (hosting API) or client mode (forwarding to remote)
"""

import os
import sys
import uvicorn
from dotenv import load_dotenv

# Add /app to Python path for imports
sys.path.insert(0, '/app')

# Load environment variables
load_dotenv()

def main():
    """Start the API server based on configuration"""

    # Check if running in server mode
    is_server = os.getenv("IS_SERVER", "true").lower() == "true"

    if not is_server:
        print("❌ IS_SERVER=false: This script is for server mode only.")
        print("💡 For client mode, use: python3 core/rag_processor.py")
        print("   The MCP client will automatically forward requests to the remote API.")
        sys.exit(1)

    # Server configuration
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8080"))
    log_level = os.getenv("LOG_LEVEL", "info").lower()

    # Validate required configuration
    api_key = os.getenv("LOCAL_API_KEY")
    if not api_key:
        print("❌ LOCAL_API_KEY not set in .env file")
        print("💡 Generate a secure API key and add it to .env:")
        print("   LOCAL_API_KEY=your-secure-api-key-here")
        sys.exit(1)

    print("🚀 Starting Crawl4AI RAG API Server")
    print(f"🏠 Server Mode: hosting REST API on {host}:{port}")
    print(f"🔑 API Key: {api_key[:8]}...")
    print(f"📚 Database: {os.getenv('DB_PATH', 'crawl4ai_rag.db')}")
    print(f"🌐 Crawl4AI: {os.getenv('CRAWL4AI_URL', 'http://localhost:11235')}")
    print("")
    print("📖 API Documentation will be available at:")
    print(f"   http://{host}:{port}/docs")
    print("")

    # Import and create the app
    from api.api import create_app
    app = create_app()

    # Start the server
    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level=log_level,
            access_log=True
        )
    except KeyboardInterrupt:
        print("\n👋 Shutting down API server...")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()