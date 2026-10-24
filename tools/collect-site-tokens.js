// Collect the site's colour tokens from a live page (paste into DevTools).
//
// The revamped OJ injects part of its component CSS with JavaScript, so a plain
// HTTP fetch is not enough - open the page while logged in, paste this file's
// content into the console, and it downloads one JSON snapshot.  Run it on each
// page type (home, problem list, problem, homework, contest, record, ranking,
// profile, discussion, blog, course, settings, ...) and drop the downloaded
// files into tools/snapshots/ before running tools/sync-theme.py.
//
// It records custom properties in light and dark variants, including rules
// gated by @media (prefers-color-scheme: dark). Legacy hard-coded component
// colours are no longer collected or generated.
(() => {
  const COLOUR = /^(#[0-9a-fA-F]{3,8}|rgba?\(|hsla?\(|transparent$|currentColor$|var\(--[a-zA-Z0-9-]+\)$)/i;
  const NOT_COLOUR = /(px|rem|em|%|vh|vw|deg|s$|ms$)/i;
  const isDark = (sel, media) =>
    /theme--dark|data-theme="dark"|color-scheme="dark"|data-mantine-color-scheme="dark"/.test(sel)
    || /prefers-color-scheme:\s*dark/i.test(media || '');
  const light = {};
  const dark = {};
  let scanned = 0;

  const addTokens = (map, isDarkRule) => (body) => {
    for (const m of body.matchAll(/(--[a-zA-Z0-9-]+)\s*:\s*([^;]+)/g)) {
      const token = m[1];
      const value = m[2].trim().replace(/\s*!important$/, '');
      if (!COLOUR.test(value) || NOT_COLOUR.test(value)) continue;
      if (!map[token]) map[token] = {};
      const slot = isDarkRule ? 'dark' : 'light';
      const seen = map[token][slot] || [];
      if (!seen.includes(value)) map[token][slot] = seen.concat(value);
    }
  };

  for (const sheet of Array.from(document.styleSheets)) {
    let rules;
    try { rules = sheet.cssRules; } catch (e) { continue; }
    const walk = (list, media) => {
      for (const rule of Array.from(list)) {
        if (rule.cssRules && rule.cssRules.length) {
          walk(rule.cssRules, rule.conditionText || media);
          continue;
        }
        scanned++;
        const css = rule.cssText || '';
        const brace = css.indexOf('{');
        if (brace < 0) continue;
        const selector = css.slice(0, brace);
        const body = css.slice(brace + 1);
        const darkRule = isDark(selector, media);
        addTokens(darkRule ? dark : light, darkRule)(body);
      }
    };
    walk(rules, sheet.media && sheet.media.mediaText);
  }

  const payload = { url: location.pathname, scanned, light, dark };
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(payload)], { type: 'application/json' }));
  a.download = 'yc-' + (location.pathname.replace(/[^a-z0-9]/gi, '_') || 'home') + '.json';
  document.body.appendChild(a);
  a.click();
  a.remove();
  return `downloaded ${a.download} (light=${Object.keys(light).length} dark=${Object.keys(dark).length} rules=${scanned})`;
})();
