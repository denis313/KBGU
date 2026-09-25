from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.config import get_settings
from app.deps import CurrentUser, DbSession
from app.models import User
from app.schemas import LoginIn, RegisterIn, TelegramLoginIn, TokenOut, UserOut
from app.security import create_access_token, hash_password, verify_password
from app.services.telegram import InitDataError, validate_init_data

router = APIRouter(prefix="/api/auth", tags=["auth"])


def user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, name=user.name, has_profile=user.profile is not None)


def _find_by_email(db: DbSession, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == email.lower()))


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, db: DbSession) -> TokenOut:
    if _find_by_email(db, data.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Этот email уже зарегистрирован")
    user = User(email=data.email.lower(), name=data.name.strip(), password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    return TokenOut(access_token=create_access_token(user.id), user=user_out(user))


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: DbSession) -> TokenOut:
    user = _find_by_email(db, data.email)
    if user is None or user.password_hash is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный email или пароль")
    return TokenOut(access_token=create_access_token(user.id), user=user_out(user))


@router.post("/telegram", response_model=TokenOut)
def telegram_login(data: TelegramLoginIn, db: DbSession) -> TokenOut:
    """Sign in from inside the Telegram Mini App; the account is created on first launch."""
    settings = get_settings()
    try:
        tg = validate_init_data(data.init_data, settings.telegram_bot_token, settings.telegram_init_data_max_age)
    except InitDataError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e

    user = db.scalar(select(User).where(User.telegram_id == tg.id))
    if user is None:
        user = User(telegram_id=tg.id, name=tg.full_name[:100])
        db.add(user)
    user.telegram_username = tg.username or None
    db.commit()
    return TokenOut(access_token=create_access_token(user.id), user=user_out(user))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return user_out(user)
