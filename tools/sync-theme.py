#!/usr/bin/env python3
"""Regenerate the site-specific blocks of Power-YoungCoder.user.styl.

The revamped OJ funnels component colours through CSS custom properties and
keeps a second, hard-coded palette for its own dark mode.  The userstyle forces
its own palette, so it has to write both of them itself.  This script derives
those blocks from snapshots collected with tools/collect-site-tokens.js:

  1. tools/snapshots/*.json       one file per page type, see the collector
  2. python tools/sync-theme.py   rewrites the two generated sections in place

Generated sections (do not edit by hand):
  * site-token-values-light / site-token-values-dark   (property remap)
  * the block between @site-dark-rules-begin / -end    (hard-coded colours)
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
DARK_PARTS = [
    r':is\([^()]*theme--dark[^()]*\)',
    r':is\([^()]*data-theme="dark"[^()]*\)',
    r'\.theme--dark',
    r'\[data-theme="dark"\]',
]
# containers the userstyle turns into acrylic cards itself (see the stylesheet):
# the site's own dark background is skipped for these, our acrylic layer shows
CARD_CONTAINERS = [
    'yc-domain-bulletin-card', 'yc-home-card', 'yc-hw-list-panel', 'yc-hw-intro',
    'yc-profile-shell', 'yc-profile-content', 'yc-problem-overview', 'yc-problem-statement',
    'yc-contest-panel', 'yc-side-navigation', 'yc-homework-sidebar', 'yc-contest-sidebar',
    'yc-hw-overview', 'yc-homework-description',
]
SKIP_SELECTOR = re.compile(r'^(?::root|html\b|body\b|#panel$)'
                          r'|\.button\b|\.textbox\b|^(?:input|select|textarea)\b')
PROTECTED_BG = re.compile(r'\.section\b|\.data-table\b'
                          r'|' + '|'.join(re.escape(c) for c in CARD_CONTAINERS))


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
    light, dark, hard = defaultdict(set), defaultdict(set), {}
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
        for item in data.get('darkHard', []):
            base = re.sub(r'\s+', ' ', item['sel']).strip()
            for part in DARK_PARTS:
                base = re.sub(part, '', base)
            base = re.sub(r'\s*,\s*', ', ', base)
            base = re.sub(r'\s+', ' ', base).strip()
            base = re.sub(r'^[>+~]\s*', '', base)
            if not base or SKIP_SELECTOR.search(base):
                continue
            decls = [d.replace(' !important', '').strip() for d in item['decls']]
            if decls:
                hard.setdefault(base, decls)
    print(f'snapshots: {len(files)} pages, {len(light)} light / {len(dark)} dark tokens, '
          f'{len(hard)} hard-coded dark rules')
    return ({k: sorted(v) for k, v in light.items()},
            {k: sorted(v) for k, v in dark.items()}, hard)


def palette_value(prop, value):
    """Our palette symbol for a neutral colour, else None (keep the site's)."""
    rgb = hex_rgb(value)
    if rgb is None or max(rgb) - min(rgb) > TINT_LIMIT:
        return None
    lum = luminance(rgb)
    if prop.startswith(('background', 'fill')):
        return 'surface_color' if lum < 0.16 else 'raised_color'
    if prop.startswith(('border', 'outline')):
        return 'separator_color'
    if prop == 'color':
        return 'primary_text_color' if lum > 0.45 else 'secondary_text_color'
    return None


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
    lines = []
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
        lines.append(f'        {token}: {expr} !important')
    return lines, kept


def build_dark_rules(hard):
    lines = []
    for base, decls in sorted(hard.items()):
        kept = []
        for decl in decls:
            prop, _, value = decl.partition(':')
            prop, value = prop.strip(), value.strip()
            if prop in ('background', 'background-color') and PROTECTED_BG.search(base):
                continue  # the userstyle paints those itself (acrylic layer)
            if re.search(r'gradient', value):
                kept.append(f'{prop} {value}')
                continue
            mapped = palette_value(prop, value)
            if mapped and prop.startswith('background'):
                alpha = RGB.search(value)
                if alpha and alpha.group(4) is not None and float(alpha.group(4)) < 1:
                    kept.append(f'{prop} rgba({mapped}, {alpha.group(4)})')
                else:
                    kept.append(f'{prop} {mapped}')
            elif mapped:
                kept.append(f'{prop} {mapped}')
            else:
                kept.append(f'{prop} {value}')
        if kept:
            lines.append(f'    {base}')
            lines.extend(f'        {decl} !important' for decl in kept)
    return lines


def splice(styl, token_lines, rule_lines):
    # ---- token values (two mixins, called by the rule below the anchor)
    styl = re.sub(r'^    site-token-values-(?:light|dark)\(\)\n(?:        --.*\n)+', '', styl, flags=re.M)
    mixin = ''
    for mode, lines in token_lines.items():
        mixin += f'    site-token-values-{mode}()\n' + '\n'.join(lines) + '\n'
    anchor = '    html, body, body *\n'
    if styl.count(anchor) != 1:
        sys.exit('token anchor not found - was the stylesheet edited?')
    styl = styl.replace(anchor, mixin + anchor)

    # ---- hard-coded dark rules
    body = '\n'.join('    ' + line if line.strip() else line for line in rule_lines)
    section = (
        '    //! 站点组件的硬编码颜色 -----------------------------------------\n'
        '\n'
        '    // 站点另有一批新版组件没有走 CSS 变量，而是自己写死了浅色值，再在深色\n'
        '    // 模式下换另一套写死的深色值。脚本不依赖站点的主题开关，所以这里把站点\n'
        '    // 深色模式那一套直接写进来：中性色映射到本主题调色板，状态色与强调色沿用\n'
        '    // 站点取值。站点改版后可以用仓库 tools 目录里的脚本重新生成这一段。\n'
        '    if dark-mode\n'
        '        // @site-dark-rules-begin\n'
        f'{body}\n'
        '        // @site-dark-rules-end\n'
        '\n'
    )
    marker = re.compile(r'    //! 站点组件的硬编码颜色.*?        // @site-dark-rules-end\n\n', re.S)
    if marker.search(styl):
        styl = marker.sub(section, styl, count=1)
    else:
        top = '    //! 顶栏 -----------------------------------------------------------\n'
        if styl.count(top) != 1:
            sys.exit('top-bar anchor not found - was the stylesheet edited?')
        styl = styl.replace(top, section + top)

    # the splice is idempotent, so a leftover copy means the anchors moved
    for name in ('light', 'dark'):
        if len(re.findall(rf'^    site-token-values-{name}\(\)$', styl, re.M)) != 1:
            sys.exit(f'generated block for {name} appears more than once')
    if styl.count('// @site-dark-rules-begin') != 1:
        sys.exit('hard-coded dark rules block is not unique')
    return styl


def main():
    light, dark, hard = load_snapshots()
    token_lines = {}
    for mode in ('light', 'dark'):
        lines, kept = build_token_block(mode, light, dark)
        token_lines[mode] = lines
        print(f'  {mode}: {len(lines)} token values ({kept} keep the site colour)')
    rule_lines = build_dark_rules(hard)
    print(f'  hard-coded dark rules: {len(rule_lines)} lines')
    styl = open(STYL, encoding='utf-8').read().replace('\r\n', '\n')
    styl = splice(styl, token_lines, rule_lines)
    open(STYL, 'w', encoding='utf-8', newline='\r\n').write(styl)
    print(f'updated {os.path.relpath(STYL, ROOT)}')


if __name__ == '__main__':
    main()
