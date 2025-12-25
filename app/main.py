from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
import os

from .database import engine, get_db, Base
from .routers import clubs, books, discussions, meetings, ratings
from .version import __version__

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="BookClub",
    description="Self-hosted book club management application",
    version=__version__
)

# Add session middleware for flash messages
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "change-this-secret-key"))

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="app/templates")

# Include routers
app.include_router(clubs.router, prefix="/clubs", tags=["clubs"])
app.include_router(books.router, prefix="/books", tags=["books"])
app.include_router(discussions.router, prefix="/discussions", tags=["discussions"])
app.include_router(meetings.router, prefix="/meetings", tags=["meetings"])
app.include_router(ratings.router, prefix="/ratings", tags=["ratings"])


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    """Home page"""
    # Get user's clubs if they have a session
    user_clubs = []
    session_id = request.cookies.get("session_id")
    
    if session_id:
        from .models import Member
        # Find all clubs this user is a member of
        members = db.query(Member).filter(Member.session_id == session_id).all()
        user_clubs = [member.club for member in members]
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request, 
            "title": "BookClub - Home",
            "user_clubs": user_clubs
        }
    )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": __version__}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)