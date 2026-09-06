# 问枢 Pivot · S3 完整原型（10 页）

按《问枢Pivot-A3门户设计.md》确定的**页面结构 + S3 商务蓝灰视觉 + 交互规范**制作的可点击静态原型。
纯 HTML/CSS/JS，无任何外部依赖，**双击 `index.html`（或任一页面）即可在浏览器中体验**。

## 入口与页面对照

| 页面 | 文件 | 对应规格 |
|---|---|---|
| 登录 | `login.html` | P1 |
| 首页 | `home.html` | P2 |
| 知识库列表 | `library.html` | P3 |
| 文档详情（PDF 内嵌预览） | `doc.html` | P4 |
| 全局搜索 | `search.html` | P5 |
| 对话 + 证据抽屉 | `chat.html` | P6 |
| 后台概览 | `admin-overview.html` | P7 |
| 后台文档管理 | `admin-docs.html` | P8 |
| 后台用户管理 | `admin-users.html` | P9 |
| 后台审计日志 | `admin-audit.html` | P10 |

> 建议直接打开 **`index.html`**（入口页，含各页直达链接与浏览路径推荐）。

## 模拟的路由（页面间真实跳转，可体验完整流程）

```
login.html ──登录──> home.html（首页）
home.html ──知识空间卡/最近更新──> library.html ──文档行──> doc.html
home.html ──Hero 搜文档──> search.html?q=关键词       （回显并高亮命中词）
home.html ──Hero 问 AI──>  chat.html?q=关键词        （自动带入问题）
doc.html  ──针对本文提问──> chat.html?doc=1          （显示"已引用文档"限定 chip）
doc.html  ──右上用户菜单/快捷入口──> admin-*.html     （后台四页互通）
search.html ──底部"直接问 AI"──> chat.html?q=...
doc.html?id=1&hl=1  ← 模拟"从引用跳转原文"（定位到 P12 高亮段落）
```

## 可操作的演示功能（每个都有真实反馈）

- 全局：顶栏搜索（Ctrl+K）、用户菜单、Toast 提示、Esc 关闭浮层；
- 首页：搜/问双 Tab 滑动指示、空间卡/文档行/快捷入口悬停动效；
- 对话：发送演示（打字动画 + 追加回复）、引用 [1]/[2] 悬停气泡 + 点击弹证据抽屉、👍👎 可选可取消、导出 Word/Markdown 浮层、会话切换、新建会话、看 URL 参数联动；
- 知识库：空间勾选 + 库内搜索实时过滤、类型/标签筛选、排序、翻页提示；
- 文档详情：PDF 模拟翻页（4 页）、页码指示、返回列表；
- 全局搜索：关键词高亮（mark）、命中数统计、空结果引导问 AI；
- 后台：概览统计卡/解析队列/问答趋势条（可悬停）、文档管理（模拟上传进度条、解析中/失败/重试、删除确认弹窗）、用户管理（新建用户弹窗、停用/启用、行内更新）、审计日志（提问记录可展开命中详情、筛选查询提示）。

## 文件结构

```
S3完整原型/
├── index.html        ← 入口（推荐从这里开始）
├── login.html  home.html  library.html  doc.html  search.html  chat.html
├── admin-overview.html  admin-docs.html  admin-users.html  admin-audit.html
├── s3.css            ← 共享样式：S3 设计令牌 + 全部组件（正式开发照此落地为全局变量+组件）
└── common.js         ← 公共脚本：toast / 用户菜单 / Ctrl+K / Modal / 抽屉 / 投票 / 导出浮层
```

## 与正式开发的关系

- 方案定稿依据：《问枢Pivot-技术方案V1.1.md》 + 《问枢Pivot-A3门户设计.md》（§7 视觉与交互规范）；
- 正式工程将用 **Next.js + shadcn/ui** 实现：`s3.css` 的 `:root` 变量 → 全局 CSS 变量；布局 → 前台 `Topbar+Page` / 后台 `AdminShell(aside+content)`；交互 → 共享组件（Button/Badge/Toast/Drawer/Modal/Table）；
- 本原型全部数据为 Mock，正式开发时以 API 契约替换。
