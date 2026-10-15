# Coverbound 3.0.1 — series titles, join requests, and a recap that waits

*15 October 2026*

A small release built from what members reported after 3.0.0: one bug in book
search, one gap in the public directory, and a recap that turned up too early.

---

## Every book in a series has its own name again

Searching for a series could return a column of identical results. Every book in
Travis Bagwell's *Awaken Online* came back titled just "Awaken Online", so there
was no telling which one you were adding.

The cause was in how Open Library catalogues series: the series name goes in the
title, and the book's own name in a subtitle we weren't asking for. Search now
fetches the subtitle and shows the full title — *Awaken Online: Hellion*,
*Awaken Online: Inferno*.

Open Library has also merged several of these books into a single record with no
subtitle at all. For that one, Coverbound now takes the title and cover from the
edition that best matched your search, so "awaken online catharsis" gives you
*Catharsis* with the *Catharsis* cover rather than a mismatched pair.

## Public clubs can be joined without a code

3.0.0 added a directory of clubs that choose to be listed. But joining one still
needed the club's code, and the directory, rightly, never shows it. Finding a
club you liked ended at "ask the organiser", with no way to reach them.

Listed clubs now have **Request to join**. You pick the name you'll go by in
that club and send the request; it waits until one of the club's admins approves
it. Admins see who is asking under **Club admin → Asking to join**, and a badge on
the club page shows how many are waiting. Declining simply clears the request,
so someone can ask again later.

Codes work exactly as before: a code admits you at once, and using one clears
any request you had pending.

## The year in books waits for the end of the year

The year-in-books recap appeared as soon as anyone finished a book, which turned
a look back into a running tally from February onwards.

A year's recap now opens on **December 1st**, and the home and club pages only
promote it during December. After that it doesn't go away: every past year is
linked from your profile, and the club's past years from its shelf.

---

## Upgrading

One migration, adding the `join_requests` table (`007`):

```bash
DATABASE_URL=sqlite:///./data/coverbound.db alembic upgrade head
```

Nothing changes behaviour on upgrade apart from the recap timing above. The
suite grows from 95 tests to 120. Full details are in
[CHANGELOG.md](../../CHANGELOG.md).

---

*Coverbound is free software under the GNU GPL v3 or later. Issues and patches
welcome.*
