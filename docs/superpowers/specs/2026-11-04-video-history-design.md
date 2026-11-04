# 视频历史记录（Video History）设计文档

- 日期：2026-11-04
- 状态：已确认，待实施
- 关联：`docs/方案设计文档.md` 4.10 节（历史记录 ⬜）、`docs/需求分析文档.md` P2

---

## 一、目标与范围

### 1.1 目标

把「解析 → AI 总结」这条链路产生的数据落库，形成用户可见的历史记录，使用户能够：

1. 回看任意一个解析过的视频的 AI 分析数据（概述、核心要点、术语、深度思考、思维导图、字幕全文）
2. 从历史记录里重新下载该视频（用记录中的链接与清晰度，走网络重新下载）
3. 在历史记录里继续对视频提问（用已存储的字幕作为 AI 上下文）
4. 管理记录：查看列表、删除单条、清空全部

### 1.2 不在本期范围内

- 用户系统 / 登录 / 多租户隔离（当前为单机单人应用）
- 自动过期清理、配额与磁盘占用统计（用户已明确选择「基础管理能力」）
- 永久保存视频文件（历史下载一律走网络重新下载，本地不留成品文件）
- 保存 AI 对话历史（对话只在当前会话内有效）
- 支付、字幕独立下载等其他 P3 功能

### 1.3 现状与约束

当前三条链路的运行时状态**全部只在内存中**：

| 状态 | 位置 | 生命周期 |
|---|---|---|
| 解析结果缓存 | `backend/services/video_service.py::_parse_cache` | 进程内，30 分钟 TTL |
| 下载进度 | `backend/services/video_service.py::task_progress` | 进程内，重启即丢 |
| AI 总结结果 | `backend/api/router.py::ai_task_progress` | 进程内，重启即丢 |

可复用的既有资产：

- `backend/config.py` 已定义 `DB_PATH = backend/history.db`，但无人使用
- `backend/database/__init__.py` 是空壳（原规划为 `db.py` + `models.py`）
- `backend/requirements.txt` 已含 `aiosqlite`（本设计实际使用标准库 `sqlite3`，不新增依赖）
- `frontend/src/components/AiSummaryPanel.vue` 已是纯 props 组件（总结/字幕/思维导图/AI 问答 四 Tab），可直接复用于历史详情页
- `backend/services/export_service.py::generate_pdf` 与 `router.py::_result_to_markdown` 可直接复用于历史记录的导出

---

## 二、关键决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 记录产生时机 | 解析成功即建记录，AI 总结完成后再补写分析数据 | 无字幕/AI 失败的视频也要留痕，避免解析结果白丢 |
| 历史「下载」语义 | 用记录的链接 + 清晰度重新走网络下载 | 本地不留成品文件，磁盘干净；代价是需 10~60 秒 |
| 存储的 AI 数据 | 总结结果 + 思维导图 + 字幕全文 | 存了字幕才能在历史页继续 AI 问答 |
| 存储方案 | 单表 SQLite + JSON 列 | 零新依赖；URL 唯一索引天然去重；查询简单 |
| 页面形态 | 独立路由页 `/history` | 与 `docs/方案设计文档.md` 规划一致；列表不挤占首页 |
| 同 URL 重复解析 | 更新原记录（不新增行） | 列表不出现重复条目；AI 数据刷新为最新 |
| 自动化测试 | 引入 pytest | 后端 CRUD/去重/分页是纯逻辑，值得回归保护 |

---

## 三、存储设计

### 3.1 表结构

单表 `history`，存于 `backend/history.db`（路径由 `config.DB_PATH` 决定，已在 `.gitignore` 中）。

