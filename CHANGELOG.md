# Changelog

All notable changes to Coverbound will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2026-09-19

A warm literary redesign, real cover art, Google sign-in, and a security pass
over authentication and club privacy.

### Breaking Changes

- **Everyone is logged out once.** Identity moved from an unsigned
  `coverbound_user_id` cookie into the `SECRET_KEY`-signed session, so existing
  browser cookies stop being accepted. Members log in again; nothing else is
  affected.
- **`coverbound.env` is no longer tracked in git.** `coverbound.env.example` is
  the template; `make init` copies it and generates a `SECRET_KEY`. Your existing
  env file is untouched — but it will no longer be overwritten by a `git pull`.
- **Club contents are members-only.** Book pages, discussions, reviews, meetings,
  the shelf and reading progress all require membership. Previously anyone with a
  club code — or a guessed book id — could read a club's discussions and reviews.
  `is_public` now controls *listing* in the directory, not readability.
- **Choosing the club's next read is admin-only**: spinning the reel, closing a
  vote, assigning a book and archiving one. Suggesting, voting and vetoing are
  unchanged.
- Complete visual overhaul: the generic indigo/gray theme is replaced by a warm
  literary identity (Newsreader + Hanken Grotesk, cream/brown/terracotta) built on
  semantic color tokens (`bg-surface`, `text-ink`, `border-line`, `text-accent`)
  rather than hardcoded palette classes
- `templates.TemplateResponse(name, context)` replaced with the request-first
  signature `TemplateResponse(request, name, context)` across all 28 call sites —
  required by Starlette ≥ 1.0
- Creating a club now lands on a new-club empty state (`/clubs/{code}/welcome`)
  instead of the club dashboard
- `package-lock.json` is now committed (previously gitignored) — the Dockerfile's
  `npm ci` requires it

### Security

- **Fixed an authentication bypass.** The login cookie was an unsigned, plain
  user id (`coverbound_user_id=1`), so anyone could edit it in devtools and act
  as any account. Identity now lives in the `SECRET_KEY`-signed session cookie.
- The app refuses to start with `DEBUG=false` and no `SECRET_KEY`, rather than
  falling back to a hardcoded default that would make every deployment's session
  cookies forgeable.
- Session cookie is now `SameSite=Lax`, `HttpOnly`, and `Secure` outside debug.
- `DEBUG` now defaults to `false` in the shipped env template. `DEBUG=true` drops
  the `Secure` flag from session cookies and is for local development only.
- Club content requires membership across `/books/{id}`, `/discussions/book/{id}`,
  `/ratings/book/{id}`, `/meetings/club/{code}`, `/clubs/{code}` and
  `/clubs/{code}/shelf`. Book ids are sequential, so these were enumerable.

### Added

- **Google sign-in** (OpenID Connect via Authlib), off unless `GOOGLE_CLIENT_ID`
  and `GOOGLE_CLIENT_SECRET` are configured. Authorization-code flow with PKCE
  (`S256`), `state`, `nonce`, and ID-token signature validation against Google's
  JWKS.
  - First-time Google visitors choose their own username rather than inheriting
    one from their email address, and are warned if an existing account already
    holds that address.
  - Connect / disconnect from **Account settings → Security**. Linking is always
    explicit — signing in with Google never silently adopts an existing account,
    even on an email match.
  - Disconnecting from an account with no account secret generates one and
    reveals it once, instead of locking the owner out.
  - `PUBLIC_BASE_URL` builds the OAuth redirect URI correctly behind a proxy.
- **Real book covers.** Every book shows its actual cover art from Open Library.
  Books added from search arrive with one; books typed in by hand get theirs
  looked up in the background, so the colored placeholder is a fallback rather
  than the normal case. Art appears everywhere a book is drawn — club home,
  shelf, picker, recaps, book page, search results, header switcher, public
  directory and profile club chips.
- **The landing hero rotates.** Three spines showing real covers drawn at random
  per page load from a pool of Open Library's best-rated fiction, one book per
  author so a hero never shows two volumes of the same series.
