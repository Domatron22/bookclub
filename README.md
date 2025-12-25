# BookClub - Self-Hosted Book Club Management

A self-hosted web application for managing book clubs with random book selection, discussions, and member management.

## Features

### Core Features (MVP)
- [X] Club creation with unique join codes
- [X] Session-based member participation (no account required)
- [X] Book suggestion submission with metadata
- [X] Random book selection from suggestion pool
- [X] Currently reading book display
- [X] Basic discussion threads per book
  - [X] Spoiler tags/collapsible sections
- [X] Reading history/archive of past books
- [X] Calendar view of upcoming meetings
  - [X] RSVP System
- [X] Admin Interface
  - [X] Set book selection type (Vote, Random)
    - [X] Adjustable Percentage Of Group
  - [X] Enable/Disable book veto 
    - [X] Adjustable Percentage Of Group
- [X] Book Review Section
- [X] Currently Reading Count

### TODOs:

#### Reading Management Features
- [ ] Reading pace tracker (chapter/page progress)
- [ ] Poll system for meeting times or tied book decisions

#### Social Features
- [ ] Book recommendation engine based on club history
- [ ] Favorite genres tracking
- [ ] Require users to join read before being able to contribute to discussions/reviews?

#### Practical Features
- [ ] Library system integration for availability checking
- [ ] Links to purchase/borrow options

#### QOL Features
- [ ] Book cover display via OpenLibrary/Google Books API
- [ ] Genre/tag filtering for suggestions
- [ ] "Read again" option for club favorites
- [ ] Import books from Goodreads/other services
- [ ] Mobile-responsive design
- [ ] Improve Choice Sliders to allow input to easily choose percentage
- [ ] Animation when selecting books

## Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: SQLAlchemy ORM with SQLite (PostgreSQL support planned)
- **Frontend**: Jinja2 templates + Alpine.js/HTMX for interactivity
- **Styling**: Tailwind CSS
- **Containerization**: Docker + Docker Compose

## Project Structure

```
bookclub/
├── docker-compose.yml           # Docker orchestration
├── Dockerfile                   # Multi-stage container build (Node + Python)
├── Makefile                     # Build and deployment commands
├── rebuild.sh                   # One-command full rebuild script
├── package.json                 # Node.js dependencies (Tailwind CSS)
├── tailwind.config.js           # Tailwind CSS configuration
├── requirements.txt             # Python dependencies
├── README.md                    # Project documentation
├── bookclub.env               # Environment variables template
├── .gitignore                  # Git ignore rules
│
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── database.py             # Database configuration
│   ├── models.py               # SQLAlchemy models (all database tables)
│   │
│   ├── routers/                # API route handlers
│   │   ├── clubs.py           # Club CRUD, join/leave, admin settings
│   │   ├── books.py           # Book suggestions, selection, veto, reading tracker
│   │   ├── discussions.py     # Discussion threads with infinite comment nesting
│   │   ├── meetings.py        # Meeting scheduling, RSVPs, calendar
│   │   └── ratings.py         # Book reviews with infinite comment nesting
│   │
│   ├── templates/              # Jinja2 HTML templates
│   │   ├── base.html          # Base template with nav, footer, dark mode toggle
│   │   ├── index.html         # Homepage with club listings
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
│   │   └── ratings/
│   │       └── list.html      # Reviews with recursive comments
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
├── data/                       # Persistent data (SQLite DB, uploads)
│   └── bookclub.db            # SQLite database (auto-created)
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
cd bookclub
```

2. Initialize the project:
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

Environment variables can be set in `.env` file:
- `DATABASE_URL`: Database connection string
- `SECRET_KEY`: Session encryption key
- `DEBUG`: Enable debug mode (true/false)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

TBD

## Author

Domatron22

Built with ❤️ for book lovers everywhere
