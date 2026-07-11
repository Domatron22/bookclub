# Coverbound - Self-Hosted Book Club Management

A self-hosted web application for managing book clubs with user accounts, random book selection, discussions, and member management.

## Features

### Current Feature
- [X] Username-based user accounts with account secret authentication
- [X] Club creation with unique join codes
- [X] Book suggestion submission with metadata
- [X] Random book selection from suggestion pool
- [X] Currently reading book display
- [X] Individual member book completion tracking
- [X] Basic discussion threads per book
  - [X] Spoiler tags/collapsible sections
- [X] Reading history/archive of past books
- [X] Calendar view of upcoming meetings
  - [X] RSVP System
- [X] Admin Interface
  - [X] Admin-only book archiving
  - [X] Set book selection type (Vote, Random)
    - [X] Adjustable Percentage Of Group
  - [X] Enable/Disable book veto
    - [X] Adjustable Percentage Of Group
- [X] Book Review Section
- [X] Currently Reading Count
- [X] Public user profile page (`/profile/{username}`) — reading stats, bio, favorites, reading history, visible clubs
- [X] Account settings page — display name, bio, favorite genre/book/author, privacy toggles, club visibility, account secret reveal, account deletion
- [X] Per-field privacy controls (bio, favorites, reading history)
- [X] Per-club profile visibility toggle
- [X] Favorite genre/book/author tracking

### TODOs:

#### Reading Management Features
- [ ] Reading pace tracker (chapter/page progress)
- [ ] Poll system for meeting times or tied book decisions

#### Social Features
- [ ] Book recommendation engine based on club history

#### Practical Features
- [ ] Library system integration for availability checking
- [ ] Links to purchase/borrow options

#### QOL Features
- [ ] Book cover display via OpenLibrary/Google Books API
- [ ] Genre/tag filtering for suggestions
- [ ] "Read again" option for club favorites
- [ ] Import books from Goodreads/other services
- [ ] Mobile-responsive design improvements
- [ ] Animation when selecting books
- [ ] Self-hosted font option (currently requires Google Fonts access)

## Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: SQLAlchemy ORM with SQLite (PostgreSQL supported)
- **Migrations**: Alembic
- **Frontend**: Jinja2 templates
- **Styling**: Tailwind CSS (compiled, not CDN)
- **Containerization**: Docker + Docker Compose

## Project Structure

```
coverbound/
├── docker-compose.yml           # Docker orchestration
├── Dockerfile                   # Multi-stage container build (Node + Python)
├── Makefile                     # Build and deployment commands
├── package.json                 # Node.js dependencies (Tailwind CSS)
├── tailwind.config.js           # Tailwind CSS configuration
├── requirements.txt             # Python dependencies
├── README.md                    # Project documentation
├── coverbound.env               # Environment variables template
├── alembic.ini                  # Alembic migration configuration
├── .gitignore                   # Git ignore rules
│
├── migrations/                  # Alembic migration scripts
│   └── versions/
│
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── database.py             # Database configuration
│   ├── models.py               # SQLAlchemy models (all database tables)
│   ├── dependencies.py         # Centralized auth dependencies
│   │
│   ├── routers/                # API route handlers
│   │   ├── auth.py            # Registration, login, logout
│   │   ├── clubs.py           # Club CRUD, join/leave, admin settings
│   │   ├── books.py           # Book suggestions, selection, veto, reading tracker
│   │   ├── discussions.py     # Discussion threads with infinite comment nesting
│   │   ├── meetings.py        # Meeting scheduling, RSVPs, calendar
│   │   ├── ratings.py         # Book reviews with infinite comment nesting
│   │   └── profile.py         # User profiles and account settings
│   │
│   ├── templates/              # Jinja2 HTML templates
│   │   ├── base.html          # Base template with nav, footer, dark mode toggle
│   │   ├── index.html         # Homepage with club listings
│   │   │
│   │   ├── auth/
│   │   │   ├── register.html      # Registration form
│   │   │   ├── register_success.html  # One-time account secret display
│   │   │   └── login.html         # Login form
│   │   │
│   │   ├── clubs/
│   │   │   ├── create.html    # Create new club form
│   │   │   ├── join.html      # Join club with code
│   │   │   ├── view.html      # Main club page with members dropdown
│   │   │   └── admin.html     # Admin settings panel with sliders
│   │   │
│   │   ├── discussions/
│   │   │   ├── list.html      # All discussions for a book
│   │   │   └── view.html      # Single discussion with recursive comments
│   │   │
│   │   ├── meetings/
│   │   │   ├── setup.html     # Initial meeting schedule setup
│   │   │   ├── create.html    # Create new meeting
│   │   │   ├── calendar.html  # Calendar view of all meetings
│   │   │   └── rsvp.html      # RSVP form with potluck coordination
│   │   │
│   │   ├── ratings/
│   │   │   └── list.html      # Reviews with recursive comments
│   │   │
│   │   └── profile/
│   │       ├── view.html      # Public profile page
│   │       └── settings.html  # Account settings (display name, bio, favorites, privacy, clubs, danger zone)
│   │
│   └── static/                 # Static assets
│       ├── css/
│       │   ├── input.css      # Tailwind source file
│       │   ├── tailwind.css   # Generated Tailwind CSS (production build)
│       │   └── custom.css     # Custom styles and dark mode overrides
│       │
│       └── js/
│           └── main.js        # JavaScript utilities
│
├── data/                       # Persistent data (SQLite DB)
│   └── coverbound.db          # SQLite database (auto-created)
│
└── node_modules/               # Node dependencies (gitignored)
    └── tailwindcss/           # Tailwind CSS CLI
```

