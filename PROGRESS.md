# AlphaSignal — 开发进度记录

> 最后更新：2026-02-24

---

## 线上地址

| 服务 | URL |
|------|-----|
| 前端 (Vercel) | https://alphasignalapp.vercel.app |
| 后端 (Railway) | https://alphasignal-production.up.railway.app |
| API 文档 | https://alphasignal-production.up.railway.app/docs |
| GitHub | https://github.com/samchenhub/alphasignal |

---

## 已完成功能

### 基础设施
- [x] FastAPI 后端部署到 Railway（push 到 main 自动重新部署）
- [x] Next.js 前端部署到 Vercel
- [x] Next.js rewrites 代理 `/api/*` → Railway（解决 CORS，无需客户端 API URL）
- [x] GitHub Actions CI（push 到 main 自动跑测试，已修复 GROQ_API_KEY 配置）
- [x] Alembic 数据库迁移（启动时自动运行 `alembic upgrade head`）
- [x] PostgreSQL on Railway（migrations 0001～0003 已应用）

### 数据采集
- [x] RSS 新闻采集（多个 US/CN 新闻源，每 15 分钟运行）
- [x] yfinance 新闻 API（per-ticker 新闻，补充 RSS 覆盖不足的股票）
- [x] yfinance 历史价格数据（自动拉 90 天 OHLCV）
- [x] AKShare A 股数据（中国市场）
- [x] 35 只美股 ticker 追踪（从 7 只扩展到 35 只）

### LLM 分析流水线
- [x] Groq llama-3.3-70b（两阶段：相关性过滤 → 情绪分析）
- [x] 公司名称映射（HD → Home Depot，防止 LLM 漏判）
- [x] 全局并发锁（防止多次 sync 打爆 Groq 30 RPM 限制）
- [x] 非阻塞后台 sync（HTTP 不超时）

### 前端 UI
- [x] 深色主题导航栏（α Logo + Live 指示器 + GitHub 链接）
- [x] 统计卡片（分析文章数、采集文章数、价格数据点、告警数）
- [x] 市场选择（🇺🇸 US / 🇨🇳 A-Share）+ 可滚动 ticker 栏
- [x] 5 个 Tab：📈 Price & Sentiment / 📰 News Feed / ⚡ Backtest / 🔔 Alerts / 🔍 Search
- [x] StockChart：价格折线 + 情绪柱状图（绿/红）
- [x] NewsFeed：左侧情绪颜色条 + 情绪分数徽章
- [x] AlertsPanel + SearchPanel

### 用户认证
- [x] Clerk 认证集成（可选，未配置时不影响运行）
- [x] `user_watchlists` 表 + CRUD API
- [x] PyJWT + JWKS 验证

### M4 自然语言回测引擎（刚完成）
- [x] `strategy_parser.py` — Groq 解析自然语言 → 结构化策略 JSON
- [x] `backtest/engine.py` — 纯 Python 回测引擎（无 backtrader 依赖）
  - 支持做多 / 做空方向
  - 情绪阈值入场（例：sentiment < -0.7）
  - 时间固定出场（持仓 N 天后平仓）
  - 计算：Total Return、Sharpe Ratio、Max Drawdown、Win Rate
- [x] `api/backtest.py` — `POST /api/v1/backtest/` + `GET /api/v1/backtest/history`
- [x] `BacktestPanel.tsx` — 自然语言输入 + 指标卡片 + Equity Curve 图表 + 交易记录表
- [x] Migration 0003（`backtest_strategies` + `backtest_results` 表）

---

## 已知问题 / 待观察

| 问题 | 说明 |
|------|------|
| Groq 免费 token 日限 | 100K tokens/day，采集 + 分析消耗快，每天 UTC 00:00 重置 |
| analysis_results 积累慢 | Scheduler 每 15 min 处理 20 篇，大量 articles 在积压 |
| pgvector 扩展缺失 | Railway PostgreSQL 17 没有 pgvector，向量搜索暂时无法使用 |
| 回测信号依赖数据量 | 需要足够多的 analysis_results 才能触发交易信号 |

---

## 下一步工作

### 第一步 — 验证 Backtest 端到端（下次开始前先做）
- [ ] 等 Groq token 重置后（明天），用 AMZN 或 GS 跑一次完整回测
- [ ] 验证：策略解析 → 有交易记录 → 指标数值合理
- [ ] 如果没有信号，调低入场阈值（-0.7 → -0.3）或拉长时间范围

### P1 — M5 Multi-Agent 研究助手

**后端（新建 3 个文件）**

`backend/app/research/agents.py`
- News Agent：汇总该 ticker 的情绪数据和关键事件
- Price Agent：拉 OHLCV 统计（均值、波动率、涨跌幅）
- Correlation Agent：分析情绪 vs 价格相关性
- Report Agent：用 Claude Sonnet 生成 Markdown 报告

`backend/app/api/research.py`
- `POST /api/v1/research/` — Server-Sent Events 流式输出（实时显示每个 agent 进度）
- `GET /api/v1/research/history` — 历史报告列表

`backend/app/db/migrations/versions/0004_add_research_reports.py`
```sql
CREATE TABLE research_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id VARCHAR(255),
  query TEXT,
  tickers TEXT[],
  report_markdown TEXT,
  agent_trace JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**前端（新建 1 个文件）**

`frontend/src/app/components/ResearchPanel.tsx`
- 查询输入框
- 实时进度流（News Agent ✓ → Price Agent ✓ → Correlation ✓ → Report ✓）
- Markdown 报告渲染（需安装 `react-markdown`）

`page.tsx` 增加 🔬 Research tab

### P2 — 数据质量提升
- [ ] 向量语义搜索：在 Railway 启用 pgvector 扩展（或迁移到 Supabase）
- [ ] 增加每批处理量（从 20 → 50，需要 Groq Dev Tier 或更换免费 key）

### P3 — 产品化（Month 3）
- [ ] Landing page（未登录用户看到的介绍页）
- [ ] Stripe 计费（Free / Pro 两档：$0 / $19 per month）
  - Free：5 次回测/月，3 次研究报告/月
  - Pro：不限次数 + 1 年历史数据
- [ ] Webhook 告警（极端情绪 → Slack 消息）
- [ ] Sentry 错误监控

---

## 技术架构速查

```
前端：  Next.js 15 + TailwindCSS + Recharts
后端：  FastAPI + asyncpg + SQLAlchemy async
数据库：PostgreSQL 17 (Railway)
LLM：   Groq llama-3.3-70b-versatile（免费：30 RPM / 100K tokens/day）
采集：  yfinance + AKShare + RSS (feedparser)
认证：  Clerk (可选)
部署：  Railway (后端) + Vercel (前端) + GitHub Actions (CI)
```

## 数据库表（当前状态）

| 表名 | 说明 | Migration |
|------|------|-----------|
| `articles` | 采集的原始文章 | 0001 |
| `analysis_results` | LLM 情绪分析结果 | 0001 |
| `stock_prices` | 日线 OHLCV 价格数据 | 0001 |
| `alerts` | 极端情绪告警 | 0001 |
| `user_watchlists` | 用户自定义 watchlist | 0002 |
| `backtest_strategies` | 回测策略（NL 输入 + 解析结果） | 0003 |
| `backtest_results` | 回测绩效指标 + equity curve | 0003 |
