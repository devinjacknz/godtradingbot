import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, validator

from ...core.auth import (
    SignupRequest,
    Token,
    create_access_token,
    extract_request_context,
    get_current_active_user,
    get_password_hash,
    verify_password,
)
from ...models.user import User, UserCreate, UserRole

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticate user and return JWT token.
    """
    # Extract request context for logging
    context = extract_request_context(request)

    # Get user by email
    user = await User.get_by_email(form_data.username)  # username field contains email
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if user.disabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )

    # Create access token
    access_token = create_access_token(data={"sub": user.username})

    return Token(access_token=access_token, token_type="bearer")


class SignupRequestExtended(SignupRequest):
    @validator("password")
    def password_strength(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError("Password must contain at least one special character")
        return v

    @validator("email")
    def email_format(cls, v):
        """Validate email format."""
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Invalid email format")
        return v


@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
async def signup(request: Request, signup_data: SignupRequestExtended):
    """
    Create a new user account.

    Args:
        request: FastAPI request object
        signup_data: User signup data including email and password

    Returns:
        Token: JWT access token for the new user

    Raises:
        HTTPException: If email is already registered or validation fails
    """
    try:
        # Extract request context for logging
        context = extract_request_context(request)

        # Check if user already exists
        existing_user = await User.get_by_email(signup_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        # Create new user
        hashed_password = get_password_hash(signup_data.password)
        user_data = UserCreate(
            email=signup_data.email,
            username=signup_data.username,
            hashed_password=hashed_password,
            disabled=False,
            roles=[
                UserRole(
                    name="backend_developer",
                    permissions=["execute_market_maker_trades"],
                )
            ],
            request_context=context,
        )

        user = await User.create(user_data)

        # Create access token
        access_token = create_access_token(data={"sub": user.username})

        return Token(access_token=access_token, token_type="bearer")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the account",
        )
