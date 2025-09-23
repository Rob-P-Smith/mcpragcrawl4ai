"""
Authentication middleware for Crawl4AI RAG REST API
Handles API key validation, rate limiting, and session management
"""

import os
import time
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

security = HTTPBearer()

class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(list)
        self.max_requests = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

    def is_allowed(self, api_key: str) -> bool:
        now = time.time()
        minute_ago = now - 60

        # Clean old requests
        self.requests[api_key] = [req_time for req_time in self.requests[api_key] if req_time > minute_ago]

        # Check if under limit
        if len(self.requests[api_key]) >= self.max_requests:
            return False

        # Add current request
        self.requests[api_key].append(now)
        return True

class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.session_timeout = timedelta(hours=24)

    def create_session(self, api_key: str) -> str:
        session_id = hashlib.sha256(f"{api_key}{time.time()}".encode()).hexdigest()[:16]
        self.sessions[session_id] = {
            "api_key": api_key,
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "requests_count": 0
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        if session_id not in self.sessions:
            return None

        session = self.sessions[session_id]
        if datetime.now() - session["last_activity"] > self.session_timeout:
            del self.sessions[session_id]
            return None

        session["last_activity"] = datetime.now()
        session["requests_count"] += 1
        return session

    def cleanup_expired_sessions(self):
        now = datetime.now()
        expired_sessions = [
            sid for sid, session in self.sessions.items()
            if now - session["last_activity"] > self.session_timeout
        ]
        for sid in expired_sessions:
            del self.sessions[sid]

# Global instances
rate_limiter = RateLimiter()
session_manager = SessionManager()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)) -> Dict[str, Any]:
    """
    Verify API key from Authorization header
    Returns session information if valid
    """
    token = credentials.credentials
    expected_key = os.getenv("LOCAL_API_KEY")

    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: LOCAL_API_KEY not set"
        )

    if token != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check rate limit
    if not rate_limiter.is_allowed(token):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again later."
        )

    # Create or get session
    session_id = session_manager.create_session(token)

    return {
        "api_key": token,
        "session_id": session_id,
        "authenticated": True,
        "timestamp": datetime.now().isoformat()
    }

def verify_client_mode() -> bool:
    """Check if running in client mode"""
    return os.getenv("IS_SERVER", "true").lower() == "false"

def get_remote_config() -> Dict[str, str]:
    """Get remote server configuration for client mode"""
    if not verify_client_mode():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not running in client mode"
        )

    remote_url = os.getenv("REMOTE_API_URL")
    remote_key = os.getenv("REMOTE_API_KEY")

    if not remote_url or not remote_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Remote server configuration missing"
        )

    return {
        "url": remote_url,
        "api_key": remote_key
    }

async def log_api_request(endpoint: str, method: str, session_info: Dict[str, Any],
                         status_code: int, response_time: float):
    """Log API request for audit trail"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "endpoint": endpoint,
        "method": method,
        "session_id": session_info.get("session_id"),
        "status_code": status_code,
        "response_time_ms": round(response_time * 1000, 2)
    }

    # You can extend this to write to a log file or database
    print(f"API Request: {log_entry}", flush=True)

def cleanup_sessions():
    """Cleanup expired sessions - call this periodically"""
    session_manager.cleanup_expired_sessions()