```sql
CREATE TABLE IF NOT EXISTS history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    url           TEXT    NOT NULL UNIQUE,        -- 归一化后的原始链接
    title         TEXT    NOT NULL DEFAULT '',
    author        TEXT    NOT NULL DEFAULT '',
    platform      TEXT    NOT NULL DEFAULT '',
    thumbnail     TEXT    NOT NULL DEFAULT '',     -- 远程封面 URL
    thumb_path    TEXT    NOT NULL DEFAULT '',     -- 本地缓存封面（相对路径）
    duration      REAL,
    formats_json  TEXT    NOT NULL DEFAULT '[]',   -- [{format_id,resolution,ext,filesize}]
    subtitle_lang TEXT,
    subtitle_json TEXT,                            -- [{time,text}]，带时间戳
    transcript    TEXT,                            -- 字幕纯文本
    ai_result     TEXT,                            -- {summary,highlights,terms,qa}
    mindmap_md    TEXT,                            -- markmap 兼容的 Markdown
    status        TEXT    NOT NULL DEFAULT 'parsed',  -- parsed | ai_done | ai_failed
    error         TEXT,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_history_created_at ON history (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_history_status     ON history (status);
```

字段说明：

- `url` 上的 UNIQUE 索引是「同 URL 重复解析 → 更新原记录」的实现基础，写入使用 `INSERT ... ON CONFLICT(url) DO UPDATE`。
- `formats_json` 保存解析时的全部可用格式（抖音 fallback 为单一 `format_id='fallback_best'`），历史页据此渲染清晰度选择器。
- `subtitle_json` / `transcript` 分别存结构化字幕与纯文本：前者用于渲染带时间戳的字幕列表与导出 SRT，后者作为 AI 对话上下文。
- `status` 三态：`parsed`（仅解析成功）、`ai_done`（AI 总结完成）、`ai_failed`（AI 总结失败，错误文案存 `error`）。
- `thumb_path` 存本地封面相对路径；下载失败时留空，前端回退到 `thumbnail` 远程 URL 经 `/api/proxy/image` 代理。

### 3.2 连接管理（`backend/database/db.py`）

- 使用 Python 标准库 `sqlite3`（不引入 `aiosqlite`，避免为异步 API 引入额外依赖与线程/事件循环混用问题）
- 每个线程一个连接（`threading.local`），`check_same_thread=False` + WAL 模式
- 写入使用短事务（`with conn:`），无长事务阻塞读
- 连接初始化时执行 `CREATE TABLE IF NOT EXISTS`（自愈；表缺失不会导致 500）
- 提供 `get_conn()` / `init_db()` / `close_conn()` 三个入口

### 3.3 服务层（`backend/services/history_service.py`）

职责：纯粹的「记录读写」，不依赖 FastAPI，不做网络 IO。

| 方法 | 说明 |
|---|---|
| `upsert_parsed(url, video_info, subtitle_lang=None)` | 解析成功后写入/更新记录，返回 `record_id` |
| `attach_ai_result(record_id, subtitle_data, transcript, ai_result, mindmap_md)` | AI 完成后补写分析数据，`status='ai_done'` |
| `mark_ai_failed(record_id, error)` | AI 失败时标记 `status='ai_failed'` 并记录错误 |
| `list_records(page, page_size, platform=None, keyword=None)` | 分页查询，列表不含字幕/AI 大字段 |
| `get_record(record_id)` | 取完整记录（含 AI 数据） |
| `delete_record(record_id)` | 删除单条并清理本地封面 |
| `clear_records()` | 清空全部并清理本地封面 |
| `get_record_by_url(url)` | 按 url 取最近一条（`history_id` 缺失时的兜底） |

所有对外方法返回普通 `dict` / `list`（JSON 字段在服务层反序列化），路由层不接触 JSON 编解码细节。

---

## 四、后端 API

### 4.1 新增端点

| 方法 | 路径 | 说明 | 响应 |
|---|---|---|---|
| GET | `/api/history?page=1&page_size=20` | 分页列表 | `{total, page, page_size, items:[...]}` |
| GET | `/api/history/{id}` | 记录详情（含字幕/AI 数据） | 完整记录对象 |
| DELETE | `/api/history/{id}` | 删除单条 | `{deleted: true}` |
| DELETE | `/api/history` | 清空全部 | `{deleted: n}` |
| POST | `/api/history/{id}/download` | 重新下载 | `{task_id}` |
| GET | `/api/history/thumb/{id}` | 本地封面 | 图片流（不存在返回 404，前端回退远程代理） |

