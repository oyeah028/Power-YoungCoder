// ==UserScript==
// @name         Power-YoungCoder · 复制题目为 Markdown
// @name:zh-CN   Power-YoungCoder · 复制题目为 Markdown
// @namespace    https://github.com/oyeah028/Power-YoungCoder
// @version      1.0.0
// @description  在 YCOJ / Hydro 题目页的「题目描述」卡片右上角加一个「复制为 Markdown」按钮，把整道题转成 Markdown 复制到剪贴板。与 Power-YoungCoder 主题配色一致，也可以不装主题单独使用。
// @author       oyeah(deepseek二开)
// @license      CC-BY-NC-SA-4.0
// @match        https://youngcoder.cn/*
// @match        https://*.youngcoder.cn/*
// @match        https://hydro.ac/*
// @match        https://*.hydro.ac/*
// @run-at       document-idle
// @grant        none
// ==/UserScript==

/*
 * 为什么是 userscript 而不是 Stylus：
 * Stylus（用户样式）只能注入 CSS，没有任何执行 JS 的通道，做不出「点一下就写剪贴板」的按钮。
 * 所以按钮本身放在这里，样式仍然跟主题走同一套中性色（半透明 + 描边），亮/暗模式下都不违和。
 *
 * 转换目标：题目页上「题目描述」所在的内容区，以及它后面同级的输入格式 / 输出格式 / 样例 / 提示……
 * 每个区域的小标题会变成 `## 标题`，页面标题变成 `# 标题`。
 * 站点改版后如果按钮没出现，打开控制台看 `[yc-md]` 开头的日志，那里会打印它找到了什么容器。
 */

