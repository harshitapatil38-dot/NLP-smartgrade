from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.core.security import verify_password, create_access_token
from app.models.user import User
from app.schemas.auth import LoginRequest, Token

router = APIRouter(tags=["Auth"])

@router.post("/login", response_model=Token)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user and return a JWT."""
    user = db.query(User).filter(User.email == request.email).first()
    
    # Generic error logic: don't reveal if email exists, password is wrong, or user is inactive
    if not user or not verify_password(request.password, user.hashed_password) or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    access_token = create_access_token(subject=user.id, role=user.role.value)
    return Token(access_token=access_token, token_type="bearer")