列表项字段（刻意不含字幕/AI 大字段，保证分页接口轻量）：

```json
{
  "id": 12,
  "title": "视频标题",
  "author": "作者",
  "platform": "bilibili",
  "duration": 754.0,
  "thumbnail": "https://...",
  "thumb_path": "thumbs/12.jpg",
  "status": "ai_done",
  "has_ai": true,
  "created_at": "2026-11-04 10:30:00",
  "updated_at": "2026-11-04 10:31:12"
}
```

其中 `has_ai` 等价于 `status === 'ai_done'`，前端据此决定是否显示「AI 已总结」徽标。

详情额外字段：`formats`（数组）、`subtitle_data`（数组）、`transcript`（字符串）、`ai_result`（对象）、`mindmap_markdown`（字符串）、`url`、`error`。

### 4.2 改造的现有端点

**`POST /api/parse`** —— 解析成功后落库，返回值新增 `history_id`：

```json
{ "title": "...", "formats": [...], ..., "history_id": 12 }
```

写入失败（DB 异常）**不影响解析结果返回**，仅记日志并继续——历史记录是辅助能力，不应拖垮主流程。

**`POST /api/ai/summarize`** —— 请求体新增可选字段 `history_id`：

```json
{ "url": "...", "subtitle_lang": null, "history_id": 12 }
```

- `history_id` 存在 → AI 完成后回写该记录
- `history_id` 缺失 → 后端按 `url` 兜底匹配最近一条记录（`get_record_by_url`），匹配不到则不写库（不影响 AI 任务本身）

AI worker 线程在两种终态下都要回写：

- 成功 → `attach_ai_result(...)`，`status='ai_done'`
- 失败（无字幕 / 模型报错）→ `mark_ai_failed(record_id, error)`，`status='ai_failed'`

**`POST /api/download`** —— 抽取公共解析入口，修复「重启后抖音下载失效」的现存缺陷：

```python
def resolve_download_source(url: str, format_id: str) -> tuple[str, str | None]:
    """返回 (mode, direct_url)；mode 为 'direct'（直链下载）或 'yt-dlp'。"""
```

逻辑：

1. 命中内存 `_parsed_cache` 且结果带 `_fallback` → 直链模式
2. 否则调用 `parse_video(url)` 重新解析（命中 30 分钟缓存则秒回）；结果带 `_fallback` → 直链模式
3. 其余情况 → yt-dlp 模式

`/api/download` 与 `/api/history/{id}/download` 共用该函数。历史下载场景下即使服务重启、内存缓存已空，也能通过第 2 步重新拿到抖音直链。

### 4.3 历史下载流程

`POST /api/history/{id}/download {format_id}`：

1. 取记录 → 得到 `url` 与可选的 `format_id`
2. `format_id` 缺省时，取记录中分辨率最高的格式
3. `resolve_download_source(url, format_id)` 判定走直链还是 yt-dlp
4. `start_fallback_download(direct_url)` 或 `start_download(url, format_id)` → 返回 `task_id`
5. 前端用**现有**的 `/api/download/status/{task_id}` 轮询进度、`/api/download/file/{task_id}` 取文件，交互与首页下载完全一致

下载产物沿用现有约定：`backend/downloads/{task_id}.mp4`，不长期保留。

---

## 五、前端设计

### 5.1 路由与入口

- `frontend/src/router.js` 新增 `/history` → `views/History.vue`
- `Home.vue` 导航栏新增「历史记录」链接（现有导航为 功能 / 支持平台 / 定价 三个锚点，改为「历史记录」指向路由）
- `useHistory.js` composable：列表分页、详情加载、删除、清空、触发下载、加载状态与错误提示

### 5.2 列表页（`views/History.vue`）

- 顶部：标题 + 「清空全部」按钮（二次确认）
- 主体：卡片网格，1 列（移动端）/ 2 列（桌面端）
- 卡片内容：封面缩略图（优先本地 `thumb_path`，回退远程代理图）、标题（2 行截断）、作者、平台徽标、时长、解析时间、状态徽标
  - `parsed` → 灰色「已解析」
  - `ai_done` → 绿色「AI 已总结」
  - `ai_failed` → 橙色「AI 失败」（hover 显示 error 文案）
