// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Domatron22
/**
 * Dev-only interaction check for the global shell.
 *
 * Drives the clubs switcher, avatar menu, theme toggle and feedback modal the
 * way a person would — including by keyboard — and captures each open state.
 *
 *   node scripts/check_shell.js [--out DIR] [--theme light|dark]
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
const arg = (f, d) => {
  const i = process.argv.indexOf(f);
  return i === -1 ? d : process.argv[i + 1];
};
const outDir = arg('--out', path.join(process.env.TMPDIR || '/tmp', 'coverbound-shots'));
const theme = arg('--theme', 'light');

const results = [];
const check = (name, pass, detail = '') =>
  results.push({ name, pass, detail });

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

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2 });
  await context.addCookies([{ name: 'theme', value: theme, url: BASE }]);
  await login(context);
  const page = await context.newPage();
  const jsErrors = [];
  page.on('pageerror', (e) => jsErrors.push(String(e)));
  await page.goto(BASE + '/clubs/MOONLIT', { waitUntil: 'networkidle' });

  const hidden = (sel) => page.locator(sel).evaluate((el) => el.hidden);
  const shot = async (n) => (await page.waitForTimeout(300), page.screenshot({ path: path.join(outDir, `shell-${theme}-${n}.png`) }));

  // --- overlays start closed ---
  check('feedback modal starts hidden', await hidden('#feedback-modal'));
  check('toast starts hidden', await hidden('#feedback-toast'));
  check('switcher panel starts hidden', await hidden('#clubs-switcher-panel'));

  // --- clubs switcher ---
  await page.click('#clubs-switcher-btn');
  check('switcher opens', !(await hidden('#clubs-switcher-panel')));
  check('switcher aria-expanded=true',
    (await page.getAttribute('#clubs-switcher-btn', 'aria-expanded')) === 'true');
  const clubRows = await page.locator(
    '#clubs-switcher-panel a[href^="/clubs/"]:not([href="/clubs/create"]):not([href="/clubs/join"])'
  ).count();
  check('switcher lists all 3 clubs', clubRows === 3, `saw ${clubRows}`);
  check('switcher has Create + Join',
    (await page.locator('#clubs-switcher-panel a[href="/clubs/create"]').count()) === 1 &&
    (await page.locator('#clubs-switcher-panel a[href="/clubs/join"]').count()) === 1);
  await shot('switcher');

  await page.keyboard.press('Escape');
  check('Escape closes switcher', await hidden('#clubs-switcher-panel'));

  await page.click('#clubs-switcher-btn');
  await page.click('body', { position: { x: 640, y: 700 } });
  check('outside click closes switcher', await hidden('#clubs-switcher-panel'));

  // --- avatar menu ---
  await page.click('#avatar-btn');
  check('avatar menu opens', !(await hidden('#avatar-panel')));
  check('avatar menu has sign out',
    (await page.locator('#avatar-panel form[action="/auth/logout"] button').count()) === 1);
  await shot('avatar');
  await page.keyboard.press('Escape');

  // --- opening one menu closes the other ---
  await page.click('#clubs-switcher-btn');
  await page.click('#avatar-btn');
  check('opening avatar closes switcher', await hidden('#clubs-switcher-panel'));
  await page.keyboard.press('Escape');

  // --- theme toggle ---
  const before = await page.evaluate(() => document.documentElement.classList.contains('dark'));
  await page.click('#theme-toggle');
  const after = await page.evaluate(() => document.documentElement.classList.contains('dark'));
  check('theme toggle flips .dark', before !== after);
  check('theme cookie persisted',
    (await context.cookies()).some((c) => c.name === 'theme' && c.value === (after ? 'dark' : 'light')));
  await page.click('#theme-toggle'); // back

  // --- feedback modal ---
  await page.click('#feedback-open');
  check('feedback modal opens', !(await hidden('#feedback-modal')));
  check('submit disabled while summary empty',
    await page.locator('#feedback-submit').isDisabled());
  check('focus lands in summary',
    (await page.evaluate(() => document.activeElement.id)) === 'fb-summary');
  check('default kind is Idea',
    await page.locator('#feedback-form input[value="idea"]').isChecked());
  check('context label names the screen',
    (await page.locator('#feedback-modal').innerText()).includes('the club home'));

  await page.fill('#fb-summary', 'The shelf marquee scrolls too fast to read');
  check('submit enables once summary filled',
    await page.locator('#feedback-submit').isEnabled());

  // pick a different kind, confirm the chip paints
  await page.locator('.cb-kind-chip', { hasText: 'Something broke' }).click();
  check('kind chip selects',
    await page.locator('#feedback-form input[value="bug"]').isChecked());
  const chipPainted = await page.locator('.cb-kind-chip', { hasText: 'Something broke' })
    .evaluate((el) => el.className.includes('bg-accent-soft'));
  check('selected chip shows accent-soft', chipPainted);
  await shot('feedback-modal');

  // tab focus stays inside the dialog
  for (let i = 0; i < 25; i++) await page.keyboard.press('Tab');
  const inDialog = await page.evaluate(() =>
    document.getElementById('feedback-modal').contains(document.activeElement));
  check('focus trapped inside modal', inDialog);

  // submit → modal closes, toast appears (endpoint may 404 until phase 4)
  await page.click('#feedback-submit');
  await page.waitForTimeout(400);
  check('modal closes on submit', await hidden('#feedback-modal'));
  check('toast appears on submit', !(await hidden('#feedback-toast')));
  await shot('toast');

  await page.click('#feedback-toast-dismiss');
  check('toast dismisses', await hidden('#feedback-toast'));

  // Escape closes the modal
  await page.click('#feedback-open');
  await page.keyboard.press('Escape');
  check('Escape closes modal', await hidden('#feedback-modal'));

  check('no JS errors', jsErrors.length === 0, jsErrors.join(' | '));

  await browser.close();

  const failed = results.filter((r) => !r.pass);
  results.forEach((r) =>
    console.log(`${r.pass ? '  ok ' : 'FAIL '} ${r.name}${r.detail ? '  — ' + r.detail : ''}`));
  console.log(`\n${results.length - failed.length}/${results.length} passed (${theme})`);
  process.exit(failed.length ? 1 : 0);
})();