(function () {
  'use strict';

  const BTN_ATTR = 'data-yc-md-copy';
  const BTN_CLASS = 'yc-md-copy';
  const LOG_PREFIX = '[yc-md]';

  // 只有题目详情页需要按钮；题目列表 / 提交记录页不注入。
  function isProblemPage() {
    const p = location.pathname;
    if (/\/p\/[^/]+/.test(p)) return true;          // /p/xxx
    if (/\/contest\/[^/]+\/p\//.test(p)) return true;
    if (/\/homework\/[^/]+\/p\//.test(p)) return true;
    if (/\/problem\//.test(p)) return true;
    return false;
  }

  /* ============================================================
   * 一、HTML → Markdown
   * 不依赖第三方库：站点正文只是普通的 markdown 渲染结果（标题/段落/列表/代码块/表格/公式）。
   * ============================================================ */

  const SKIP_TAGS = new Set([
    'script', 'style', 'noscript', 'svg', 'button', 'input', 'textarea', 'select',
    'iframe', 'canvas', 'video', 'audio', 'template', 'nav',
  ]);

  // 站点自己的工具条 / 装饰层，不属于正文
  const SKIP_SELECTORS = [
    '[' + BTN_ATTR + ']', '.yc-md-copy', '.section__tools', '.problem__footer',
    '.katex-html', '.MJX_Assistive_MathML', '.MathJax_Preview', '.md-editor-toolbar',
  ];

  const BLOCK_TAGS = new Set([
    'address', 'article', 'aside', 'blockquote', 'details', 'div', 'dl', 'dd', 'dt',
    'fieldset', 'figcaption', 'figure', 'footer', 'form', 'h1', 'h2', 'h3', 'h4', 'h5',
    'h6', 'header', 'hr', 'li', 'main', 'ol', 'p', 'pre', 'section', 'summary',
    'table', 'tbody', 'thead', 'tfoot', 'tr', 'ul',
  ]);

  const HEADING_RE = /^h([1-6])$/;

  function isSkippable(el) {
    const tag = el.tagName.toLowerCase();
    if (SKIP_TAGS.has(tag)) return true;
    for (const sel of SKIP_SELECTORS) {
      try { if (el.matches(sel)) return true; } catch (e) { /* 老浏览器忽略 */ }
    }
    return false;
  }

  function mdChildren(el, blockCtx) {
    let out = '';
    for (const c of el.childNodes) out += mdNode(c, blockCtx);
    return out;
  }

  function mdNode(node, blockCtx) {
    if (node.nodeType === 3) {
      const t = node.nodeValue.replace(/\u00a0/g, ' ');
      if (!t) return '';
      if (blockCtx) return t.trim() ? t.replace(/\s+/g, ' ') : '';
      return t.replace(/\s+/g, ' ');
    }
    if (node.nodeType !== 1) return '';
    const el = node;
    if (isSkippable(el)) return '';
    const tag = el.tagName.toLowerCase();

    // 块级公式（KaTeX 的 .katex-display / MathJax 的 .MathJax_Display）
    if (el.classList.contains('katex-display') || el.classList.contains('MathJax_Display')) {
      const tex = el.querySelector('annotation[encoding="application/x-tex"]');
      if (tex) return '\n\n$$\n' + tex.textContent.trim() + '\n$$\n\n';
      return '\n\n$$\n' + el.textContent.trim() + '\n$$\n\n';
    }

    if (BLOCK_TAGS.has(tag)) return mdBlock(el, tag);
    return mdInline(el, tag);
  }

  function mdInline(el, tag) {
    // 行内公式
    if (el.classList.contains('katex') || el.classList.contains('MathJax')) {
      const tex = el.querySelector('annotation[encoding="application/x-tex"]');
      const raw = tex ? tex.textContent.trim() : el.textContent.trim();
      if (raw) return '$' + raw + '$';
    }

    const inner = mdChildren(el, false);
    switch (tag) {
      case 'br':
        // 反斜杠换行比「两个空格 + \n」更耐后续的空行清理
        return '\\\n';
      case 'strong': case 'b':
        return wrapEmphasis(inner, '**');
      case 'em': case 'i':
        return wrapEmphasis(inner, '*');
      case 'del': case 's': case 'strike':
        return wrapEmphasis(inner, '~~');
      case 'code': case 'kbd': case 'samp':
        return codeSpan(el.textContent.replace(/\u00a0/g, ' '));
      case 'a': {
        const href = el.getAttribute('href') || '';
        const text = inner.trim();
        if (!href || href.startsWith('javascript:')) return inner;
        if (!text) return '';
        const url = href.startsWith('#') ? href : new URL(href, location.href).href;
        return '[' + escBrackets(text) + '](' + url.replace(/\)/g, '%29') + ')';
      }
      case 'img': {
        const src = el.getAttribute('src') || '';
        const alt = (el.getAttribute('alt') || '').replace(/[\[\]]/g, '');
        if (!src) return '';
        return '![' + alt + '](' + new URL(src, location.href).href + ')';
      }
      case 'sup': {
        return inner.trim() ? '^' + inner.trim() : '';
      }
      case 'sub': {
        return inner.trim() ? '~' + inner.trim() + '~' : '';
      }
      default:
        return inner;
    }
  }

  function mdBlock(el, tag) {
    const hm = HEADING_RE.exec(tag);
    if (hm) {
      const text = mdChildren(el, false).replace(/\s+/g, ' ').trim();
      return text ? '\n\n' + '#'.repeat(+hm[1]) + ' ' + text + '\n\n' : '';
    }

    switch (tag) {
      case 'hr':
        return '\n\n---\n\n';

      case 'p': {
        const text = mdChildren(el, false).trim();
        return text ? '\n\n' + text + '\n\n' : '';
      }

      case 'pre':
        return preMd(el);

      case 'ul':
        return listMd(el, false);

      case 'ol':
        return listMd(el, true);

      case 'blockquote': {
        const body = mdChildren(el, true).replace(/\n{3,}/g, '\n\n').trim();
        if (!body) return '';
        const quoted = body.split('\n').map(function (l) {
          return l.trim() ? '> ' + l : '>';
        }).join('\n');
        return '\n\n' + quoted + '\n\n';
      }

      case 'table':
        return tableMd(el);

      default: {
        // div / section / li / td……：递归，靠子节点自己产生块分隔
        const inner = mdChildren(el, true);
        if (!inner.trim()) return '';
        return tag === 'li' || tag === 'td' || tag === 'th' ? inner : '\n\n' + inner.trim() + '\n\n';
      }
    }
  }

  function preMd(el) {
    const codeEl = el.querySelector('code') || el;
    const cls = (codeEl.getAttribute('class') || '') + ' ' + (el.getAttribute('class') || '');
    const lm = /(?:language|lang)-([\w+#.-]+)/.exec(cls);
    const lang = lm ? lm[1] : '';

    let text = codeEl.textContent.replace(/\u00a0/g, ' ');
    text = text.replace(/^\n+/, '').replace(/\s+$/, '');

    // 围栏要比正文里最长的一串反引号更长
    const runs = text.match(/`+/g) || [];
    let maxRun = 2;
    for (const r of runs) maxRun = Math.max(maxRun, r.length);
    const fence = '`'.repeat(maxRun + 1);

    return '\n\n' + fence + lang + '\n' + text + '\n' + fence + '\n\n';
  }

  function listMd(el, ordered) {
    const items = [];
    for (const c of el.children) {
      if (c.tagName && c.tagName.toLowerCase() === 'li') items.push(c);
    }
    if (!items.length) return '';

    let out = '\n\n';
    let n = 0;
    for (const li of items) {
      n++;
      const marker = ordered ? n + '. ' : '- ';
      const body = mdChildren(li, true).replace(/\n{3,}/g, '\n\n').trim();
      const lines = body.split('\n');
      out += marker + (lines[0] || '') + '\n';
      for (let i = 1; i < lines.length; i++) {
        out += (lines[i].trim() ? ' '.repeat(marker.length) + lines[i].replace(/\s+$/, '') : '') + '\n';
      }
    }
    return out + '\n';
  }

  function tableMd(el) {
    const trs = el.querySelectorAll('tr');
    if (!trs.length) return '';

    const rows = [];
    for (const tr of trs) {
      const cells = [];
      for (const cell of tr.children) {
        const t = cell.tagName ? cell.tagName.toLowerCase() : '';
        if (t !== 'td' && t !== 'th') continue;
        cells.push(mdChildren(cell, false).replace(/\n+/g, ' ').replace(/\|/g, '\\|').trim());
      }
      if (cells.length) rows.push(cells);
    }
    if (!rows.length) return '';

    const width = rows.reduce(function (w, r) { return Math.max(w, r.length); }, 0);
    const pad = function (r) {
      const out = r.slice();
      while (out.length < width) out.push('');
      return '| ' + out.join(' | ') + ' |';
    };

    let out = '\n\n' + pad(rows[0]) + '\n|' + ' --- |'.repeat(width) + '\n';
    for (let i = 1; i < rows.length; i++) out += pad(rows[i]) + '\n';
    return out + '\n';
  }

  function wrapEmphasis(text, mark) {
    const t = text.trim();
    if (!t) return text;
    return mark + t + mark;
  }

  function codeSpan(text) {
    const t = text.replace(/\s*\n\s*/g, ' ').replace(/^\s+|\s+$/g, '');
    if (!t) return '';
    let fence = '`';
    while (t.indexOf(fence) !== -1) fence += '`';
    const pad = /^`|`$/.test(t) ? ' ' : '';
    return fence + pad + t + pad + fence;
  }

  function escBrackets(s) {
    return s.replace(/[[\]]/g, function (m) { return '\\' + m; });
  }

  // 收尾：合并多余空行、去行尾空格、去掉开头结尾的空行
  function cleanup(md) {
    return md
      .replace(/\r\n?/g, '\n')
      .replace(/[ \t]+\n/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .replace(/^\n+/, '')
      .replace(/\s+$/, '') + '\n';
  }

  /* ============================================================
   * 二、在题目页上找到「题目描述」那一块
   * 站点改版换类名是常事，所以这里按「标题文字」定位，类名只用来兜底。
   * ============================================================ */

  const ANCHOR_RE = /^(题目描述|题目内容|问题描述|Problem Description|Description)$/i;
  const SECTION_TITLE_SEL = '.section__title, [class*="section__title"], [class*="card-title"], [class*="panel-title"], [class*="__title"]';

  function looksLikeElement(el) {
    return el && el.nodeType === 1;
  }

  // 在一个容器里找它的小标题元素
  function titleOf(el) {
    if (!looksLikeElement(el)) return null;
    const direct = el.querySelector(SECTION_TITLE_SEL);
    if (direct) return direct;
    for (const h of el.querySelectorAll('h1,h2,h3,h4,h5,h6')) return h;
    return null;
  }

  function findDescriptionSection() {
    // 按标题文字定位为主：类名会随改版变，文字不会
    const all = document.querySelectorAll('h1,h2,h3,h4,h5,h6,' + SECTION_TITLE_SEL);
    for (const el of all) {
      const text = (el.textContent || '').replace(/\s+/g, ' ').trim();
      if (text.length > 16 || !ANCHOR_RE.test(text)) continue;

      // 从标题往上找内容区。注意不能用 closest()：标题自己带 section__title 类，
      // 匹配 [class*="section"] 时会把它自己返回，按钮就塞进标题里了。
      // 也不能把 [class*="section"] 当选择器——section__header 之类全都会命中。
      let node = el.parentElement;
      let fallback = null;
      let generic = null;
      for (let depth = 0; node && node !== document.body && depth < 4; depth++) {
        const cls = node.getAttribute('class') || '';
        const tag = node.tagName.toLowerCase();
        if (tag === 'section' || /\bsection\b/.test(cls)) return node;
        if (!generic && /\b(card|panel|block|box|item|detail|article)\b/.test(cls)) generic = node;
        if (!fallback && node.querySelector('.section__body, [class*="section__body"]')) fallback = node;
        node = node.parentElement;
      }
      if (fallback) return fallback;
      if (generic) return generic;
      if (el.parentElement) return el.parentElement;
    }
    return null;
  }

  // 「题目描述」后面同级的那些内容区（输入格式 / 样例 / 提示……）
  function siblingSections(anchor) {
    const out = [anchor];
    let el = anchor.nextElementSibling;
    let skipped = 0;
    while (el && skipped < 2) {
      const cls = el.getAttribute('class') || '';
      if (/yc-md-copy|section__tools/.test(cls)) {
        el = el.nextElementSibling;
        continue;
      }
      if (titleOf(el)) {
        out.push(el);
        skipped = 0;
        el = el.nextElementSibling;
        continue;
      }
      // 没有标题的兄弟节点：纯布局容器（没有文字）就跳过继续往后找，
      // 有文字说明正文已经结束（递交框 / 评论 / 页脚），停下。
      if (!el.textContent.trim()) {
        skipped++;
        el = el.nextElementSibling;
        continue;
      }
      break;
    }
    return out;
  }

  function sectionMarkdown(sec) {
    const body = sec.querySelector('.section__body, [class*="section__body"], .richmedia, [class*="content"]') || sec;
    const headingText = headingOf(sec);

    const clone = body.cloneNode(true);
    clone.querySelectorAll('[' + BTN_ATTR + '], .yc-md-copy, .section__tools').forEach(function (n) {
      n.remove();
    });
    // 只删掉与本节标题重复的那一个标题，正文里的子标题（如「样例 1」）要保留
    clone.querySelectorAll('h1, h2, h3, h4, h5, h6, ' + SECTION_TITLE_SEL).forEach(function (n) {
      if (headingText && (n.textContent || '').replace(/\s+/g, ' ').trim() === headingText) n.remove();
    });

    return cleanup(mdChildren(clone, true));
  }

  function headingOf(sec) {
    const t = titleOf(sec);
    return t ? (t.textContent || '').replace(/\s+/g, ' ').trim() : '';
  }

  function problemTitle() {
    const h1 = document.querySelector('.problem__title, h1');
    if (h1 && h1.textContent.trim()) {
      return h1.textContent.replace(/\s+/g, ' ').trim();
    }
    return (document.title || '').split(/\s*[-|｜]\s*/)[0].trim();
  }

  function buildMarkdown(anchor) {
    const secs = siblingSections(anchor);
    const parts = ['# ' + problemTitle()];
    for (const sec of secs) {
      const heading = headingOf(sec);
      const body = sectionMarkdown(sec);
      if (!body) continue;
      if (heading) parts.push('## ' + heading);
      parts.push(body.trim());
    }
    return cleanup(parts.join('\n\n'));
  }

  /* ============================================================
   * 三、按钮
   * ============================================================ */

  const ICON =
    '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>';

  function injectStyle() {
    if (document.getElementById('yc-md-copy-style')) return;
    const style = document.createElement('style');
    style.id = 'yc-md-copy-style';
    style.textContent = [
      '.yc-md-copy{position:absolute;top:10px;right:12px;z-index:6;',
      'display:inline-flex;align-items:center;gap:5px;height:28px;padding:0 10px;',
      'border-radius:8px;border:1px solid rgba(127,127,127,.35);',
      'background:rgba(127,127,127,.14);color:inherit;',
      'font-style:normal;font-weight:500;font-size:12px;line-height:1;letter-spacing:0;',
      'cursor:pointer;opacity:.72;',
      '-webkit-backdrop-filter:blur(8px) saturate(150%);backdrop-filter:blur(8px) saturate(150%);',
      'transition:opacity .15s ease,background .15s ease,border-color .15s ease}',
      '.yc-md-copy:hover{opacity:1;background:rgba(127,127,127,.26);border-color:rgba(127,127,127,.5)}',
      '.yc-md-copy:active{transform:translateY(.5px)}',
      '.yc-md-copy.is-ok{opacity:1;border-color:rgba(72,187,120,.7);background:rgba(72,187,120,.18)}',
      '.yc-md-copy.is-fail{opacity:1;border-color:rgba(245,101,101,.7);background:rgba(245,101,101,.18)}',
      '.yc-md-copy svg{flex:0 0 auto}',
      '@media (max-width:640px){.yc-md-copy{height:26px;padding:0 8px}}',
    ].join('');
    document.head.appendChild(style);
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (e) {
      // 非安全上下文 / 无权限时退回 execCommand
    }
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.cssText = 'position:fixed;top:-9999px;left:-9999px;opacity:0';
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand('copy');
      ta.remove();
      return ok;
    } catch (e) {
      return false;
    }
  }

  function makeButton(sec) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = BTN_CLASS;
    btn.setAttribute(BTN_ATTR, '1');
    btn.title = '把这道题复制为 Markdown';
    btn.innerHTML = ICON + '<span>复制为 Markdown</span>';

    if (getComputedStyle(sec).position === 'static') sec.style.position = 'relative';

    btn.addEventListener('click', async function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      const label = btn.querySelector('span');
      let text = '';
      try {
        text = buildMarkdown(sec);
      } catch (err) {
        console.error(LOG_PREFIX, '转换失败', err);
      }
      if (!text) {
        label.textContent = '没找到内容';
        btn.classList.add('is-fail');
        setTimeout(function () { btn.classList.remove('is-fail'); label.textContent = '复制为 Markdown'; }, 1600);
        return;
      }
      const ok = await copyText(text);
      label.textContent = ok ? '已复制 ' + text.length + ' 字' : '复制失败';
      btn.classList.add(ok ? 'is-ok' : 'is-fail');
      setTimeout(function () {
        btn.classList.remove('is-ok', 'is-fail');
        label.textContent = '复制为 Markdown';
      }, 1600);
    });

    return btn;
  }

  function attach() {
    if (!isProblemPage()) return;
    const sec = findDescriptionSection();
    if (!sec) {
      if (!attach.warned) {
        attach.warned = true;
        console.debug(LOG_PREFIX, '没找到「题目描述」内容区，页面结构可能又变了；把这段 DOM 发给维护者：',
          document.querySelector('.problem-content, #problem-detail, main') || document.body);
      }
      return;
    }
    if (sec.querySelector('[' + BTN_ATTR + ']')) return;
    injectStyle();
    sec.appendChild(makeButton(sec));
    console.debug(LOG_PREFIX, '按钮已挂到', sec);
  }

  // 站点是前端路由，切页不会刷新，用 MutationObserver 兜住
  let pending = false;
  function schedule() {
    if (pending) return;
    pending = true;
    setTimeout(function () { pending = false; attach(); }, 300);
  }

  attach();
  new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('popstate', schedule);
  window.addEventListener('hashchange', schedule);

  // 调试用：控制台里 __ycMd.toMarkdown() 直接看转换结果
  window.__ycMd = {
    toMarkdown: function () {
      const sec = findDescriptionSection();
      return sec ? buildMarkdown(sec) : null;
    },
    find: findDescriptionSection,
  };
})();
