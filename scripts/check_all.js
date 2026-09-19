// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Domatron22
/**
 * Dev-only full-app sweep.
 *
 * Loads every screen at each breakpoint in both themes and reports HTTP
 * errors, horizontal overflow and JS errors; then exercises the interactive
 * flows (voting, the random reel, feedback, progress) and the reduced-motion
 * and focus-visible behaviour.
 *
 *   node scripts/check_all.js [--shots DIR]
 *
 * Requires Playwright, which is deliberately NOT in package.json: the
 * Dockerfile's `npm ci` installs devDependencies, so adding it there would
 * pull ~3MB into every production image build for a local-only tool.
 * Install it on demand:
 *
 *   npm install --no-save playwright && npx playwright install chromium
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const BASE = process.env.BASE || 'http://127.0.0.1:8009';
const arg = (f, d) => { const i = process.argv.indexOf(f); return i === -1 ? d : process.argv[i + 1]; };
const shotsDir = arg('--shots', null);

const SCREENS = [
  ['landing', '/', { anon: true }],
  ['home', '/'],
  ['browse', '/clubs/browse', { anon: true }],
  ['browse-search', '/clubs/browse?q=night'],
  ['club', '/clubs/MOONLIT'],
  ['create', '/clubs/create'],
  ['join', '/clubs/join'],
  ['admin', '/clubs/MOONLIT/admin'],
  ['welcome', '/clubs/MOONLIT/welcome'],
  ['shelf', '/clubs/MOONLIT/shelf'],
  ['book', '/books/1'],
  ['select-voting', '/clubs/MOONLIT/select'],
  ['select-random', '/clubs/WARPX/select'],
  ['search', '/books/search?club_code=MOONLIT&q=Circe'],
  ['recap-club', '/clubs/MOONLIT/recap'],
  ['recap-personal', '/profile/recap'],
  ['meetings', '/meetings/club/MOONLIT'],
  ['mcreate', '/meetings/create/MOONLIT'],
  ['msetup', '/meetings/setup/MOONLIT'],
  ['rsvp', '/meetings/1/rsvp'],
  ['disclist', '/discussions/book/1'],
  ['thread', '/discussions/1'],
  ['ratings', '/ratings/book/1'],
  ['profile', '/profile/you'],
  ['settings', '/profile/settings'],
  ['login', '/auth/login', { anon: true }],
  ['register', '/auth/register', { anon: true }],
];

const results = [];
const ck = (n, v, d = '') => results.push({ n, v, d });

// Identity moved out of a hand-settable cookie and into the signed session, so
// the harness has to log in the way a person does. `context.request` shares the
// context's cookie jar, so the session cookie it receives applies to every page
// opened from that context afterwards.
async function login(context, username = 'you', secret = 'demo-secret-you') {
  const res = await context.request.post(BASE + '/auth/login', {
    form: { username, account_secret: secret },
    maxRedirects: 0,
  });
  if (res.status() !== 303) {
    throw new Error(
      `Login as "${username}" failed (${res.status()}). Reseed with ` +
      '`.venv/bin/python scripts/seed_demo.py --reset` so the demo accounts exist.'
    );
  }
}

async function makeContext(browser, { width, theme, anon = false, reduced = false }) {
  const context = await browser.newContext({
    viewport: { width, height: 900 },
    deviceScaleFactor: shotsDir ? 2 : 1,
    reducedMotion: reduced ? 'reduce' : 'no-preference',
  });
  await context.addCookies([{ name: 'theme', value: theme, url: BASE }]);
  if (!anon) await login(context);
  return context;
}

(async () => {
  if (shotsDir) fs.mkdirSync(shotsDir, { recursive: true });
  const browser = await chromium.launch();

  // ---- render sweep ----
  for (const theme of ['light', 'dark']) {
    for (const width of [375, 768, 1280]) {
      const problems = [];
      for (const [name, url, opts = {}] of SCREENS) {
        const context = await makeContext(browser, { width, theme, anon: opts.anon });
        const page = await context.newPage();
        const errs = [];
        page.on('pageerror', (e) => errs.push(String(e)));
        const res = await page.goto(BASE + url, { waitUntil: 'networkidle' });
        await page.evaluate(() => document.fonts && document.fonts.ready);
        const overflow = await page.evaluate(() =>
          document.documentElement.scrollWidth - document.documentElement.clientWidth);
        if (res.status() >= 400) problems.push(`${name}:HTTP${res.status()}`);
        if (overflow > 0) problems.push(`${name}:overflow${overflow}px`);
        if (errs.length) problems.push(`${name}:js(${errs[0].slice(0, 40)})`);
        if (shotsDir && width === 1280) {
          await page.screenshot({ path: path.join(shotsDir, `${name}-${theme}.png`), fullPage: true });
        }
        await context.close();
      }
      ck(`${theme} @ ${width}px — ${SCREENS.length} screens`, problems.length === 0, problems.join(', '));
    }
  }

  // ---- flows ----
  const context = await makeContext(browser, { width: 1280, theme: 'light' });
  const page = await context.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(String(e)));

  // voting: hidden tallies, cast + retract
  await page.goto(BASE + '/clubs/MOONLIT/select', { waitUntil: 'networkidle' });
  const body = await page.locator('main').innerText();
  ck('voting: counts hidden when votes_visible off', body.includes('Vote counts are hidden'));
  ck('voting: no tallies rendered', !/\d+ votes?\n/.test(body));
  await page.locator('form[action$="/vote"] button').first().click();
  await page.waitForLoadState('networkidle');
  ck('voting: vote registers', (await page.locator('main').innerText()).includes('Voted'));
  await page.locator('form[action$="/vote"] button').first().click();
  await page.waitForLoadState('networkidle');
  ck('voting: vote retracts', !(await page.locator('main').innerText()).includes('Voted'));

  // random reel. The flow assigns a book, so a re-run against an unseeded
  // database would find the spin button already disabled — reseed first:
  //   .venv/bin/python scripts/seed_demo.py --reset
  await page.goto(BASE + '/clubs/WARPX/select', { waitUntil: 'networkidle' });
  if (await page.locator('#spin-btn').isDisabled()) {
    ck('reel: SKIPPED — WARPX already has a book assigned', false,
       'reseed with scripts/seed_demo.py --reset and re-run');
  } else {
  ck('reel: ack modal starts hidden', await page.locator('#ack-modal').evaluate(e => e.hidden));
  ck('reel: strip built from candidates', (await page.locator('[data-reel-book]').count()) > 0);
  await page.click('#spin-btn');
  await page.waitForTimeout(300);
  ck('reel: button disabled while spinning', await page.locator('#spin-btn').isDisabled());
  ck('reel: shows deciding state', !(await page.locator('#spin-running').evaluate(e => e.hidden)));
  await page.waitForSelector('#ack-modal:not([hidden])', { timeout: 12000 });
  ck('reel: ack modal opens after spin', true);
  const ackTitle = await page.locator('#ack-title').innerText();
  ck('reel: modal names the pick', ackTitle.length > 0, ackTitle);
  const ackAction = await page.locator('#ack-form').getAttribute('action');
  ck('reel: acknowledge posts to assign', /^\/books\/\d+\/assign$/.test(ackAction), ackAction);

  // the spin must not have assigned anything yet
  const stillSuggested = await page.evaluate(async () => {
    const r = await fetch('/clubs/WARPX/select');
    return (await r.text()).includes('Spin the shelf');
  });
  ck('reel: spin alone does not assign', stillSuggested);

  // acknowledge → assigns, lands on club home
  await page.click('#ack-form button[type="submit"]');
  await page.waitForLoadState('networkidle');
  ck('reel: acknowledge lands on club home', page.url().endsWith('/clubs/WARPX'), page.url());
  // innerText applies text-transform, so the eyebrow reads uppercase here.
  ck('reel: book is now current',
    (await page.locator('main').innerText()).toLowerCase().includes('currently reading'));

  // second spin refused once a book is assigned
  await page.goto(BASE + '/clubs/WARPX/select', { waitUntil: 'networkidle' });
  const guarded = await page.evaluate(async () => {
    const r = await fetch('/books/spin/WARPX', { method: 'POST' });
    return r.status;
  });
  ck('reel: re-spin refused server-side', guarded === 409, `HTTP ${guarded}`);

  }

  // reading progress
  await page.goto(BASE + '/clubs/MOONLIT', { waitUntil: 'networkidle' });
  ck('progress: summary collapsed by default', await page.locator('#progress-list').evaluate(e => e.hidden));
  ck('progress: shows finished count', (await page.locator('#progress-toggle').innerText()).includes('of 5'));
  await page.click('#progress-toggle');
  ck('progress: expands to per-member bars', !(await page.locator('#progress-list').evaluate(e => e.hidden)));
  await page.fill('#my-page', '256');
  await page.locator('form[action$="/progress"] button[type="submit"]').click();
  await page.waitForLoadState('networkidle');
  ck('progress: page saves', (await page.locator('#my-page').inputValue()) === '256');

  // feedback end to end
  await page.click('#feedback-open');
  await page.fill('#fb-summary', 'Automated sweep check');
  await page.click('#feedback-submit');
  await page.waitForTimeout(600);
  ck('feedback: toast appears', !(await page.locator('#feedback-toast').evaluate(e => e.hidden)));
  ck('feedback: no ticket reference without a token',
    !(await page.locator('#feedback-toast-detail').innerText()).includes('#'));

  ck('no JS errors across flows', errs.length === 0, errs.join(' | '));
  await context.close();

  // ---- reduced motion ----
  const rmCtx = await makeContext(browser, { width: 1280, theme: 'light', reduced: true });
  const rm = await rmCtx.newPage();
  const rmBad = [];
  for (const [name, url, opts = {}] of SCREENS) {
    if (opts.anon) continue;
    await rm.goto(BASE + url, { waitUntil: 'networkidle' });
    const bad = await rm.evaluate(() => {
      const out = [];
      document.querySelectorAll('*').forEach((el) => {
        const cs = getComputedStyle(el);
        if (cs.animationName !== 'none' && (parseFloat(cs.animationDuration) || 0) > 0.05) out.push('anim');
        if (parseFloat(cs.opacity) === 0) out.push('invisible');
      });
      return [...new Set(out)];
    });
    if (bad.length) rmBad.push(`${name}:${bad.join('/')}`);
  }
  ck('reduced motion: nothing animating, nothing invisible', rmBad.length === 0, rmBad.join(', '));
  await rmCtx.close();

  // ---- focus ring ----
  const fCtx = await makeContext(browser, { width: 1280, theme: 'light' });
  const fp = await fCtx.newPage();
  await fp.goto(BASE + '/clubs/MOONLIT');
  await fp.keyboard.press('Tab');
  const ring = await fp.evaluate(() => {
    const cs = getComputedStyle(document.activeElement);
    return `${cs.outlineWidth} ${cs.outlineStyle}`;
  });
  ck('focus-visible ring intact', ring === '2px solid', ring);
  await fCtx.close();

  await browser.close();
  results.forEach((r) => console.log(`${r.v ? '  ok ' : 'FAIL '} ${r.n}${r.d ? '  — ' + r.d : ''}`));
  const failed = results.filter((r) => !r.v).length;
  console.log(`\n${results.length - failed}/${results.length} passed`);
  process.exit(failed ? 1 : 0);
})();
