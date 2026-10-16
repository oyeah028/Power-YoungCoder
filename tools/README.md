# 站点改版后，脚本里有两段是「照抄站点取值」的生成内容，用 tools 里的脚本同步

改版后的 YCOJ 把组件配色收拢成了 CSS 变量（`--home-*`、`--list-*`、`--detail-*`、`--yc-*` …），
每个变量自带一套浅色值，站点自己的深色模式再换成另一套；另外还有一批组件没走变量，
而是自己写死了明暗两套颜色。脚本不依赖站点的主题开关，所以必须自己写这两部分。

对应脚本里两段「生成内容」：

* `site-token-values-light()` / `site-token-values-dark()`：站点变量的两套取值
* `// @site-dark-rules-begin` … `// @site-dark-rules-end`：站点写死的深色取值

站点改版后按下面两步重新同步即可（正常使用脚本不需要做这些）。

## 1. 采集站点当前的取值

1. 浏览器登录站点，打开 DevTools 控制台；
2. 粘贴 [collect-site-tokens.js](./collect-site-tokens.js) 的内容并回车，它会下载一个 JSON 快照；
3. 对每种页面类型各做一次（首页、题库列表、题目、作业列表/详情、比赛列表/详情、评测记录、
   排名、用户主页、讨论列表/详情、博客、课程、站内消息、账户/偏好/安全设置……）；
4. 把所有 JSON 放进 [snapshots/](./snapshots)。

## 2. 重新生成脚本里的两段内容

```bash
python tools/sync-theme.py
```

脚本会重排变量、区分中性色与状态色/强调色（中性色映射到主题调色板，
状态色/强调色沿用站点自己的深色取值），然后原地更新 `Power-YoungCoder.user.styl`。
它是幂等的，可以反复运行。

调色板符号（`surface_color`、`raised_color`、`inset_color`、`hover_color`、
`separator_color`、`primary_text_color`、`secondary_text_color`、`canvas_color`、
`alternate_color`）定义在脚本开头的「调色板」一节里，改配色改那里即可。

## 注意

* `@-moz-document` 的域名列表必须写在**同一行**（`domain("a"), domain("b")`）。
  换行后第二个 `domain()` 会让 Stylus 前处理器直接解析失败
  （`stylus:48:1 Cannot read properties of undefined (reading 'name')`），
  整个样式都会加载不出来。
* `tools/snapshots/` 只放在本地、不提交（见 `.gitignore`）。
* Mantine / Element Plus / Monaco 这些第三方组件库有自己的主题开关，脚本不动它们的变量。
* 卡片的背景由脚本自己画（亚克力层），生成时会计过 `.section` 这类容器，不再写死它们的底色。
