from fastapi import APIRouter,Depends
from prisma import Prisma
from pydantic import BaseModel
from uuid import UUID
from auth.utils import create_access_token, get_current_user 
from datetime import datetime, timedelta, timezone
from typing import Any
from pydantic import EmailStr

# Pydantic model to mirror the Prisma UserInstance model
class UserInstanceBase(BaseModel):
    clerkId: str
    email: EmailStr
    isAdmin: bool = False

class UserInstanceCreate(UserInstanceBase):
    pass

class UserInstance(UserInstanceBase):
    id: UUID

    class Config:
        orm_mode = True  # Allows Pydantic to work with ORM models (e.g., Prisma)

# Define a response model
class TokenResponse(BaseModel):
    user: Any
    token: str

router = APIRouter()
db = Prisma()


@router.post('/user/get_or_create_user_instance', response_model=TokenResponse)
async def get_or_create_user_instance(user: UserInstanceCreate):
    """Gets an existing user or creates a new one, then generates an access token."""
    await db.connect()
    
    try:
        # Check if user already exists
        existing_user = await db.userinstance.find_unique(
            where={"clerkId": user.clerkId},
            include={"subscription": True}  # Ensure we fetch the related subscription
        )

        if existing_user:
            token = create_access_token(data={
                "id": existing_user.id,
                "sub": existing_user.clerkId,
                "exp": (datetime.now(timezone.utc) + timedelta(days=365)).timestamp(),
                "isAdmin": existing_user.isAdmin,
                "subscriptionType": existing_user.subscription.planType if existing_user.subscription else None  # Handle None case
            })
            return TokenResponse(user=existing_user, token=token)

        # Create new user
        new_user = await db.userinstance.create(
            data={
                "clerkId": user.clerkId,
                "email": user.email,
                "isAdmin": user.isAdmin,
            }
        )

        token = create_access_token(data={
            "id": new_user.id,
            "sub": new_user.clerkId,
            "exp": (datetime.now(timezone.utc) + timedelta(days=7)).timestamp(),
            "isAdmin": new_user.isAdmin,
            "subscriptionType": None  # New users don't have a subscription yet
        })

        return TokenResponse(user=new_user, token=token)

    finally:
        await db.disconnect() 


@router.get('/me')
async def get_current_user(payload = Depends(get_current_user)):
    """Returns the user associated with the given access token."""
    print(payload)
    return {"member": payload}