- 空状态：无记录时展示引导文案 + 返回首页按钮
- 分页：底部「加载更多」按钮（`page_size=20`，追加而非翻页）

### 5.3 详情页

路由 `/history/:id`，独立详情视图（不复用列表页内联展开）。布局复用 `Home.vue` 的双栏结构：

- 左栏（2/5 宽）：视频卡 —— 封面、标题、作者、平台、时长、清晰度选择器（来自记录的 `formats`）、下载按钮 / 下载进度 / 完成态「保存到本地」
- 右栏（3/5 宽）：**直接复用 `AiSummaryPanel.vue`**，传入记录里的 `ai_result` / `subtitle_data` / `transcript` / `mindmap_markdown`，四个 Tab（总结 / 字幕 / 思维导图 / AI 问答）全部可用
  - 「AI 问答」Tab：上下文用库里的 `transcript`，调用现有 `/api/ai/chat`，对话记录不持久化
  - 状态为 `ai_failed` 时，该面板显示错误文案与「重新解析」入口（回到首页重新解析同一 URL）
- 详情页底部：删除本条记录、导出 Markdown / PDF（复用 `export_service` 与 `_result_to_markdown`）

### 5.4 Composable 改造

**`useSummarize.js` 新增 `load(record)`**：把库中记录的数据灌入现有状态（`summaryResult` / `transcriptText` / `subtitleData` / `mindmapMarkdown` / `videoTitle`），不触发新的 AI 任务。历史页借此复用其 `chat()` 能力。

**`useDownload.js` 新增 `downloadWith(url, formatId)`**：用记录里的链接与选中清晰度启动下载，复用现有的轮询与文件 URL 逻辑；不改动现有 `download()` 行为。

**`api/index.js` 新增**：`listHistory` / `getHistory` / `deleteHistory` / `clearHistory` / `downloadHistory` / `getHistoryThumbUrl`，风格与现有封装一致（统一 `_extractDetail` 错误处理）。

---

## 六、封面本地缓存

抖音/B站封面 URL 带签名会过期，历史记录隔天回看可能裂图。方案：

- 解析成功后，后台线程异步下载封面到 `backend/history/thumbs/{record_id}.jpg`（`config.HISTORY_THUMB_DIR`）
- 下载失败不阻断主流程，`thumb_path` 留空，前端回退远程 URL 经 `/api/proxy/image` 代理
- 删除记录 / 清空时同步删除对应封面文件

---

## 七、错误处理与边界

| 场景 | 处理 |
|---|---|
| 视频无字幕 | 记录保留，`status='ai_failed'`，`error='该视频没有字幕，暂不支持 AI 总结'`；历史页仍可重新下载 |
| AI 接口报错 / 超时 | 同上，记录保留并标记 `ai_failed` |
| 落库失败（DB 异常/磁盘满） | 记日志，不影响解析与 AI 主流程；解析响应照常返回（仅 `history_id` 缺失） |
| 封面下载失败 | 不阻断；回退远程代理图 |
| 历史记录指向的视频已下架 | 重新下载时 yt-dlp 报错，前端沿用现有错误提示；记录保留，可删除 |
| 抖音直链过期 | 历史下载走 `resolve_download_source` 重新解析拿新直链 |
| 同 URL 并发解析 | UNIQUE 索引 + `ON CONFLICT DO UPDATE` 保证单行；各线程独立连接 |
| 服务重启 | 记录与 AI 数据在 SQLite 中存活；仅进行中的下载/AI 任务进度丢失（内存态，符合现状） |
| 详情页访问不存在的 id | 返回 404 + 「记录不存在」 |

---

## 八、测试

引入 pytest（`backend/requirements.txt` 增加 `pytest`、`httpx` 已存在）。