- Pre-login landing page with a looping marquee of publicly listed clubs
- Book page (finished-book look-back) and full shelf list
- **Choose next book**: voting mode with admin-gated vote-count visibility, a
  configurable threshold and veto; or random mode with a decelerating cover reel.
  Both end in an acknowledgment modal, and the pick is held server-side so the
  book that gets assigned is always the one that was actually drawn.
- Book search via the Open Library API, with manual entry as a fallback
- Year in books recaps, per club and personal (across all clubs)
- Per-member reading progress with a collapsible summary and an exact
  page-number control
- Clubs switcher in the header
- **In-app feedback**: stores a `feedback` row and opens a GitHub issue
  (`GITHUB_TOKEN` / `GITHUB_REPO`); degrades gracefully with no token or on API
  failure. Requires sign-in and is rate limited to 5 per hour per account, since
  each submission spends a write on an external issue tracker.
- Per-club feature toggles: reading progress, year in books, public directory
  listing, live vote counts
- Migration `004`: club feature flags, book page count / cover colors / Open
  Library id, `member_book_progress` and `feedback` tables
- Migration `005`: `google_sub` (unique), `email`, `email_verified`,
  `avatar_url` on `users`; `account_secret` becomes nullable
- Migration `006`: `meetings.host_id` and `meeting_schedules.current_host_id`
  become nullable, so a departing member doesn't take the club's meetings
- `scripts/refresh_popular_books.py` rebuilds the landing pool into
  `app/popular_books.json`, verifying every cover actually loads first. Nothing
  calls it at runtime. The pool is narrowed to `subject:fiction` — unfiltered,
  "best rated" mixes novels with business and self-help titles, accurate but
  jarring on a book club's front page. `--subject ''` turns that off.
- `scripts/backfill_covers.py` fetches cover art for books that predate the
  lookup. Safe to re-run; it skips books that already have one.
- `make check`, `check-auth`, `check-ui`, `check-shell` and `shots` targets for
  the dev harnesses

### Changed

- **Licensing is now stated consistently.** The repo shipped a GPL-3.0 `LICENSE`
  while the README said "TBD" and `package.json` declared nothing. All three now
  say GPL-3.0-or-later, and every first-party source file carries an SPDX header.
- The footer shows the running version, the license and a link to the source.
  The version reads from `app/version.py`, so a release bump reaches it with no
  template edit. A fork running modified code can point the source link at its
  own repository with `SOURCE_URL`.
- `coverbound.env` is now loaded when running outside Docker too (`python-dotenv`
  was a declared dependency that nothing used), so a local uvicorn run picks up
  the same configuration the container gets from `env_file`.
- Logging in with the account-secret form on a Google-only account now says so,
  instead of reporting invalid credentials.
- Routers share one Jinja environment (`app/templating.py`) instead of
  constructing their own
- Starlette is now pinned explicitly rather than left to FastAPI's range
- Dev harnesses (`scripts/check_all.js`, `check_shell.js`, `shots.js`,
  `seed_demo.py`) authenticate by posting the real login form — they previously
  hand-set the identity cookie, which the security fix rightly makes impossible.
- Cover art is requested at the size it is rendered: Open Library's `-L` variant
  above 90px, `-M` below, so large covers are no longer upscaled from a 180px
  image.
- A cover that fails to load falls back to the colored placeholder instead of a
  broken-image icon — the placeholder is always rendered underneath and the art
  is layered over it.
- Book cards are held back until their cover can be painted and then revealed
  whole, instead of a coloured placeholder taking delivery of a picture while
  the reader watches.
  - The trigger is the image's `decode()`, not its `load` event: `load` only
    means the bytes are in, so with `decoding="async"` a reveal could start
    against a frame that was still decoding and the picture would snap in.
  - A card is never held more than 1.2s. If the cover is slow, lazy or dead, the
    card comes up on time and the art fades in afterwards — text is never held
    hostage to a third-party image.
  - Cards with no cover art are not held. Hidden cards still occupy their space,
    so nothing reflows when one lands.
  - Three covers keep the lighter per-image fade instead, because they are not
    cards and hiding their container would hide navigation: the 30px spine in the
    header switcher, the 18px spine on profile club chips, and the covers in the
    picker's spin reel. The coloured spine underneath fades out on the same
    curve, so the two never read as a double exposure, and only `opacity`
    animates — a late cover can never shift layout. The reduced-motion backstop
    collapses it to an instant swap, and a `<noscript>` rule keeps the art
    visible without JavaScript.
