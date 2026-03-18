# Changelog

All notable changes to Coverbound will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.0.2] - 2026-03-17

### Changed
- Dockerfile rewritten as a three-stage multi-stage build: `css-builder` (node:20-slim) compiles Tailwind CSS, `pip-builder` (python:3.11-slim + gcc) installs Python dependencies into an isolated venv, `runtime` (python:3.11-slim) copies only the venv and app code — gcc and Node never reach the final image
- Container UID/GID is set via `user: "${UID:-4001}:${GID:-4001}"` in `docker-compose.yml`, matching the host user that owns the bind-mounted `./data` directory — no `chown` or build args required
- `make init` creates `./data` owned by the current host user; the compose `user:` field ensures the container process can write to it
- `docker-compose.yml` hardened: `no-new-privileges`, `cap_drop: ALL`, `read_only: true` filesystem with a 64 MB tmpfs at `/tmp`
- Added `.dockerignore` to exclude `.git`, `node_modules`, `.venv`, `__pycache__`, `data/`, secrets (`*.env`), and editor configs from the build context

## [2.0.1] - 2026-03-17

### Fixed
- Welcome banner shown after creating a new club had no dark mode styling, appearing as a bright light-green box inside a dark card
- Guest warning banner in club view had no dark mode styling
- Account secret dots (hidden state) were near-invisible in dark mode (`dark:text-gray-500` on `dark:bg-gray-700` yields ~1.6:1 contrast)
- Disabled username field in account settings was near-invisible in dark mode; also added `opacity-100` to prevent browsers from applying additional opacity reduction to disabled inputs
- Admin page flash message was missing all dark mode variants and used a non-existent `animate-slide-down` CSS class; replaced with `flash-animate` to match the rest of the app
- Replaced `fa-champagne-glasses` welcome icon (renders as a blank box in some environments) with `fa-circle-check`

## [2.0.0] - 2026-03-16

### Breaking Changes
- Project renamed from BookClub to **Coverbound**
- Session-based anonymous authentication replaced with username + account secret system
- `bookclub.env` renamed to `coverbound.env`
- Docker service renamed from `bookclub` to `coverbound`, container from `bookclub-app` to `coverbound-app`
- Existing session-based members are automatically migrated to user accounts (generated usernames: `user_{id}`)

### Added
- User accounts: register with a username, authenticate with an account secret
- Account secret displayed **once** on registration with copy-to-clipboard; never shown again
- `coverbound_user_id` cookie replaces old `session_id` cookie
- `GET /auth/register`, `POST /auth/register` — registration flow
- `GET /auth/login`, `POST /auth/login` — login with account secret
- `POST /auth/logout` — clear session
- Individual member book completion tracking (`MemberBookCompletion` model)
- `POST /books/{id}/member-complete` and `POST /books/{id}/member-uncomplete` — toggle personal read status
- "Mark as Finished" / "Finished Reading" toggle button on currently reading book
- Completion checkmarks in reader list for currently reading books
- "You read this" badge in Reading History for personally completed books
- Alembic migrations for all schema changes (`001_add_user_auth`, `002_add_member_book_completion`, `003_add_user_profile_fields`)
- `app/dependencies.py` — centralized auth helpers (`get_current_user`, `require_current_user`, `get_member_for_club`, `require_member_for_club`)
- User profile pages (`/profile/{username}`) — shows display name, reading stats, bio, favorites, reading history, and visible clubs; requires login to view
- Account settings page (`/profile/settings`) — six sections: Account (display name), Preferences (bio, favorite genre/book/author), Privacy (per-field visibility toggles), Club Visibility (per-club profile toggle), Security (click-to-reveal account secret), Danger Zone (account deletion with username confirmation)
- Per-field privacy controls: `bio_public`, `favorites_public`, `reading_history_public` on the User model
- Per-club profile visibility: `profile_visible` on the Member model
- Reading stats on profile: total books read, club count, most active club (from visible clubs only)
- Navbar profile link (`/profile/{username}`) and dedicated settings icon link