## Getting Started

### Prerequisites
- Docker
- Docker Compose

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd coverbound
```

2. Initialize the project (generates a secret key):
```bash
make init
```

3. Build and run with Docker Compose:
```bash
make start
```

4. Access the application:
```
http://localhost:8000
```

## Configuration

Environment variables are set in `coverbound.env`:
- `DATABASE_URL`: Database connection string (default: SQLite)
- `SECRET_KEY`: Session encryption key (change in production!)
- `DEBUG`: Enable debug mode (true/false)

## Authentication

Coverbound uses a username + account secret system:
- Register with a unique username
- Your account secret is shown **once** — save it in a password manager
- Log in from any device using your username and account secret
- No email or password required

## Database Migrations

Coverbound uses [Alembic](https://alembic.sqlalchemy.org/) to manage schema changes. Migrations are required when upgrading from v1.x (session-based auth) to v2.0.0 (user accounts).

### Fresh installation

No action needed. `Base.metadata.create_all()` runs automatically on startup and creates all tables. Alembic is only required if you need to track the schema version explicitly:

```bash
DATABASE_URL=sqlite:///./data/coverbound.db alembic stamp head
```

### Upgrading an existing v1.x database to v2.0.0

The migration will create user accounts from your existing session data and drop the old `session_id` column. **Back up your database first.**

1. Install dependencies (if not using Docker):
```bash
pip install -r requirements.txt
```

2. Run all pending migrations:
```bash
DATABASE_URL=sqlite:///./data/coverbound.db alembic upgrade head
```

What this does:
- **Migration 001**: Creates the `users` table, generates one user account per existing member (username: `user_<id>`, account secret: auto-generated), links members to their new accounts, then drops `session_id`.
- **Migration 002**: Creates the `member_book_completions` table for individual reading tracking.
- **Migration 003**: Adds bio, favorite genre/book/author, and privacy toggle columns to `users`; adds `profile_visible` to `members`.

3. After migration, each existing member will have a new user account with an auto-generated account secret. You will need to reset those secrets manually or provide members with new credentials, as the generated secrets are not recorded anywhere.

### Checking migration status

```bash
DATABASE_URL=sqlite:///./data/coverbound.db alembic current
```

### Rolling back

```bash
# Roll back one step
DATABASE_URL=sqlite:///./data/coverbound.db alembic downgrade -1

# Roll back to a specific revision
DATABASE_URL=sqlite:///./data/coverbound.db alembic downgrade 000
```

> **Note for Docker users**: Migrations must be run outside the container against the database file in `./data/`, or exec'd into the running container: `docker exec -it coverbound-app alembic upgrade head`

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

TBD

## Author

Domatron22

Built with ❤️ for book lovers everywhere
