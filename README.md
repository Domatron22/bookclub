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

Settings live in `coverbound.env`. That file is **not** tracked in git — it
holds this deployment's signing key. `coverbound.env.example` is the tracked
template; `make init` copies it and fills in a `SECRET_KEY` for you.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Database connection string (default: SQLite) |
| `SECRET_KEY` | Signs session cookies. Generated per deployment by `make init` |
| `DEBUG` | Debug mode. Leave `false` anywhere reachable from a network |
| `GITHUB_TOKEN` / `GITHUB_REPO` | Optional: mirror in-app feedback to GitHub issues |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Optional: enable Google sign-in |
| `PUBLIC_BASE_URL` | The address users type. Required behind a reverse proxy |
| `SOURCE_URL` | Where this deployment's source lives, linked from the footer. Set it if you run modified code |

`SECRET_KEY` is what stops someone forging a login: the session cookie carries
the signed-in user's id, so a key that is shared between deployments — or
committed to a repo — lets anyone mint a session for any account. `make init`
generates one and refuses to continue if it cannot. With `DEBUG=false` the app
will not start without it.

`DEBUG=true` also drops the `Secure` flag from session cookies so the app works
over plain HTTP locally. Never run it that way in public.

## Privacy model

A club's contents — its shelf, book pages, discussions, reviews, meetings and
per-member reading progress — are visible only to that club's members. There is
no "anyone with the link" tier: a non-member who follows a club URL is sent to
the join form.

`is_public` controls **listing**, not readability. A club that opts in appears
in `/clubs/browse` with its name, description, member and book counts, and what
it is currently reading — enough to decide whether to ask for a code. Everything
past that needs membership.

Choosing the club's next read — spinning the reel, closing a vote, assigning a
book, archiving one — is restricted to club admins. Any member can suggest
books, vote and veto.

## Authentication

Coverbound supports two ways in. Both resolve to the same account, and one
account can use either.

### Username + account secret (always available)

- Register with a unique username
- Your account secret is shown **once** — save it in a password manager
- Log in from any device using your username and account secret
- No email or password required

### Google sign-in (optional)

Off unless configured, so a self-hoster is never forced to create a Google
Cloud project. When it is configured, "Continue with Google" appears on the
login and register screens, and existing accounts can connect Google from
**Account settings → Security**.

Setting it up:

