# 时雨视频分析网站 — 开发方案

> 详细文档已拆分为：
> - [需求分析文档](docs/需求分析文档.md)
> - [方案设计文档](docs/方案设计文档.md)

## 一、项目概述

开发一个时雨视频分析网站，支持从各大视频平台（YouTube、Bilibili、抖音、Twitter等1000+平台）下载视频。
采用Apple官网风格UI设计，支持手机端使用，具备付费能力。

## 二、技术架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        用户（浏览器/手机）                     │
│                   Safari / Chrome / 微信内置浏览器             │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTPS
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                     Nginx（反向代理）                         │
│              静态资源托管 / SSL终端 / 负载均衡                  │
│            ┌──────────────┬───────────────┐                  │
│            │  /           │  /api/*       │                  │
│            │  前端静态资源  │  转发到后端    │                  │
│            └──────┬───────┴───────┬───────┘                  │
└───────────┼───────────────┼───────────────────────────┘
             │               │
             ▼               ▼
┌──────────────────┐  ┌──────────────────────────────────────┐
│  前端（静态资源）  │  │          后端（FastAPI）               │
│                  │  │                                      │
│  Vue 3 + Vite    │  │  ┌──────────────────────────────┐    │
│  Tailwind CSS    │  │  │       API 层（路由）           │    │
│                  │  │  │  /parse    /download          │    │
│  ┌────────────┐  │  │  │  /subtitle /history          │    │
│  │ 页面组件    │  │  │  │  /payment                    │    │
│  │ - Home     │  │  │  └──────────┬───────────────────┘    │
│  │ - History  │  │  │             │                        │
│  │ - Pricing  │  │  │  ┌──────────▼───────────────────┐    │
│  └────────────┘  │  │  │       Service 层（业务逻辑）   │    │
│  ┌────────────┐  │  │  │                              │    │
│  │ 通用组件    │  │  │  │  video_service.py            │    │
│  │ - 输入框   │  │──│  │   └→ yt-dlp (视频解析/下载)   │    │
│  │ - 进度条   │  │  │  │                              │    │
│  │ - 卡片     │  │  │  │  subtitle_service.py         │    │
│  └────────────┘  │  │  │   └→ yt-dlp (字幕提取)       │    │
│  ┌────────────┐  │  │  │                              │    │
│  │ API调用层   │  │  │  │  history_service.py          │    │
│  │ - fetch    │  │  │  │   └→ SQLite (历史记录)       │    │
│  │ - 轮询     │  │  │  │                              │    │
│  └────────────┘  │  │  │  payment_service.py          │    │
│                  │  │  │   └→ 微信/支付宝 API          │    │
│  构建产物：       │  │  └──────────┬───────────────────┘    │
│  dist/ 静态文件   │  │             │                        │
└──────────────────┘  │  ┌──────────▼───────────────────┐    │
                      │  │       数据层                   │    │
                      │  │                              │    │
                      │  │  SQLite (history.db)          │    │
                      │  │   └→ 下载历史记录              │    │
                      │  │                              │    │
                      │  │  内存字典 (task_progress)     │    │
                      │  │   └→ 实时下载进度缓存          │    │
                      │  │                              │    │
                      │  │  临时文件 (downloads/)        │    │
                      │  │   └→ 视频文件+字幕文件         │    │
                      │  └──────────────────────────────┘    │
                      └──────────────────────────────────────┘
                                         │
                                         ▼
                      ┌──────────────────────────────────────┐
                      │       外部依赖                        │
                      │                                      │
                      │  yt-dlp ──→ 各视频平台 (1000+)        │
                      │    │         YouTube / Bilibili /     │
                      │    │         抖音 / Twitter / ...     │
                      │    │                                  │
                      │    └──→ ffmpeg (音视频合并)            │
                      │                                      │
                      │  微信支付API / 支付宝API               │
                      │                                      │
                      │  Claude API（AI功能，后续接入）         │
                      └──────────────────────────────────────┘
```

### 2.2 前端架构

```
┌─────────────────────────────────────────────────┐
│                  Vue 3 应用                      │
│              (Composition API)                   │
├─────────────────────────────────────────────────┤
│                                                  │
│  Router (Vue Router)                             │
│  ┌──────────┬──────────┬──────────┬───────────┐  │
│  │ /        │ /history │ /pricing │ /payment   │  │
│  │ Home.vue │ History  │ Pricing  │ Payment    │  │
│  │ (首页)    │ .vue     │ .vue     │ .vue       │  │
│  └──────────┴──────────┴──────────┴───────────┘  │
│                                                  │
│  Components (组件层)                              │
│  ┌─────────────────────────────────────────────┐│
│  │ Navbar          导航栏（响应式+汉堡菜单）      ││
│  │ HeroSection     核心输入区（URL输入+解析）     ││
│  │ VideoInfo       视频信息展示                   ││
│  │ QualitySelector 清晰度选择                     ││
│  │ SubtitleSelector 字幕选择                     ││
│  │ DownloadProgress 下载进度（实时轮询）          ││
│  │ HistoryList     历史记录列表                   ││
│  │ FeatureCards    功能展示                       ││
│  │ PlatformGrid    支持平台                       ││
│  │ PricingTable    定价对比                       ││
│  │ Footer          页脚                          ││
│  └─────────────────────────────────────────────┘│
│                                                  │
│  Composables (逻辑复用层)                         │
│  ┌─────────────────────────────────────────────┐│
│  │ useDownload.js  下载状态机                    ││
│  │   ├→ parse()      解析视频                    ││
│  │   ├→ download()   发起下载，获取task_id       ││
│  │   ├→ pollStatus() 轮询进度 (1s间隔)           ││
│  │   └→ saveFile()    保存文件到本地              ││
│  │                                              ││
│  │ useHistory.js   历史记录操作                   ││
│  │   ├→ fetchList()   获取历史列表(分页)          ││
│  │   ├→ deleteItem()  删除单条                   ││
│  │   └→ clearAll()    清空全部                   ││
│  └─────────────────────────────────────────────┘│
│                                                  │
│  API Layer (请求层)                               │
│  ┌─────────────────────────────────────────────┐│
│  │ api/index.js                                  ││
│  │   ├→ POST /api/parse                         ││
│  │   ├→ POST /api/download                      ││
│  │   ├→ GET  /api/download/status/{id}          ││
│  │   ├→ GET  /api/download/file/{id}            ││
│  │   ├→ GET  /api/subtitle/list                 ││
│  │   ├→ GET  /api/subtitle/download             ││
│  │   ├→ GET  /api/history                       ││
│  │   └→ DELETE /api/history/{id}                ││
│  └─────────────────────────────────────────────┘│
│                                                  │
│  Tailwind CSS (样式层)                            │
│  ┌─────────────────────────────────────────────┐│
│  │ 自定义主题：                                   ││
│  │   colors.apple-black: #1d1d1f                ││
│  │   colors.apple-gray: #f5f5f7                 ││
│  │   colors.apple-blue: #0071e3                 ││
│  │   fontFamily.sans: PingFang SC, system-ui    ││
│  │   borderRadius.card: 18px                    ││
│  │   backdropBlur.glass: blur(20px)             ││
│  └─────────────────────────────────────────────┘│
└─────────────────────────────────────────────────┘
```

### 2.3 后端架构

```
┌─────────────────────────────────────────────────┐
│                FastAPI 应用                       │
├─────────────────────────────────────────────────┤
│                                                  │
│  Middleware (中间件层)                            │
│  ┌─────────────────────────────────────────────┐│
│  │ CORS中间件        允许前端跨域请求             ││
│  │ 限流中间件        IP级限流，防止滥用            ││
│  │ 异常处理中间件     统一错误响应格式             ││
│  └─────────────────────────────────────────────┘│
│                                                  │
│  API Layer (路由层)                               │
│  ┌─────────────────────────────────────────────┐│
│  │ parse.py                                       ││
│  │   └→ POST /api/parse                          ││
│  │      请求 → video_service.parse_video()       ││
│  │      响应 ← 视频信息+格式列表+字幕列表          ││
│  │                                                ││
│  │ download.py                                    ││
│  │   ├→ POST /api/download                       ││
│  │   │   创建异步任务，返回task_id                 ││
│  │   ├→ GET /api/download/status/{task_id}       ││
│  │   │   从内存字典读取实时进度                     ││
│  │   └→ GET /api/download/file/{task_id}         ││
│  │      StreamingResponse 返回文件流              ││
│  │                                                ││
│  │ subtitle.py                                    ││
│  │   ├→ GET /api/subtitle/list?url=              ││
│  │   └→ GET /api/subtitle/download?url=&lang=    ││
│  │                                                ││
│  │ history.py                                     ││
│  │   ├→ GET    /api/history?page=&size=          ││
│  │   ├→ DELETE /api/history/{id}                 ││
│  │   └→ DELETE /api/history                      ││
│  └─────────────────────────────────────────────┘│
│                                                  │
│  Service Layer (业务逻辑层)                       │
│  ┌─────────────────────────────────────────────┐│
│  │ video_service.py                               ││
│  │   ├→ parse_video(url)                         ││
│  │   │   yt-dlp.extract_info(download=False)      ││
│  │   │   过滤格式，返回视频信息+格式列表            ││
│  │   │                                            ││
│  │   ├→ download_video(url, format_id, task_id)  ││
│  │   │   yt-dlp.download() + progress_hooks       ││
│  │   │   进度实时写入 task_progress[task_id]       ││
│  │   │   完成后写入 history_service                ││
│  │   │                                            ││
│  │   └→ get_download_url(url, format_id)         ││
│  │       部分平台支持直链获取                       ││
│  │                                                ││
│  │ subtitle_service.py                            ││
│  │   ├→ list_subtitles(url)                      ││
│  │   │   yt-dlp.extract_info → subtitles字段      ││
│  │   └→ download_subtitle(url, lang, fmt)        ││
│  │       yt-dlp writesubtitles配置                ││
│  │                                                ││
│  │ history_service.py                             ││
│  │   ├→ add_record(video_info)   写入SQLite       ││
│  │   ├→ get_list(page, size)     分页查询         ││
│  │   ├→ delete_record(id)        删除单条         ││
│  │   └→ clear_all()              清空全部         ││
│  └─────────────────────────────────────────────┘│
│                                                  │
│  Data Layer (数据层)                              │
│  ┌─────────────────────────────────────────────┐│
│  │ SQLite (history.db)                            ││
│  │   └→ downloads表: 下载历史记录                 ││
│  │                                                ││
│  │ 内存字典 (task_progress: dict)                 ││
│  │   └→ {task_id: {status, progress, speed, ...}}││
│  │   └→ 下载完成或超时后自动清理                    ││
│  │                                                ││
│  │ 文件系统                                       ││
│  │   ├→ downloads/  视频临时文件                   ││
│  │   └→ subtitles/  字幕临时文件                   ││
│  └─────────────────────────────────────────────┘│
└─────────────────────────────────────────────────┘
```

### 2.4 核心数据流

```
┌─ 视频下载完整数据流 ──────────────────────────────────────────┐
│                                                              │
│  用户                前端(Vue3)            后端(FastAPI)       │
│   │                    │                      │               │
│   │  粘贴URL           │                      │               │
│   │──────────────────→│                      │               │
│   │                    │  POST /api/parse     │               │
│   │                    │─────────────────────→│               │
│   │                    │                      │──→ yt-dlp     │
│   │                    │                      │    .extract   │
│   │                    │  ← 视频信息+格式列表   │    _info()    │
│   │  ← 展示视频信息     │                      │               │
│   │                    │                      │               │
│   │  选择清晰度+字幕    │                      │               │
│   │──────────────────→│                      │               │
│   │                    │  POST /api/download  │               │
│   │                    │─────────────────────→│               │
│   │                    │  ← task_id           │──→ 创建异步    │
│   │  ← 显示"下载中"    │                      │    下载任务    │
│   │                    │                      │               │
│   │                    │  GET /status/{id}    │   yt-dlp      │
│   │                    │─────────────────────→│   .download() │
│   │                    │  ← {67%, 2.5MB/s}   │   +progress   │
│   │  ← 更新进度条      │                      │   _hooks     │
│   │                    │                      │               │
│   │                    │  ...(每秒轮询)...     │──→ 写入       │
│   │                    │                      │    SQLite     │
│   │                    │  GET /status/{id}    │    历史       │
│   │                    │─────────────────────→│               │
│   │                    │  ← {status:"done"}   │               │
│   │  ← 显示"下载完成"  │                      │               │
│   │                    │                      │               │
│   │                    │  GET /file/{id}      │               │
│   │                    │─────────────────────→│               │
│   │                    │  ← 文件流(Streaming) │──→ 读取临时    │
│   │  ← 浏览器保存文件   │                      │    文件       │
│   │                    │                      │──→ 清理临时    │
│   │                    │                      │    文件       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## 三、技术栈

> 注：技术栈详情见上方「2.1 整体架构图」和「2.2 前端架构」

## 四、项目结构

```
video-downloader/
├── backend/                      # Python后端
│   ├── main.py                   # FastAPI应用入口
│   ├── config.py                 # 配置文件（端口、代理、限流等）
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py             # 路由注册
│   │   ├── parse.py              # 视频解析API
│   │   ├── download.py           # 视频下载API（流式传输）
│   │   ├── subtitle.py           # 字幕下载API
│   │   ├── history.py            # 历史记录API
│   │   └── payment.py            # 支付相关API
│   ├── services/
│   │   ├── __init__.py
│   │   ├── video_service.py      # yt-dlp封装（核心）
│   │   ├── subtitle_service.py   # 字幕提取服务
│   │   ├── history_service.py    # 历史记录服务（SQLite）
│   │   └── payment_service.py    # 支付逻辑封装
│   ├── database/
│   │   ├── __init__.py
│   │   ├── db.py                 # SQLite连接管理
│   │   └── models.py             # 数据模型（历史记录表）
│   ├── middleware/
│   │   ├── cors.py               # 跨域配置
│   │   └── rate_limit.py         # 限流中间件
│   ├── downloads/                # 临时下载目录（自动清理）
│   ├── subtitles/                # 字幕临时目录
│   └── requirements.txt          # Python依赖
│
├── frontend/                     # Vue 3前端
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── src/
│       ├── main.js               # Vue入口
│       ├── App.vue               # 根组件
│       ├── views/
│       │   ├── Home.vue          # 首页（主下载页）
│       │   ├── History.vue       # 下载历史记录页
│       │   ├── Pricing.vue       # 定价页
│       │   └── Payment.vue       # 支付页
│       ├── components/
│       │   ├── Navbar.vue        # 导航栏
│       │   ├── HeroSection.vue   # Hero区域（URL输入+下载）
│       │   ├── VideoInfo.vue     # 视频信息展示卡片
│       │   ├── QualitySelector.vue # 清晰度选择器
│       │   ├── DownloadProgress.vue # 下载进度条（实时进度+速度）
│       │   ├── SubtitleSelector.vue # 字幕选择与下载
│       │   ├── HistoryList.vue   # 历史记录列表组件
│       │   ├── FeatureCards.vue  # 功能展示卡片组
│       │   ├── PlatformGrid.vue  # 支持平台展示
│       │   ├── PricingTable.vue  # 定价对比表
│       │   └── Footer.vue        # 页脚
│       ├── api/
│       │   └── index.js          # 后端API调用封装
│       ├── composables/
│       │   ├── useDownload.js    # 下载逻辑复用（含进度追踪）
│       │   └── useHistory.js    # 历史记录逻辑复用
│       └── assets/
│           └── styles/
│               └── main.css      # Tailwind入口 + 自定义样式
│
└── PLAN.md                       # 本文档
```

## 五、API设计

### 4.1 视频解析

```
POST /api/parse
请求：{ "url": "https://www.youtube.com/watch?v=xxx" }
响应：{
  "title": "视频标题",
  "thumbnail": "缩略图URL",
  "duration": 120,
  "author": "作者",
  "platform": "youtube",
  "formats": [
    { "format_id": "137", "resolution": "1080p", "ext": "mp4", "filesize": 52428800 },
    { "format_id": "22",  "resolution": "720p",  "ext": "mp4", "filesize": 26214400 },
    { "format_id": "18",  "resolution": "360p",  "ext": "mp4", "filesize": 13107200 }
  ]
}
```

### 4.2 视频下载

```
POST /api/download
请求：{ "url": "https://...", "format_id": "137" }
响应：{ "task_id": "abc123" }

GET /api/download/status/{task_id}
响应：{
  "status": "downloading",     # downloading / merging / done / error
  "progress": 45.2,            # 百分比
  "speed": "2.5MB/s",          # 下载速度
  "downloaded": 13107200,      # 已下载字节数
  "total": 52428800,           # 总字节数（可能为null）
  "eta": 15                    # 预计剩余秒数
}

GET /api/download/file/{task_id}
响应：文件流（Content-Disposition: attachment）
```

### 4.3 字幕下载

```
GET /api/subtitle/list
请求参数：url=视频链接
响应：{
  "subtitles": [
    { "lang": "en", "name": "English", "auto_generated": false },
    { "lang": "zh", "name": "中文（简体）", "auto_generated": true }
  ]
}

GET /api/subtitle/download
请求参数：url=视频链接&lang=en&format=srt
响应：字幕文件流（.srt / .vtt / .ass）
```

### 4.4 历史记录

```
GET  /api/history              获取下载历史（分页）
请求参数：page=1&page_size=20
响应：{
  "total": 42,
  "items": [
    {
      "id": 1,
      "title": "视频标题",
      "thumbnail": "缩略图URL",
      "platform": "youtube",
      "url": "原始链接",
      "resolution": "1080p",
      "file_size": 52428800,
      "created_at": "2024-01-15 10:30:00"
    }
  ]
}

DELETE /api/history/{id}        删除单条记录
DELETE /api/history              清空全部历史
```

### 4.5 支付（后续实现）

```
POST /api/payment/create    创建支付订单
POST /api/payment/notify    支付回调通知
POST /api/payment/verify    验证支付状态
```

## 六、核心模块设计

### 5.1 yt-dlp 封装 (video_service.py)

```python
核心方法：
- parse_video(url)         → 解析视频信息，返回格式列表
- download_video(url, format_id, output_dir) → 下载视频到本地
- get_download_url(url, format_id)          → 获取直链（部分平台支持）
- list_subtitles(url)      → 列出可用字幕
- download_subtitle(url, lang, fmt)         → 下载指定语言字幕

关键配置：
- 代理设置（config.py）
- 超时控制
- 文件大小限制
- 进度回调（用于WebSocket推送）
```

### 5.2 下载流程（含进度追踪）

```
用户输入URL
    ↓
前端 POST /api/parse
    ↓
后端调用 yt-dlp extract_info(download=False)
    ↓
返回视频信息 + 可用格式列表 + 可用字幕列表
    ↓
用户选择清晰度 + 是否下载字幕
    ↓
前端 POST /api/download → 返回 task_id
    ↓
后端异步下载，yt-dlp progress_hooks 实时记录进度到内存字典
    ↓
前端轮询 GET /api/download/status/{task_id}（每秒1次）
    ↓  实时显示：进度百分比、下载速度、已下载/总大小、预计剩余时间
    ↓
下载完成 → 保存历史记录到 SQLite
    ↓
前端 GET /api/download/file/{task_id} → 获取文件流保存到本地
    ↓
自动清理临时文件
```

### 5.3 历史记录模块

```
SQLite 表结构：
- id: 主键
- title: 视频标题
- thumbnail: 缩略图URL
- platform: 来源平台
- source_url: 原始链接
- resolution: 下载清晰度
- file_size: 文件大小
- status: 状态（downloading/completed/failed）
- created_at: 创建时间

存储在 backend/history.db，无需额外部署数据库服务。
每次下载完成自动写入，前端可查看/删除历史。
```

## 七、前端页面设计（Apple风格）

### 6.1 设计规范

- **主色调**：黑(#1d1d1f) + 白(#f5f5f7) + 蓝色(#0071e3)作为CTA色
- **渐变**：深色Hero区域使用微妙的紫蓝渐变
- **字体**：系统字体栈 -apple-system, PingFang SC, sans-serif
- **圆角**：卡片18px，按钮12px
- **间距**：大量留白，模块间距80-120px
- **动画**：淡入+上移，时长0.6-0.8s，ease-out
- **毛玻璃**：导航栏背景 backdrop-filter: blur(20px)

### 6.2 首页布局

```
┌──────────────────────────────────────┐
│  [Logo]  时雨视频分析  功能  定价  登录  │  ← 毛玻璃导航栏
├──────────────────────────────────────┤
│                                      │
│     下载任何视频                      │  ← 超大标题 56px
│     只需一个链接                      │
│                                      │
│  ┌────────────────────────────┐      │
│  │ 粘贴视频链接...    [下载]   │      │  ← 核心输入区
│  └────────────────────────────┘      │
│                                      │
│  支持 YouTube、Bilibili、抖音...      │  ← 灰色副标题
│                                      │
├──────────────────────────────────────┤
│                                      │
│  ┌────────┐ ┌────────┐ ┌────────┐   │
│  │ 1000+  │ │ 4K高清  │ │ 批量   │   │  ← 功能卡片
│  │ 平台   │ │ 下载    │ │ 下载   │   │
│  └────────┘ └────────┘ └────────┘   │
│                                      │
├──────────────────────────────────────┤
│                                      │
│  [YouTube] [Bilibili] [抖音] [Twitter]│  ← 支持平台Logo墙
│  [微博]   [小红书] [快手]  [更多...]  │
│                                      │
├──────────────────────────────────────┤
│                                      │
│  免费版          │  Pro版            │  ← 定价对比
│  ¥0/月          │  ¥29/月          │
│  · 标清下载      │  · 4K高清下载     │
│  · 单个下载      │  · 批量下载       │
│                 │  · AI视频总结      │
│  [免费使用]      │  [立即订阅]       │
│                                      │
├──────────────────────────────────────┤
│  © 2024 时雨视频分析  关于  联系  隐私  │  ← 页脚
└──────────────────────────────────────┘
```

### 6.3 视频解析结果展示

```
用户输入URL点击下载后，输入区下方展开：

┌──────────────────────────────────────┐
│  ┌──────┐                            │
│  │ 缩略图 │  视频标题                 │
│  │      │  作者 · 3分20秒            │
│  └──────┘                            │
│                                      │
│  清晰度：                             │
│  ○ 1080p (50MB)  ● 720p (25MB)      │
│  ○ 480p (12MB)   ○ 360p (8MB)       │
│                                      │
│  字幕：                               │
│  ☑ 英文 (自动生成)  ☐ 中文 (自动生成) │
│  字幕格式：[SRT ▼]                    │
│                                      │
│  [开始下载]                           │
│                                      │
│  ┌─ 下载进度 ──────────────────────┐  │
│  │ [████████████░░░░] 67%          │  │
│  │ 速度: 2.5MB/s  已下载: 35/50MB  │  │
│  │ 预计剩余: 6秒                    │  │
│  └─────────────────────────────────┘  │
│                                      │
│  [下载完成 - 点击保存到本地]           │
└──────────────────────────────────────┘
```

### 6.4 历史记录页面

```
┌──────────────────────────────────────┐
│  下载历史                 [清空全部]  │
├──────────────────────────────────────┤
│  ┌──────┐                            │
│  │ 缩略图 │  视频标题1                │
│  │      │  YouTube · 1080p · 50MB    │
│  │      │  2024-01-15 10:30    [删除] │
│  └──────┘                            │
│  ┌──────┐                            │
│  │ 缩略图 │  视频标题2                │
│  │      │  Bilibili · 720p · 25MB    │
│  │      │  2024-01-14 18:22    [删除] │
│  └──────┘                            │
│  ...                                 │
│                                      │
│  [上一页]  1  2  3  ...  [下一页]     │
└──────────────────────────────────────┘
```

### 6.5 移动端布局适配

```
手机端（< 768px）：

┌────────────────────┐
│  [Logo]    [☰ 菜单] │  ← 汉堡菜单
├────────────────────┤
│                    │
│  下载任何视频       │  ← 标题 32px
│  只需一个链接       │
│                    │
│ ┌────────────────┐ │
│ │ 粘贴链接... [↓] │ │  ← 全宽输入
│ └────────────────┘ │
│                    │
│ ┌────────────────┐ │
│ │ ┌────┐         │ │
│ │ │图  │ 标题     │ │  ← 卡片全宽
│ │ └────┘ 信息     │ │  ← 纵向排列
│ │ [选择清晰度 ▼]  │ │
│ │ [进度条]        │ │
│ │ [下载]          │ │
│ └────────────────┘ │
│                    │
│ 功能卡片：         │
│ ┌────────────────┐ │  ← 单列纵向
│ │  1000+平台     │ │
│ └────────────────┘ │
│ ┌────────────────┐ │
│ │  4K高清        │ │
│ └────────────────┘ │
└────────────────────┘
```

## 八、开发步骤（优先级排序）

### 第一阶段：核心功能（优先）

#### 步骤1：后端骨架搭建
- [ ] 创建 backend/ 目录结构
- [ ] 安装 fastapi, uvicorn, yt-dlp, aiosqlite
- [ ] 实现 config.py（端口、代理等配置）
- [ ] 实现 CORS 中间件
- [ ] 实现 /api/parse 接口（调用 yt-dlp 解析视频信息）
- [ ] 实现 /api/download 接口（异步下载 + 返回task_id）
- [ ] 实现 /api/download/status/{task_id}（进度查询：百分比/速度/已下载/总大小/ETA）
- [ ] 实现 /api/download/file/{task_id}（文件流下载）
- [ ] yt-dlp progress_hooks 实时记录下载进度到内存
- [ ] 本地测试：用 curl/Postman 验证解析和下载功能

#### 步骤2：前端骨架搭建
- [ ] 创建 Vue 3 + Vite 项目
- [ ] 安装配置 Tailwind CSS
- [ ] 实现基础页面布局（导航栏 + URL输入框 + 下载按钮）
- [ ] 实现后端API调用逻辑（parse + download + status轮询）
- [ ] 实现视频信息展示（标题、缩略图、清晰度选择）
- [ ] 实现下载进度实时展示（进度条 + 百分比 + 速度 + ETA）
- [ ] 实现文件保存功能（下载完成后触发浏览器保存）
- [ ] 前后端联调，确保完整下载流程跑通

#### 步骤3：核心流程验证
- [ ] 测试多个平台：YouTube、Bilibili、抖音、Twitter
- [ ] 测试不同清晰度选择
- [ ] 测试大文件下载稳定性
- [ ] 测试下载进度显示准确性
- [ ] 测试手机端浏览器下载体验
- [ ] 修复发现的问题

### 第二阶段：UI美化 + 移动端优化

#### 步骤4：Apple风格UI + 移动端适配
- [ ] 导航栏：毛玻璃效果 + 移动端汉堡菜单
- [ ] Hero区域：大标题渐变 + 动画
- [ ] 功能卡片：圆角 + 阴影 + hover动画
- [ ] 支持平台展示：Logo网格
- [ ] 深色/浅色模式切换
- [ ] 移动端响应式适配（< 768px 单列布局）
- [ ] 触摸优化：按钮尺寸 >= 44px，间距适配手指操作
- [ ] 移动端下载进度展示优化（紧凑布局）
- [ ] 页面加载动画
- [ ] 输入框聚焦动画

### 第三阶段：扩展功能

#### 步骤5：字幕下载
- [ ] 后端：/api/subtitle/list（列出可用字幕）
- [ ] 后端：/api/subtitle/download（下载字幕文件，支持SRT/VTT/ASS）
- [ ] 前端：字幕选择器组件（SubtitleSelector）
- [ ] 解析结果中展示可用字幕列表
- [ ] 支持自动生成字幕和手动字幕

#### 步骤6：历史记录
- [ ] 后端：SQLite 数据库初始化 + 历史记录表
- [ ] 后端：下载完成自动写入历史记录
- [ ] 后端：GET /api/history（分页查询）
- [ ] 后端：DELETE /api/history/{id}、DELETE /api/history（删除/清空）
- [ ] 前端：History.vue 历史记录页面
- [ ] 前端：HistoryList.vue 组件（缩略图+标题+平台+清晰度+时间）
- [ ] 前端：分页导航 + 清空全部 + 单条删除
- [ ] 导航栏添加"历史记录"入口

### 第四阶段：商业化

#### 步骤7：定价与支付
- [ ] 定价页面（免费/付费对比表）
- [ ] 微信支付对接（H5支付/扫码支付）
- [ ] 支付宝对接
- [ ] 付费功能限制（高清下载需登录+付费）
- [ ] 用户会话管理（JWT Token）

### 第五阶段：AI功能（后续）

#### 步骤8：AI功能
- [ ] 视频AI总结（基于字幕/描述，调用Claude API）
- [ ] 字幕翻译（多语言互译）

## 九、部署方案

### 开发环境
```bash
# 后端
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev   # 默认 localhost:5173
```

### 生产部署
- 前端：npm run build → 静态文件由 FastAPI 托管或 Nginx 代理
- 后端：uvicorn + Gunicorn 或 Docker
- 域名 + SSL证书

## 十、风险与注意事项

1. **yt-dlp更新频繁**：需要定期更新，部分平台extractor可能失效
2. **版权风险**：需要在网站声明仅供个人学习使用
3. **带宽成本**：视频流式传输消耗带宽，考虑CDN或直链模式
4. **并发限制**：同时下载数量需要限制，防止服务器过载
5. **平台封锁**：部分平台（如YouTube）可能需要代理，需在config中配置
6. **ffmpeg依赖**：yt-dlp合并视频+音频需要系统安装ffmpeg
7. **移动端兼容**：iOS Safari对大文件下载有限制，需考虑替代方案（如直链跳转）
8. **字幕可用性**：并非所有视频都有字幕，需优雅处理无字幕情况
9. **历史记录存储**：SQLite适合单机部署，如需多实例部署需迁移到MySQL/PostgreSQL