- `backend/tests/conftest.py`：临时目录 + 临时 DB 的 fixture（通过 monkeypatch `config.DB_PATH` / `config.HISTORY_THUMB_DIR` 指向 tmp_path），保证**不触碰真实的 `backend/history.db`**
- `backend/tests/test_history_service.py`：
  - upsert 新建记录后字段正确
  - 同 URL 二次 upsert → 行数不变、字段被更新（去重语义）
  - `attach_ai_result` / `mark_ai_failed` 正确改写 `status`
  - 分页：`page` / `page_size` 边界、`total` 正确、按 `created_at DESC` 排序
  - `delete_record` / `clear_records` 生效且清理封面文件
  - `get_record_by_url` 命中与未命中
- `backend/tests/test_history_api.py`：用 `fastapi.testclient.TestClient` 覆盖 `GET /api/history`、`GET /api/history/{id}`、`DELETE /api/history/{id}`、`DELETE /api/history`、`POST /api/history/{id}/download`（下载分支打桩，不真实联网）

手工验证清单（无法自动化，需真实网络）：

1. 解析一个 YouTube 视频 → 首页历史页出现记录，状态「AI 已总结」
2. 刷新浏览器 / 重启后端 → 记录与 AI 数据仍在
3. 历史详情页四个 Tab 均有内容，AI 问答能基于字幕回答
4. 历史详情页点下载 → 进度条走完 → 文件可下载保存
5. 抖音视频：重启后端后从历史记录重新下载仍成功
6. 删除单条 / 清空全部 → 列表刷新、封面文件消失

---

## 九、改动清单

### 后端

| 文件 | 动作 |
|---|---|
| `backend/config.py` | 新增 `HISTORY_THUMB_DIR`、`HISTORY_PAGE_SIZE_DEFAULT` |
| `backend/database/db.py` | 新建：连接管理、建表 |
| `backend/database/models.py` | 新建：表结构定义与初始化 SQL |
| `backend/services/history_service.py` | 新建：记录读写服务 |
| `backend/services/video_service.py` | 新增 `resolve_download_source()`；`start_download`/`start_fallback_download` 复用 |
| `backend/api/router.py` | 新增 6 个 history 端点；`/api/parse` 返回 `history_id`；`/api/ai/summarize` 支持 `history_id` 并回写；`_summarize_worker` 增加落库分支 |
| `backend/requirements.txt` | 增加 `pytest`（dev） |
| `backend/tests/conftest.py` | 新建：临时 DB / 临时缩略图目录 fixture |
| `backend/tests/test_history_service.py` | 新建：服务层单元测试 |
| `backend/tests/test_history_api.py` | 新建：接口级测试 |

### 前端

| 文件 | 动作 |
|---|---|
| `frontend/src/router.js` | 新增 `/history` 与 `/history/:id` |
| `frontend/src/api/index.js` | 新增 history 相关 API 封装 |
| `frontend/src/composables/useHistory.js` | 新建：列表/详情/删除/清空/下载 |
| `frontend/src/composables/useSummarize.js` | 新增 `load(record)` |
| `frontend/src/composables/useDownload.js` | 新增 `downloadWith(url, formatId)` |
| `frontend/src/views/History.vue` | 新建：列表页 |
| `frontend/src/views/HistoryDetail.vue` | 新建：详情页（复用 `AiSummaryPanel.vue`） |
| `frontend/src/views/Home.vue` | 导航栏增加「历史记录」入口 |

### 文档

| 文件 | 动作 |
|---|---|
| `docs/方案设计文档.md` | 4.10 节标记为已实现并更新 API 说明 |
| `docs/需求分析文档.md` | P2 历史记录状态更新 |
| `docs/项目总结文档.md` | 补充历史记录已实现说明 |

---

## 十、实施顺序建议

1. `database/db.py` + `models.py` → `history_service.py`（含 pytest）
2. `router.py` 落库接入（`/api/parse` 返回 `history_id`、`/api/ai/summarize` 回写）+ 6 个 history 端点
3. `video_service.resolve_download_source()` + 历史下载端点（含抖音重启后可用）
4. 封面本地缓存
5. 前端：API 封装 → `useHistory` → `useSummarize.load` / `useDownload.downloadWith` → 列表页 → 详情页 → 导航入口
6. 文档更新
