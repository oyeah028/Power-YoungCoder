# 站点改版后，同步组件颜色变量

改版后的 YCOJ 把组件配色收拢成了 CSS 变量（`--home-*`、`--list-*`、`--detail-*`、`--yc-*` …），
每个变量自带一套浅色值，站点自己的深色模式再换成另一套。用户样式会把这些中性色
映射到主题调色板，并保留站点自己的状态色和强调色。

生成内容是 `site-token-values-light()` / `site-token-values-dark()`。相同颜色的变量
会合并成 `set-theme-tokens(...)` 调用，避免源码中出现数百条重复声明。

站点改版后按下面两步重新同步即可（正常使用脚本不需要做这些）。

## 1. 采集站点当前的取值

1. 浏览器登录站点，打开 DevTools 控制台；
2. 粘贴 [collect-site-tokens.js](./collect-site-tokens.js) 的内容并回车，它会下载一个 JSON 快照；
3. 对每种页面类型各做一次（首页、题库列表、题目、作业列表/详情、比赛列表/详情、评测记录、
   排名、用户主页、讨论列表/详情、博客、课程、站内消息、账户/偏好/安全设置……）；
4. 把所有 JSON 放进 [snapshots/](./snapshots)。

## 2. 重新生成变量映射

```bash
python tools/sync-theme.py
```

脚本会重排变量、区分中性色与状态色/强调色，然后原地更新 `Power-YoungCoder.user.styl`。
它是幂等的，可以反复运行。

旧版站点曾经需要一大段逐组件写死的深色规则；当前版本已经由站点变量和
`--yc-ui-surface` 等通用表面变量承载，这段兼容样式已在 1.2.1 中弃用。

调色板符号（`surface_color`、`raised_color`、`inset_color`、`hover_color`、
`separator_color`、`primary_text_color`、`secondary_text_color`、`canvas_color`、
`alternate_color`）定义在脚本开头的「调色板」一节里，改配色改那里即可。

## 注意

* 顶层 `@-moz-document` 的域名必须写在**同一行**。当前只匹配 `youngcoder.cn`。
* 卡片选择器使用 `html:root:not(#…) body #panel` 提高权重；`:not(#…)` 不改变匹配范围。
  不要改用 `:is()` 收拢嵌套选择器，Stylus 展开时可能破坏后代规则。
* `tools/snapshots/` 只放在本地、不提交（见 `.gitignore`）。
* Mantine / Element Plus / Monaco 这些第三方组件库有自己的主题开关，脚本不动它们的变量。
