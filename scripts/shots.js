// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Domatron22
/**
 * Dev-only screenshot harness for the UI overhaul.
 *
 * Captures a page at 375 / 768 / 1280 in both light and dark, so every screen
 * can be checked against the design at each breakpoint in one pass.
 *
 *   node scripts/shots.js <path> [--out DIR] [--name NAME]
 *                                [--widths 375,768,1280] [--themes light,dark]
 *                                [--user 1] [--full] [--reduced-motion]
 *
 * Requires the dev server on BASE (default http://127.0.0.1:8009) and
 * `npm install --no-save playwright`.
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const BASE = process.env.BASE || 'http://127.0.0.1:8009';

function arg(flag, fallback) {
  const i = process.argv.indexOf(flag);
  return i === -1 ? fallback : process.argv[i + 1];
}
const has = (flag) => process.argv.includes(flag);

const target = process.argv[2];
if (!target || target.startsWith('--')) {
  console.error('usage: node scripts/shots.js <path> [options]');
  process.exit(1);
}

const outDir = arg('--out', path.join(process.env.TMPDIR || '/tmp', 'coverbound-shots'));
const name = arg('--name', target.replace(/^\/|\/$/g, '').replace(/\W+/g, '-') || 'home');
const widths = arg('--widths', '375,768,1280').split(',').map(Number);
const themes = arg('--themes', 'light,dark').split(',');
// Which demo account to view as. Logging in needs the username, not an id —
// see login() below; secrets are `demo-secret-<username>` from seed_demo.py.
const asUser = arg('--user', 'you');
const fullPage = has('--full');

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
  const written = [];

  for (const theme of themes) {
    for (const width of widths) {
      const context = await browser.newContext({
        viewport: { width, height: Math.round(width * 0.78) + 320 },
        deviceScaleFactor: 2,
        reducedMotion: has('--reduced-motion') ? 'reduce' : 'no-preference',
      });
      // The app reads `theme` from a cookie and stamps `.dark` on <html>
      // before first paint. Login is a real form POST — see login() above.
      await context.addCookies([{ name: 'theme', value: theme, url: BASE }]);
      await login(context, asUser, `demo-secret-${asUser}`);

      const page = await context.newPage();
      const errors = [];
      page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
      page.on('pageerror', (e) => errors.push(String(e)));

      const res = await page.goto(BASE + target, { waitUntil: 'networkidle' });
      // Let webfonts settle so the serif headings aren't captured mid-swap.
      await page.evaluate(() => document.fonts && document.fonts.ready);
      await page.waitForTimeout(350);

      const overflow = await page.evaluate(() =>
        document.documentElement.scrollWidth - document.documentElement.clientWidth);

      const file = path.join(outDir, `${name}-${theme}-${width}.png`);
      await page.screenshot({ path: file, fullPage });
      written.push(file);

      const flags = [];
      if (res && res.status() >= 400) flags.push(`HTTP ${res.status()}`);
      if (overflow > 0) flags.push(`h-overflow ${overflow}px`);
      if (errors.length) flags.push(`js: ${errors.slice(0, 2).join(' | ')}`);
      console.log(`${theme.padEnd(5)} ${String(width).padStart(4)}  ${path.basename(file)}` +
        (flags.length ? `   ⚠ ${flags.join('; ')}` : ''));

      await context.close();
    }
  }

  await browser.close();
  console.log(`\n${written.length} shots → ${outDir}`);
})();