- `preconnect`/`dns-prefetch` hints for `covers.openlibrary.org` and
  `archive.org`. A cover costs two hops — Open Library 302s into a zip on
  archive.org — and on a cold connection the handshakes were over half of the
  roughly one second before the first byte arrived.
- The two covers above the fold — a club's currently-reading book and the book
  page — load eagerly at high priority instead of lazily.
- Looking a cover up no longer blocks the suggest form. Open Library can take
  seconds to answer, so the fetch runs after the response is sent.
- **Join a club** now offers the public directory alongside the code form, with
  the number of listed clubs, and hides the offer when nothing is listed. Joining
  still needs a code: listing a club publicly makes it discoverable, not open.

### Fixed

- **Account deletion no longer fails.** Deleting an account that had finished any
  book raised `NOT NULL constraint failed: member_book_completions.member_id`.
  Every table referencing `members.id` now cascades from the `Member` mapper
  rather than from a hand-maintained list that new tables kept falling out of.
- **Leaving a club no longer strands it without an admin**, and no longer orphans
  the departing member's posts, votes, ratings and progress.
- Meetings and recurring schedules survive the departure of their host instead of
  blocking the delete; a hostless schedule can be taken over by an admin.
- `select-random` no longer crashes on a book with a `NULL` weight.
- Static assets were served with `last-modified` and `etag` but no
  `Cache-Control`, so browsers fell back to heuristic freshness — roughly a tenth
  of the file's age — and would reuse a cached stylesheet for days without
  revalidating. Rebuilding the image shipped CSS the browser never asked for,
  which made front-end changes look like they had simply not happened. Asset URLs
  now carry an mtime stamp (`asset_url()`).
- `app/routers/meetings.py` imported `pytz` without declaring it in
  `requirements.txt`; the import was unused and has been removed (icalendar 7.x
  no longer supplies pytz transitively).
- `npm run version:sync` failed with an unterminated quoted string;
  `update_version.sh` also now keeps `package-lock.json`'s root version in step,
  which `npm ci` requires.
- Native date/time pickers and number spinners rendered light-on-dark; `.dark`
  now sets `color-scheme: dark`.
- `.gitignore`'s Python-venv patterns (`lib/`, `dist/`, `build/`, `env/`, `var/`
  and friends) had no leading slash, so they matched at any depth — an ordinary
  `app/static/lib/` or `app/static/dist/` would have been silently skipped by
  `git add .` and never reached the Docker build. They are now anchored to the
  repository root.

### Dependencies

- Upgraded to clear 27 known CVEs: FastAPI 0.109.0 → 0.141.1, Starlette
  0.35.1 → 1.6.0 (CVE-2026-48710 "BadHost"), python-multipart 0.0.6 → 0.0.32,
  Jinja2 3.1.3 → 3.1.6, requests 2.31.0 → 2.34.2, python-dotenv 1.0.0 → 1.2.3,
  plus SQLAlchemy, Alembic, uvicorn, pydantic, pydantic-settings, itsdangerous
  and icalendar
- Added `authlib==1.7.2` and `httpx==0.28.1` (which bring `joserfc`,
  `cryptography`, `httpcore`, `cffi`, `pycparser`). `pip-audit`: no known
  vulnerabilities.

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

[Unreleased]: https://github.com/Domatron22/bookclub/compare/v3.0.0...HEAD
[3.0.0]: https://github.com/Domatron22/bookclub/compare/v2.0.2...v3.0.0
[2.0.2]: https://github.com/Domatron22/bookclub/compare/v2.0.1...v2.0.2
[2.0.1]: https://github.com/Domatron22/bookclub/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/Domatron22/bookclub/compare/v1.0.1...v2.0.0
[1.0.1]: https://github.com/Domatron22/bookclub/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/Domatron22/bookclub/releases/tag/v1.0.0
