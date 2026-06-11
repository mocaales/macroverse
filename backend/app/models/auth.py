from pydantic import BaseModel, EmailStr


class UserResponse(BaseModel):
    uid: str
    email: EmailStr
