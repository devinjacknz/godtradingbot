import json
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

router = APIRouter()

GOOGLE_CLIENT_CONFIG = {
    "web": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "project_id": os.getenv("GOOGLE_PROJECT_ID"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "redirect_uris": [
            os.getenv(
                "GOOGLE_REDIRECT_URI", "http://localhost:3001/api/auth/google/callback"
            )
        ],
        "javascript_origins": [os.getenv("FRONTEND_URL", "http://localhost:3001")],
    }
}


@router.get("/google")
async def google_login():
    flow = Flow.from_client_config(
        GOOGLE_CLIENT_CONFIG,
        scopes=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
        ],
        redirect_uri=GOOGLE_CLIENT_CONFIG["web"]["redirect_uris"][0],
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true"
    )
    return RedirectResponse(authorization_url)


@router.get("/google/callback")
async def google_callback(request: Request, code: str):
    try:
        flow = Flow.from_client_config(
            GOOGLE_CLIENT_CONFIG,
            scopes=[
                "openid",
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile",
            ],
            redirect_uri=GOOGLE_CLIENT_CONFIG["web"]["redirect_uris"][0],
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials

        service = build("oauth2", "v2", credentials=credentials)
        user_info = service.userinfo().get().execute()

        # Store session in a secure way (e.g., JWT, secure cookie)
        response = RedirectResponse(url="/")
        response.set_cookie(
            key="session",
            value=json.dumps(
                {
                    "email": user_info.get("email"),
                    "name": user_info.get("name"),
                    "picture": user_info.get("picture"),
                }
            ),
            httponly=True,
            secure=True,
            samesite="lax",
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/check-session")
async def check_session(request: Request):
    session = request.cookies.get("session")
    if not session:
        return {"isAuthenticated": False}
    try:
        user_data = json.loads(session)
        return {"isAuthenticated": True, "user": user_data}
    except:
        return {"isAuthenticated": False}


@router.post("/logout")
async def logout():
    response = Response()
    response.delete_cookie(key="session")
    return response
