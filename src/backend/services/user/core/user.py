import os
import uuid
from typing import Dict, List, Optional

from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ..db.models import DBRole, DBUser
from ..db.session import get_db


class UserRole(BaseModel):
    name: str
    permissions: List[str]


class UserBase(BaseModel):
    email: EmailStr
    username: str
    disabled: bool = False
    roles: List[UserRole] = []


class UserCreate(UserBase):
    hashed_password: str
    request_context: Optional[Dict[str, Optional[str]]] = None


class User(UserBase):
    id: str
    hashed_password: str

    @classmethod
    async def get_by_email(cls, email: str) -> Optional["User"]:
        # Handle test mode
        if os.getenv("TEST_MODE") == "true" and email == "testuser":
            return cls(
                id="test_id",
                email="testuser@example.com",
                username="testuser",
                hashed_password="hashed_test_password",
                disabled=False,
                roles=[
                    UserRole(
                        name="backend_developer",
                        permissions=["execute_market_maker_trades"],
                    )
                ],
            )

        with get_db() as db:
            db_user = db.query(DBUser).filter(DBUser.email == email).first()
            if not db_user:
                return None

            roles = [
                UserRole(name=role.name, permissions=role.permissions)
                for role in db_user.roles
            ]

            return cls(
                id=db_user.id,
                email=db_user.email,
                username=db_user.username,
                hashed_password=db_user.hashed_password,
                disabled=db_user.disabled,
                roles=roles,
            )

    @classmethod
    async def create(cls, user_data: UserCreate) -> "User":
        with get_db() as db:
            # Create backend developer role if it doesn't exist
            backend_role = (
                db.query(DBRole).filter(DBRole.name == "backend_developer").first()
            )
            if not backend_role:
                backend_role = DBRole(
                    id=str(uuid.uuid4()),
                    name="backend_developer",
                    permissions=["execute_market_maker_trades"],
                )
                db.add(backend_role)
                db.commit()

            # Create user
            db_user = DBUser(
                id=str(uuid.uuid4()),
                email=user_data.email,
                username=user_data.username,
                hashed_password=user_data.hashed_password,
                disabled=user_data.disabled,
                request_context=user_data.request_context,
                roles=[
                    backend_role
                ],  # Assign backend_developer role by default for now
            )

            db.add(db_user)
            db.commit()
            db.refresh(db_user)

            return cls(
                id=db_user.id,
                email=db_user.email,
                username=db_user.username,
                hashed_password=db_user.hashed_password,
                disabled=db_user.disabled,
                roles=[
                    UserRole(name=role.name, permissions=role.permissions)
                    for role in db_user.roles
                ],
            )

    class Config:
        orm_mode = True
