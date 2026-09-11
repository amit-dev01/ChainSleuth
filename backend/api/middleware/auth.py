"""
Authentication and role-based access control (RBAC) middleware.
Supports Law Enforcement API Key headers and JWT credentials for Investigating Officers.
"""

from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from backend.config.settings import get_settings

settings = get_settings()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_auth = HTTPBearer(auto_error=False)


async def get_current_user(
    api_key: Optional[str] = Security(api_key_header),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_auth)
) -> Dict[str, Any]:
    """
    Authenticate LEA officer via API key or JWT bearer token.
    Permits internal hackathon requests with mock IO identity if authentication is relaxed in development.
    """
    # 1. Check API Key
    if api_key:
        if api_key == settings.API_KEY_SECRET or api_key == "chainsleuth-demo-key-2026":
            return {
                "user_id": "io-delhi-cyber-001",
                "name": "Insp. Rajesh Kumar",
                "role": "INVESTIGATING_OFFICER",
                "agency": settings.LEA_ORGANIZATION,
                "badge_no": "DL-CY-8821"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Law Enforcement API Key"
            )

    # 2. Check Bearer Token (JWT)
    if credentials:
        token = credentials.credentials
        # Simplified token verification for hackathon demo
        if token == settings.SECRET_KEY or token.startswith("ey"):
            return {
                "user_id": "io-mumbai-cyber-002",
                "name": "Insp. Ananya Sharma",
                "role": "INVESTIGATING_OFFICER",
                "agency": settings.LEA_ORGANIZATION,
                "badge_no": "MH-CY-4910"
            }

    # Development / Demo Fallback
    if settings.DEBUG:
        return {
            "user_id": "dev-lea-officer",
            "name": "SIH Cyber Cell Investigator",
            "role": "INVESTIGATING_OFFICER",
            "agency": settings.LEA_ORGANIZATION,
            "badge_no": "SIH-2026-DEMO"
        }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide X-API-Key or Bearer token."
    )
