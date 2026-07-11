import hmac
import re
import secrets

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import COOKIE_NAME, get_current_user
from ..models import User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

USERNAME_RE = re.compile(r'^[a-zA-Z0-9_]{3,30}$')


@router.get("/register", response_class=HTMLResponse)
async def register_form(request: Request, db: Session = Depends(get_db)):
    """Show the registration form."""
    current_user = get_current_user(request, db)
    if current_user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "auth/register.html",
        {"request": request, "title": "Register", "current_user": None}
    )


@router.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    display_name: str = Form(""),
    db: Session = Depends(get_db)
):
    """Create a new user account."""
    # Validate username format
    if not USERNAME_RE.match(username):
        return templates.TemplateResponse(
            "auth/register.html",
            {
                "request": request,
                "title": "Register",
                "current_user": None,
                "error": "Username must be 3–30 characters: letters, numbers, and underscores only.",
                "username": username,
                "display_name": display_name,
            },
            status_code=400,
        )

    # Check uniqueness
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        return templates.TemplateResponse(
            "auth/register.html",
            {
                "request": request,
                "title": "Register",
                "current_user": None,
                "error": "That username is already taken. Please choose another.",
                "username": username,
                "display_name": display_name,
            },
            status_code=400,
        )

    # Create the user
    account_secret = secrets.token_urlsafe(36)
    user = User(
        username=username,
        account_secret=account_secret,
        display_name=display_name.strip() or None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Store secret in session for one-time display
    request.session['new_account_secret'] = account_secret
    request.session['new_account_username'] = user.username

    response = RedirectResponse(url="/auth/register/success", status_code=303)
    response.set_cookie(
        key=COOKIE_NAME,
        value=str(user.id),
        httponly=True,
        max_age=365 * 24 * 60 * 60,  # 1 year
    )
    return response


@router.get("/register/success", response_class=HTMLResponse)
async def register_success(request: Request, db: Session = Depends(get_db)):
    """Show the account secret one time after registration."""
    secret = request.session.pop('new_account_secret', None)
    username = request.session.pop('new_account_username', None)
    current_user = get_current_user(request, db)

    if not secret:
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        "auth/register_success.html",
        {
            "request": request,
            "title": "Save Your Account Secret",
            "current_user": current_user,
            "username": username,
            "account_secret": secret,
        }
    )


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, db: Session = Depends(get_db)):
    """Show the login form."""
    current_user = get_current_user(request, db)
    if current_user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "auth/login.html",
        {"request": request, "title": "Login", "current_user": None}
    )


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    account_secret: str = Form(...),
    db: Session = Depends(get_db)
):
    """Validate account secret and set session cookie."""
    user = db.query(User).filter(User.username == username).first()

    # Use constant-time comparison to prevent timing attacks
    secret_matches = (
        user is not None
        and hmac.compare_digest(user.account_secret, account_secret)
    )

    if not secret_matches:
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "title": "Login",
                "current_user": None,
                "error": "Invalid username or account secret.",
                "username": username,
            },
            status_code=401,
        )

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key=COOKIE_NAME,
        value=str(user.id),
        httponly=True,
        max_age=365 * 24 * 60 * 60,
    )
    return response


@router.post("/logout")
async def logout(request: Request):
    """Clear the session cookie."""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response
