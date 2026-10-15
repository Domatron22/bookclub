# Coverbound 3.0.0 — a warm redesign, real covers, and a security pass

*19 September 2026*

Coverbound is a self-hosted book club: you and some friends pick a book, read it,
argue about it, and keep a shelf of what you've finished. 3.0.0 is the largest
release so far. It looks like a different application, it knows what your books
actually look like, and it fixes an authentication flaw that had been there since
the beginning.

If you run an instance, **read the upgrade notes at the bottom before you pull.**
There are four breaking changes, and one of them logs everybody out.

---

## It looks like a book club now

The old theme was the one every side project starts with: indigo buttons, grey
cards, a system font stack. Functional and anonymous.

3.0.0 replaces it with something that belongs to the subject matter — Newsreader
for headings, Hanken Grotesk for interface text, and a palette of cream, brown
and terracotta. The whole thing is built on semantic colour tokens rather than
hardcoded classes, so light and dark are one system instead of two, and a future
retheme is a variable change rather than a rewrite.

There's a proper landing page for logged-out visitors, with a marquee of clubs
that have opted into the public directory.

## Real book covers, everywhere

Previously every book was a coloured rectangle with the title set in it. Now
books show their actual cover art, pulled from [Open Library](https://openlibrary.org).

Books added through search arrive with a cover already attached. Books typed in
by hand get theirs looked up **in the background, after the response is sent** —
Open Library can take a few seconds, and a form that hangs on a third party is a
form people stop using. The coloured spine is still there underneath as the
fallback, which means a missing or slow cover degrades to what 2.x always looked
like instead of a broken-image icon.

Covers turn up everywhere a book is drawn: the club home, the shelf, the picker,
recaps, the book page, search results, the header switcher, the public directory,
and the club chips on a profile.

Two details that took more work than they look like:

- **Cards wait for their cover, then appear whole.** The trigger is the image's
  `decode()`, not its `load` event — `load` only means the bytes arrived, so with
  async decoding a card could start revealing against a frame that was still
  decoding and the picture would snap in. A card is never held longer than 1.2
  seconds; if a cover is slow, lazy or dead, the text arrives on time and the art
  fades in behind it. Text is never held hostage to someone else's image server.
- **Covers are requested at the size they're rendered.** Open Library serves three
  fixed widths, and the large covers on the club home were being upscaled from a
  180px image.

If you're upgrading, `scripts/backfill_covers.py` fetches art for books that
predate the lookup. It's safe to re-run — it skips anything that already has one.

## Choosing the next book

This was the feature the app was missing. Two modes, set per club:

**Voting** — members vote, an admin closes it. The winner has to clear a
configurable threshold, and a tie is reported as a tie rather than quietly
resolved by list order. Vote counts can be hidden until voting closes.

**Chance** — a reel of covers spins and decelerates onto a pick, then an
acknowledgment modal confirms it.

Both paths end in the same modal, and the pick is held server-side between the
draw and the confirmation. That last part matters: the book that gets assigned is
always the one that was actually drawn, and a draw can only be spent once.

## Everything else that's new

- **A book page** for looking back at something you've finished, and a **full
  shelf** of everything the club has read.
- **Book search** against Open Library, with manual entry as a fallback for
  anything it doesn't know.
- **Year in books** recaps, per club and per person across all your clubs.
- **Reading progress** — an exact page number per member, with a collapsible
  summary on the club home. Off or on per club.
- **A clubs switcher** in the header, for people in more than one.
- **In-app feedback** that opens a GitHub issue. Sign-in required, rate limited,
  and it degrades quietly if no token is configured.
- **Google sign-in**, optional and off by default.

## Google sign-in

OpenID Connect via Authlib: authorization-code flow with PKCE, `state`, `nonce`,
and ID-token signature validation against Google's published keys.

It stays off unless you configure `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`,
and when it's off the buttons don't render at all. Nobody self-hosting a book
club should be made to create a Google Cloud project.

Three decisions worth stating, because they're the ones that go wrong elsewhere:

- **Accounts are matched on Google's subject identifier, never on email.** People
  change their Google address, and addresses get recycled. Matching on email
  would eventually let a new owner of an old address inherit someone else's clubs.
- **Linking is always explicit.** Signing in with Google never silently adopts an
  existing account, even when the email matches. If an account already holds that
  address, you're told, and you choose.
- **Disconnecting Google from an account that has no account secret generates one
  and shows it once**, rather than locking the owner out of their own clubs.

First-time visitors also pick their own username instead of inheriting whatever
their email address implies — usernames here are public and permanent.

## The security pass

**There was an authentication bypass, and it's fixed.**

Login identity lived in a cookie called `coverbound_user_id`, and its value was a
plain user id. Not signed, not encrypted — just the number. Anyone could open
devtools, change `coverbound_user_id=4` to `coverbound_user_id=1`, and become
that account.

Identity now lives in the `SECRET_KEY`-signed session cookie, which is `HttpOnly`,
`SameSite=Lax`, and `Secure` outside debug mode. **This is why everyone is logged
out once** — the old cookies are no longer accepted, deliberately.

Alongside that:

- The app **refuses to start** with `DEBUG=false` and no `SECRET_KEY`, rather than
  falling back to a hardcoded default that would make every deployment's cookies
  forgeable with the same string.
- `DEBUG` now ships as `false`. It drops the `Secure` flag from session cookies,
  which is right for local HTTP development and wrong everywhere else.
- **Club contents are members-only.** Book pages, discussions, reviews, meetings
  and the shelf now all require membership. Previously a club code — or a guessed
  book id, and ids are sequential — was enough to read a club's conversations.
  `is_public` now controls *listing* in the directory, not readability.

## A test suite

3.0.0 ships **95 tests**: authentication and session integrity, the privacy
rules, admin-gated selection and the draw/assign handshake, feedback rate
limiting, and account deletion across every table that references a member.

They run in about fifteen seconds and block all outbound network calls, so
they're deterministic and work offline. A test that quietly reaches Open Library
fails loudly instead of hanging.

The suite earned its keep immediately: it caught the release script silently
stripping a licence header from `version.py` on every version bump, and it
surfaced that deleting an account had *never worked* for anyone who had marked a
book as finished — the cascade tried to null out a non-nullable foreign key and
the whole delete failed. Both are fixed.

## Also fixed

- **Deleting an account works.** It previously failed with a `NOT NULL constraint`
  error for any account with a finished book. Every table referencing a member now
  cascades from the model, rather than from a hand-maintained list that new tables
  kept falling out of.
- **Leaving a club no longer strands it without an admin**, and meetings survive
  the departure of their host instead of blocking the delete.
- **Static assets stopped going stale.** They were served without `Cache-Control`,
  so browsers fell back to heuristic freshness and could reuse a cached stylesheet
  for days. Rebuilding shipped CSS the browser never asked for, which made
  front-end changes look like they simply hadn't happened.
- Dependencies upgraded to clear 27 known CVEs — FastAPI, Starlette,
  python-multipart, Jinja2, requests and others.

## Licensing

Coverbound is **GPL-3.0-or-later**. It always was, but the repository didn't say
so consistently: a GPL `LICENSE` file, a README that said "TBD", and a
`package.json` that declared nothing. All three now agree, and every first-party
source file carries an SPDX header.

The footer shows the running version, the licence, and a link to the source. If
you run a modified Coverbound, point `SOURCE_URL` at your own repository — under
the GPL, the people using your instance are entitled to *your* source, not
upstream's.

---

## Upgrading

Back up your database first. Then:

```bash
DATABASE_URL=sqlite:///./data/coverbound.db alembic upgrade head
```

Three migrations run: club feature flags and book metadata (`004`), Google
sign-in columns (`005`), and nullable meeting hosts (`006`).

**Four things to know before you pull:**

1. **Everyone is logged out once.** The old identity cookie is no longer accepted.
   Members log in again; nothing else is affected.
2. **`coverbound.env` is no longer tracked in git.** The template is now
   `coverbound.env.example`, and `make init` creates the real file and generates a
   `SECRET_KEY`. Your existing file is left alone — but it's now gitignored, so a
   `git pull` won't clobber it.
3. **Club contents are members-only.** If you were sharing a club URL with
   non-members, they'll now be asked to join instead.
4. **Choosing the next book is admin-only.** Suggesting, voting and vetoing are
   unchanged.

Feature-flag defaults are chosen so nothing changes behaviour on upgrade: reading
progress and year-in-books are **on**, public directory listing and live vote
counts are **off**. An upgrade will not publish an existing club or reveal running
vote tallies.

Full details are in [CHANGELOG.md](../../CHANGELOG.md).

---

*Coverbound is free software under the GNU GPL v3 or later. Issues and patches
welcome.*