### Changed
- Club create/join now requires a logged-in account
- "Mark Complete" (archive book at club level) is now **admin-only**
- Flash messages on book archive success/failure
- All routers use shared auth dependency instead of local `get_current_member()` helpers
- Navbar shows auth links (Register/Login) when logged out, username + club links when logged in
- Updated `index.html` "Easy to Join" feature card text to reflect account system
- **UI redesign**: replaced Inter with DM Sans (body) and Lora (serif headings) for a more literary aesthetic
- Key section headings (club name, "Currently Reading", "Book Suggestions", "Reading History", display name, hero titles) now use the Lora serif font
- Added page entrance animation on every page load (subtle fade + slide-up on `<main>`)
- Added staggered entrance animations on feature cards and club cards (home page) and book suggestion cards (club page)
- Added card hover lift effect on feature cards, club cards, and book suggestion cards
- Added button lift animation on the Pick Random Book button
- Flash messages now slide in from above instead of appearing instantly
- Google Fonts now loaded via `<link>` in `base.html` with `preconnect` hints
- "Coverbound" logo text uses serif font with letter-spacing for a more editorial feel

### Fixed
- `fa-random` icon replaced with `fa-shuffle` (correct FA6 name; `fa-random` renders as a blank square in FA6)
- `fa-party-horn` replaced with `fa-champagne-glasses` (the original icon does not exist in Font Awesome free)
- `fa-history` replaced with `fa-clock-rotate-left` (correct FA6 name)
- `fa-user-friends` replaced with `fa-user-group` (correct FA6 name)
- `fa-id-card` replaced with `fa-quote-left` on the profile About section (better semantic match)
- `User.members` relationship now has `cascade="all, delete-orphan"` so deleting a user correctly removes all member rows

## [1.0.1] - 2024-12-25

### Fixed
- Fixed users inability to create new clubs

## [1.0.0] - 2024-12-24

### Added

#### Core System
- Session-based authentication
- Unique 8-character club codes for easy joining
- Club creation with name, description, and settings
- Member management with display names

#### Book Management System
- Book suggestion system with title, author, and description
- Random selection support
- Admin-configurable book veto system with configurable thresholds (5-100%, increments of 5%)
- Admin-configurable voting system for book selection
- Currently reading status display
- Reading history/archive of completed books
- Reading tracker - members can join/leave current book
- Expandable reader lists showing who read each book
- Historical reader data preserved after book completion

#### Discussion System
- Discussion threads for each book
- Infinite-depth comment nesting (recursive comments)
- Like functionality on posts and comments at all levels
- Spoiler protection with click-to-reveal
- Real-time comment counts
- Collapsible comment threads

#### Review System
- 5-star rating system for books
- Text reviews with star ratings
- Average rating calculation and display
- Infinite-depth comment nesting on reviews
- Like functionality on reviews and comments
- Review statistics (rating averages, review counts)

#### Meeting System
- Meeting schedule setup with rotation patterns
- Automatic host rotation system
- Meeting creation with date, time, location, and description
- RSVP system with Yes/No/Maybe options
- Potluck coordination (members can list what they're bringing)
- Attendee lists with RSVP status
- Calendar view of all meetings
- iCalendar (.ics) export for calendar apps
- Next meeting display on club homepage

#### Admin System
- Club admin roles with promotion/demotion
- Veto system configuration (enable/disable, percentage threshold)
- Book selection method configuration (random vs voting)
- Voting threshold configuration with sliders and text input
- Member management (promote to admin, view all members)

#### User Interface
- Dark mode support (light/dark/auto themes, theme preference stored in cookies)
- System theme detection for auto mode
- Responsive design for mobile and desktop
- Member dropdown on club page with admin indicators
- Reading tracker with join/leave buttons
- Icon system using Font Awesome 6.4.0

[Unreleased]: https://github.com/Domatron22/bookclub/compare/v2.0.2...HEAD
[2.0.2]: https://github.com/Domatron22/bookclub/compare/v2.0.1...v2.0.2
[2.0.1]: https://github.com/Domatron22/bookclub/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/Domatron22/bookclub/compare/v1.0.1...v2.0.0
[1.0.1]: https://github.com/Domatron22/bookclub/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/Domatron22/bookclub/releases/tag/v1.0.0
