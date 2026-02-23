# Future Work & Known Issues

## 🔴 Priority 1 — 先跑起来（必须修，否则无法启动）

### 1. 修循环导入
`app/api/search.py` 里 import 了 `app.analysis.claude_analyzer`，会触发循环导入。
把 embedding 生成逻辑抽出到独立的 `app/analysis/embeddings.py`。

### 2. 锁定 APScheduler 版本
`pyproject.toml` 写的是 `apscheduler>=3.10.0`，但 APScheduler 4.x 的 API 完全不兼容。
改成 `apscheduler==3.10.4` 固定版本，或者迁移到 4.x 的新 API。

### 3. 验证 AKShare 列名
AKShare 的 `stock_news_em()` 返回的 DataFrame 列名可能不是"新闻标题"/"新闻链接"。
需要实际运行 `print(df.columns)` 查看真实列名，再更新 `akshare_news.py`。

### 4. 验证 yfinance 多 ticker 下载格式
yfinance 0.2.x 以后，多 ticker 下载返回的 MultiIndex columns 结构有变化。
`data["Close"][ticker]` 这种写法可能报 KeyError，需要实际测试后修正。

### 5. 验证 RSS Feed URLs
Reuters 近年多次更换 RSS 地址。需要逐一验证 `rss_fetcher.py` 里的 5 个 feed URL 实际可访问且返回有效内容。

### 6. Next.js `public` 文件夹
Next.js 构建需要 `frontend/public/` 目录存在，否则 Docker build 会报错。创建该目录并放一个占位文件。

---

## 🟡 Priority 2 — 功能补完（跑通之后做）

### 7. 实现真正的向量语义检索
`app/api/search.py` 里的 `_vector_search()` 目前直接 pass，落回 full-text search。
完整实现路径：
- 调用 `client.embeddings.create()` 对查询文本生成向量（或用 Sonnet 的 text representation）
- 在 `claude_analyzer.py` 处理文章时同步生成并存储 embedding 到 `analysis_results.embedding`
- `_vector_search()` 改用 pgvector 的 `<=>` 余弦距离算子查询

### 8. 实现 Webhook 告警
`.env` 里有 `ALERT_WEBHOOK_URL` 配置项，但 `claude_analyzer.py` 里只写入了 alerts 表，没有实际发出 HTTP 请求。
添加 `app/alerts/webhook.py`，在告警触发后 POST 到配置的 URL（Slack/飞书/自定义 endpoint 均可）。

### 9. 前端 Bar 颜色按情绪正负区分
`StockChart.tsx` 里情绪柱状图颜色是固定灰色。Recharts 的 `<Bar>` 不支持 per-bar 动态 fill，
需要换成自定义 `<Cell>` 或者用 `recharts` 的 `label` + 条件渲染实现绿/红分色。

### 10. API 限流
当前 FastAPI 接口没有任何限流。添加 `slowapi` 中间件，对 `/api/v1/search/` 等重计算接口限速。

### 11. 股价数据补历史
目前 `sync_us_prices()` 只拉最近 7 天。初次启动后应该补拉至少 90 天历史数据，
否则前端 price-correlation 图表数据点过少，无法体现趋势。

---

## 🟢 Priority 3 — 质量与体验（有空再做）

### 12. 写集成测试
至少覆盖：
- RSS fetcher 能否正确解析并入库
- `claude_analyzer.py` 的 JSON 解析是否鲁棒（异常格式、空内容、纯中文）
- 所有 API 接口的 happy path

建议用 `pytest` + `pytest-asyncio` + `httpx.AsyncClient`。

### 13. 添加 Alembic 自动迁移到 CI
每次改 `models.py` 后需要手动生成迁移文件，容易忘。
可以加一个 `make migration msg="xxx"` 的快捷命令写在 Makefile 里。

### 14. SEC EDGAR 按 Ticker 过滤
目前拉的是全市场最新 8-K，与 watchlist 无关的公司也会进入数据库。
EDGAR 支持按 CIK 过滤，可以预先建立 ticker → CIK 映射表，只拉 watchlist 公司的文件。

### 15. 前端添加 Loading Skeleton 动画
目前空数据状态只显示一段文字提示。可以用 Tailwind 的 `animate-pulse` 做更精致的骨架屏。

### 16. 部署到云端
本地 `docker compose up` 之后，下一步可以部署到：
- **Railway / Render**：对 Docker Compose 支持好，免费 tier 可用，适合 demo
- **Fly.io**：免费 tier + PostgreSQL 插件，国内访问比 AWS 稳定
- 部署后更新 README 加上 live demo 链接

---

## 已知技术债

| 位置 | 问题 |
|---|---|
| `akshare_prices.py` | AKShare A股代码需区分沪（60xxxx）和深（00xxxx），部分接口参数不同 |
| `claude_analyzer.py` | LLM 调用是同步的（`_call_sonnet`），在 async FastAPI 里会阻塞事件循环，应改用 `asyncio.to_thread()` 包裹 |
| `rss_fetcher.py` | 部分 RSS feed 内容只有 summary，没有完整正文，情绪分析质量会下降 |
| `search.py` | `plainto_tsquery('simple', ...)` 对中文分词效果差，中文语义搜索需要换用 `zhparser` 扩展或直接依赖向量检索 |