1. In the [Google Cloud console](https://console.cloud.google.com/apis/credentials),
   configure the OAuth consent screen (User type **External**; scopes `openid`,
   `email`, `profile`).
2. Create an **OAuth client ID** of type *Web application*.
3. Add an authorised redirect URI — your public address plus
   `/auth/google/callback`, matched exactly:

   ```
   https://coverbound.club/auth/google/callback
   http://localhost:8000/auth/google/callback     # for local development
   ```

4. Put the credentials in `coverbound.env` and restart:

   ```
   GOOGLE_CLIENT_ID=...apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=...
   PUBLIC_BASE_URL=https://coverbound.club
   ```

`PUBLIC_BASE_URL` matters behind a reverse proxy. The app otherwise builds the
redirect URI from the request it sees — typically `http://` on an internal
host — and Google rejects any URI that isn't character-for-character one you
registered.

Notes on how accounts are matched:

- Accounts are keyed on Google's **subject identifier**, not email. People
  change their Google address and addresses get recycled; matching on email
  would let a new owner of an old address inherit someone else's clubs.
- Signing in with Google for the first time creates a **new** account and asks
  you to choose a username. To attach Google to an account you already have,
  log in with your account secret first and use **Connect** in settings.
- An account created through Google has no account secret. Disconnecting Google
  generates one and shows it to you once, rather than locking you out.

### A note on sessions

Login identity lives in a signed session cookie. `SECRET_KEY` therefore has to
be set and unique per deployment — with `DEBUG=false` the app refuses to start
without one. `make init` generates it, and says which of the three things it
did: created the env file, generated a key, or left an existing key alone.

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

### Upgrading to v3.0.0

v3.0.0 adds three migrations on top of the above. Run the same command:

```bash
DATABASE_URL=sqlite:///./data/coverbound.db alembic upgrade head
```

- **Migration 004**: Adds club feature flags (`feature_progress`, `feature_recap`,
  `is_public`, `votes_visible`), book metadata (`page_count`, cover colors,
  `open_library_id`), and the `member_book_progress` and `feedback` tables.
- **Migration 005**: Adds `google_sub` (unique), `email`, `email_verified` and
  `avatar_url` to `users`, and makes `account_secret` nullable so accounts
  created through Google can exist without one.
- **Migration 006**: Makes `meetings.host_id` and
  `meeting_schedules.current_host_id` nullable, so a member can be removed
  without taking the club's meetings with them.

Feature-flag defaults are chosen so nothing changes behaviour on upgrade:
reading progress and year-in-books are **on**, while public directory listing
and live vote counts are **off** — an upgrade will not publish an existing club
or reveal running vote tallies. Adjust them per club under **Club admin → Club
features**.

Existing accounts keep their usernames and secrets, and Google stays switched
off until you configure credentials.

> If your database predates Alembic (created by `create_all()` rather than
> migrations), stamp it before upgrading:
> `DATABASE_URL=sqlite:///./data/coverbound.db alembic stamp 003`

#### Four things to know before you upgrade

> **Everyone is logged out once.** Identity moved from an unsigned
> `coverbound_user_id` cookie into the signed session, so existing browser
> cookies stop being accepted. This is deliberate: the old cookie held a bare
> user id and could be edited by hand to impersonate any account. Members just
> log in again; nothing else is affected.

> **`coverbound.env` is no longer tracked in git.** The tracked template is now
> `coverbound.env.example`. Your existing file is left alone and keeps working —
> but it is now gitignored, so it will not be clobbered by a `git pull`, and
> `make init` will not overwrite a key you already have. If you are deploying
> fresh, `make init` creates the file and generates the key.

> **Club contents are now members-only.** Previously anyone holding a club code
> — or guessing a book id — could read a club's discussions and reviews. See
> [Privacy model](#privacy-model). If you were relying on sharing a club URL
> with non-members, they will now be asked to join instead.

> **Choosing the next book is admin-only.** Spinning the reel, closing a vote
> and assigning a book now require club admin. Suggesting, voting and vetoing
> are unchanged.

### Troubleshooting: container won't start with a SQLite error

`unable to open database file` (or `attempt to write a readonly database`) almost
always means the container can't write to `./data`.

The container runs as `APP_UID:APP_GID` (4001 by default) and its filesystem is
read-only apart from the `./data` bind mount. If that directory was created by
your host user — by running the app directly, or by `scripts/seed_demo.py` —
it's owned by you, not 4001, and SQLite can't create the database inside it.

Check the ownership:

```bash
ls -ldn data
```

Then pick one:

```bash
# Give the directory to the container's user (what `make init` does)
sudo chown 4001:4001 data

# …or run the container as yourself, no sudo required
APP_UID=$(id -u) APP_GID=$(id -g) docker compose up -d
```

The second is also `make start APP_UID=$(id -u) APP_GID=$(id -g)`. Whichever you
choose, be consistent — switching between them leaves files the other user can't
write.

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

## Tests

```bash
pip install -r requirements-dev.txt
make test          # 95 tests, ~16s, no running app needed
```

The suite blocks all outbound network calls, so it is deterministic and works
offline. A test that quietly reaches Open Library fails with *"a test tried to
make a real network call"* rather than hanging on a timeout.

The browser sweeps are separate, because they drive a live app and need
Playwright:

```bash
make check-ui      # every screen, both themes, all breakpoints, plus flows
make check-auth    # session and Google sign-in regression harness
make shots PATH_=/clubs/ABC12345
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

Coverbound is free software, licensed under the **GNU General Public License,
version 3 or later**. The full text is in [LICENSE](LICENSE).

In short: you may use, study, modify and share it, including commercially. If
you distribute it — modified or not — you must pass on those same freedoms and
make your source available under the same terms.

Copyright (C) 2026 Domatron22

Every first-party source file carries an [SPDX](https://spdx.dev/) header, so
the license is machine-readable without parsing this file:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
```

> **A note on hosting.** The GPL's copyleft is triggered by *distributing* the
> software, not by running it as a service. Someone may host a modified
> Coverbound for other people without publishing their changes. AGPL-3.0 is the
> variant that closes that gap by treating network use as triggering the same
> obligation — worth knowing about for a self-hosted web app, though switching
> is a deliberate decision, not a typo fix.

## Author

Domatron22