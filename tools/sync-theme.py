#!/usr/bin/env python3
"""Regenerate the site token mapping in Power-YoungCoder.user.styl.

The revamped OJ funnels component colours through CSS custom properties.  The
userstyle forces its own palette, so it remaps the neutral tokens from snapshots
collected with tools/collect-site-tokens.js:

  1. tools/snapshots/*.json       one file per page type, see the collector
  2. python tools/sync-theme.py   rewrites the two generated sections in place

Generated sections (do not edit by hand):
  * site-token-values-light / site-token-values-dark   (grouped property remap)
"""
import glob
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STYL = os.path.join(ROOT, 'Power-YoungCoder.user.styl')
SNAPSHOTS = os.path.join(ROOT, 'tools', 'snapshots')

HEX = re.compile(r'^#([0-9a-fA-F]{3,8})$')
BOUND = re.compile(r'^var\(--yc-dark-([a-z]+)\)$')
RGB = re.compile(r'rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)')
# third-party design systems follow their own theme switch
FOREIGN_NAME = re.compile(r'^--(mantine|el|vscode|monaco)')
FOREIGN_VALUE = re.compile(r'var\(--(mantine|el|vscode|monaco)')
TINT_LIMIT = 0.04
TINT_LIMIT_BY_ROLE = {'text': 0.13, 'muted': 0.13, 'line': 0.12}

# role -> palette symbol in the userstyle
ROLE = {
    'page': 'canvas_color',
    'surface': 'surface_color',
    'raised': 'raised_color',
    'inset': 'inset_color',
    'alternate': 'alternate_color',
    'hover': 'hover_color',
    'line': 'separator_color',
    'text': 'primary_text_color',
    'muted': 'secondary_text_color',
}
DARK_PALETTE_ROLE = {
    'page': 'page', 'surface': 'surface', 'raised': 'raised', 'inset': 'inset',
    'alternate': 'alternate', 'hover': 'hover', 'line': 'line',
    'text': 'text', 'muted': 'muted',
}
SEGMENT_ROLE = {
    'bg': 'surface', 'surface': 'surface', 'panel': 'surface', 'card': 'surface',
    'box': 'surface', 'board': 'surface', 'page': 'page', 'base': 'surface',
    'fill': 'surface', 'container': 'surface', 'canvas': 'page',
    'soft': 'raised', 'raised': 'raised', 'head': 'raised', 'header': 'raised',
    'option': 'raised', 'badge': 'raised', 'pill': 'raised', 'chip': 'raised',
    'tag': 'raised', 'alternate': 'alternate', 'alt': 'alternate', 'row': 'alternate',
    'input': 'inset', 'inset': 'inset', 'code': 'inset', 'inline': 'inset',
    'well': 'inset', 'track': 'inset',
    'hover': 'hover', 'active': 'hover', 'selected': 'hover', 'focus': 'hover',
    'divider': 'line', 'separator': 'line', 'scroll': 'line',
    'ink': 'text', 'text': 'text', 'title': 'text', 'heading': 'text', 'fg': 'text',
    'label': 'text',
    'meta': 'muted', 'placeholder': 'muted', 'hint': 'muted', 'dim': 'muted',
    'note': 'muted',
}


def hex_rgb(value):
    m = HEX.match(value.strip())
    if not m:
        m2 = RGB.search(value)
        if m2:
            return tuple(float(m2.group(i)) / 255 for i in (1, 2, 3))
        return None
    s = m.group(1)
    if len(s) == 3:
        s = ''.join(c * 2 for c in s)
    if len(s) == 8:
        s = s[:6]
    return tuple(int(s[i:i + 2], 16) / 255 for i in (0, 2, 4))


def luminance(rgb):
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def tint_of(value):
    rgb = hex_rgb(value)
    if rgb is None:
        return None
    return max(rgb) - min(rgb)


NAME_ROLES = [
    ('line', ('line', 'border', 'divider', 'separator', 'scroll')),
    ('inset', ('input', 'inset', 'canvas', 'code', 'inline', 'well', 'track', 'alt')),
    ('raised', ('soft', 'raised', 'head', 'option', 'tag', 'badge', 'pill', 'chip')),
    ('hover', ('hover', 'active', 'selected', 'focus')),
    ('text', ('ink', 'text', 'title', 'heading', 'fg', 'label')),
    ('muted', ('muted', 'meta', 'placeholder', 'hint', 'dim', 'note')),
    ('surface', ('bg', 'surface', 'panel', 'card', 'box', 'board', 'page', 'base',
                 'fill', 'container', 'canvas')),
]


def role_of(token):
    # a token's trailing word decides its role, so --yc-callout-note-bg is a
    # surface (bg) and --home-tile-hover-border is a line, not a hover colour
    for segment in reversed(token.lstrip('-').split('-')):
        if segment in SEGMENT_ROLE:
            return SEGMENT_ROLE[segment]
    # fall back to a substring match for names without a role-like tail
    name = token.lower()
    for role, keys in NAME_ROLES:
        for key in keys:
            if key in name:
                return role
    return None


