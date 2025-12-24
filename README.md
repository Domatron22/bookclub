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

### Discussion Features
- [X] Discussion threads for each book
- [X] Spoiler tags/collapsible sections
- [ ] Schedule discussion dates with reminders
- [ ] Rating/review system after finishing books
- [ ] Quote sharing from current reads

### Reading Management
- [ ] Reading pace tracker (chapter/page progress)
- [ ] Poll system for meeting times or tied book decisions
- [ ] Currently reading status indicator
- [X] Reading history/archive of past books
- [ ] Book completion tracking
  - [ ] USer count on who is reading the current book
  - [ ] After book is complete, list of users who were reading it

### Social Elements
- [ ] Member profiles with reading preferences
- [ ] Book veto system (members can veto suggestions)
  - [ ] Allow the group admin to set if vetos are allowed, and what percent of the group has to veto a book
- [ ] Allow admin to choose what system will be used to choose the book each time
  - [ ] Weighted random selection (some books get higher odds)
  - [ ] voting system
- [ ] Book recommendation engine based on club history
- [ ] Favorite genres tracking

### Practical Features
- [ ] Library system integration for availability checking
- [ ] Links to purchase/borrow options
- [ ] Export reading list/history
- [ ] Calendar view of upcoming meetings
- [ ] Email/notification system for reminders

### Nice-to-Haves
- [ ] Book cover display via OpenLibrary/Google Books API
- [ ] Genre/tag filtering for suggestions
- [ ] "Read again" option for club favorites
- [ ] Import books from Goodreads/other services
- [ ] Mobile-responsive design
- [ ] Dark mode theme

## Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: SQLAlchemy ORM with SQLite (PostgreSQL support planned)
- **Frontend**: Jinja2 templates + Alpine.js/HTMX for interactivity
- **Styling**: Tailwind CSS
- **Containerization**: Docker + Docker Compose

## Project Structure

```
bookclub/
├── docker-compose.yml       # Docker orchestration
├── Dockerfile              # Container definition
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── app/
│   ├── main.py           # FastAPI application entry point
│   ├── models.py         # SQLAlchemy models
│   ├── database.py       # Database configuration
│   ├── routers/          # API route handlers
│   │   ├── clubs.py
│   │   ├── books.py
│   │   └── discussions.py
│   ├── templates/        # Jinja2 HTML templates
│   └── static/          # CSS, JS, images
│       ├── css/
│       └── js/
└── data/                # Persistent data (SQLite DB, uploads)
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

2. Build and run with Docker Compose:
```bash
docker-compose up -d
```

3. Access the application:
```
http://localhost:8000
```

### Development

To run in development mode with hot reload:
```bash
docker-compose -f docker-compose.dev.yml up
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

## Roadmap

### Phase 1: MVP (Current)
- Basic club creation and joining
- Book suggestions and random selection
- Simple discussion threads

### Phase 2: Enhanced Features
- Reading progress tracking
- Voting and polling systems
- Member profiles and preferences

### Phase 3: Integration & Polish
- External API integrations (book data, libraries)
- Advanced recommendation engine
- Mobile app consideration

## Author

Built with ❤️ for book lovers everywhere