def load_snapshots():
    light, dark = defaultdict(set), defaultdict(set)
    files = sorted(glob.glob(os.path.join(SNAPSHOTS, '*.json')))
    if not files:
        sys.exit(f'no snapshots in {SNAPSHOTS}; run tools/collect-site-tokens.js first')
    for path in files:
        data = json.load(open(path, encoding='utf-8'))
        for target, key in ((light, 'light'), (dark, 'dark')):
            for token, modes in data.get(key, {}).items():
                values = modes.get(key)
                for value in ([values] if isinstance(values, str) else (values or [])):
                    if value:
                        target[token].add(value)
    print(f'snapshots: {len(files)} pages, {len(light)} light / {len(dark)} dark tokens, '
          'legacy hard-coded palette skipped')
    return ({k: sorted(v) for k, v in light.items()},
            {k: sorted(v) for k, v in dark.items()})


def token_expr(token, mode, light, dark):
    """Stylus value expression for one token in one mode (None = leave alone)."""
    values = (dark if mode == 'dark' else light).get(token)
    if not values:
        if mode != 'dark':
            return None  # light mode: the site already ships a light value
        light_values = light.get(token)
        if not light_values or len(light_values) > 1:
            return None
        tint, role = tint_of(light_values[0]), role_of(token)
        if tint is not None and tint <= TINT_LIMIT_BY_ROLE.get(role, TINT_LIMIT) and role:
            return ROLE[role]
        return None
    bound = [v for v in values if BOUND.match(v)]
    if bound:
        value = bound[0]
    elif len(values) > 1:
        return None  # contextual token (per difficulty, per palette, ...)
    else:
        value = values[0]
    match = BOUND.match(value)
    if match:
        return ROLE[DARK_PALETTE_ROLE.get(match.group(1), 'surface')]
    tint, role = tint_of(value), role_of(token)
    if tint is not None and tint <= TINT_LIMIT_BY_ROLE.get(role, TINT_LIMIT) and role:
        return ROLE[role]
    if value.startswith('var('):
        return None
    return '*' + value  # keep the site's own colour (tinted surface, accent, ...)


def build_token_block(mode, light, dark):
    pairs = []
    kept = 0
    for token in sorted(set(light) | set(dark)):
        if token.startswith('--yc-dark-') or FOREIGN_NAME.match(token):
            continue
        values = light.get(token, []) + dark.get(token, [])
        if any(FOREIGN_VALUE.search(v) for v in values):
            continue
        expr = token_expr(token, mode, light, dark)
        if expr is None:
            continue
        if expr.startswith('*'):
            kept += 1
            expr = expr[1:]
        pairs.append((token, expr))
    return pairs, kept


def compact_token_lines(pairs):
    """Group equal values into Stylus mixin calls while keeping every site token."""
    groups = {}
    for token, value in pairs:
        groups.setdefault(value, []).append(token)

    lines = []
    for value, tokens in groups.items():
        names = ' '.join(f"'{token}'" for token in tokens)
        lines.append(f'        set-theme-tokens({names}, {value})')
    return lines


def remove_mixin(styl, name):
    marker = f'    {name}()\n'
    start = styl.find(marker)
    if start < 0:
        return styl
    body_start = start + len(marker)
    match = re.search(r'(?m)^    \S', styl[body_start:])
    if match is None:
        sys.exit(f'cannot find end of {name}')
    return styl[:start] + styl[body_start + match.start():]


def remove_token_helper(styl):
    marker = '    set-theme-tokens(tokens, value)\n'
    start = styl.find(marker)
    if start < 0:
        return styl
    comment = '    // 同值 token 合并成一条 mixin 调用，编译后的变量与逐条声明完全一致。\n'
    comment_start = styl.rfind(comment, 0, start)
    if comment_start >= 0:
        start = comment_start
    end = styl.find('\n\n', start)
    if end < 0:
        sys.exit('cannot find end of set-theme-tokens helper')
    return styl[:start] + styl[end + 2:]


def splice(styl, token_lines):
    # ---- token values (two mixins, called by the rule below the anchor)
    for name in ('light', 'dark'):
        styl = remove_mixin(styl, f'site-token-values-{name}')
    styl = remove_token_helper(styl)
    mixin = (
        '    // 同值 token 合并成一条 mixin 调用，编译后的变量与逐条声明完全一致。\n'
        '    set-theme-tokens(tokens, value)\n'
        '        for token in tokens\n'
        '            {token}: value !important\n\n'
    )
    for mode, lines in token_lines.items():
        mixin += f'    site-token-values-{mode}()\n' + '\n'.join(lines) + '\n'
    anchor = '    html, body, body *\n'
    if styl.count(anchor) != 1:
        sys.exit('token anchor not found - was the stylesheet edited?')
    styl = styl.replace(anchor, mixin + anchor)

    # the splice is idempotent, so a leftover copy means the anchors moved
    for name in ('light', 'dark'):
        if len(re.findall(rf'^    site-token-values-{name}\(\)$', styl, re.M)) != 1:
            sys.exit(f'generated block for {name} appears more than once')
    return styl


def main():
    light, dark = load_snapshots()
    token_lines = {}
    for mode in ('light', 'dark'):
        pairs, kept = build_token_block(mode, light, dark)
        token_lines[mode] = compact_token_lines(pairs)
        print(f'  {mode}: {len(pairs)} token values in '
              f'{len(token_lines[mode])} grouped calls ({kept} keep the site colour)')
    styl = open(STYL, encoding='utf-8').read().replace('\r\n', '\n')
    styl = splice(styl, token_lines)
    open(STYL, 'w', encoding='utf-8', newline='\r\n').write(styl)
    print(f'updated {os.path.relpath(STYL, ROOT)}')


if __name__ == '__main__':
    main()
