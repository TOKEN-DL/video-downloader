# 时雨视频分析

基于 Vue 3 + FastAPI + yt-dlp 构建的时雨视频分析网站，支持 1000+ 平台的视频解析与下载，集成 AI 视频总结功能。

## 功能特性

- **视频解析与下载** — 粘贴链接即可下载，支持 YouTube、Bilibili、抖音、Twitter 等 1000+ 平台
- **多清晰度选择** — 从 360p 到 4K，音视频完整合并
- **AI 视频总结** — 基于字幕内容自动生成结构化总结、思维导图、智能问答
- **同屏布局** — 视频信息与 AI 总结左右分栏，一屏掌握所有信息
- **移动端友好** — 响应式设计，手机浏览器直接使用
- **Apple 风格 UI** — 极简设计，毛玻璃效果，流畅动画

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Vite + Tailwind CSS |
| 后端 | FastAPI (Python) |
| 视频引擎 | yt-dlp |
| 音视频合并 | ffmpeg |
| AI 总结 | DeepSeek API |
| 思维导图 | markmap-lib + markmap-view |

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- ffmpeg（[安装方式](https://ffmpeg.org/download.html)）

### 启动后端

```bash
cd backend
pip install -r requirements.txt

# 配置环境变量（AI 功能必须）
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY

python main.py    # 启动在 http://0.0.0.0:8000
```

### 启动前端

```bash
cd frontend
npm install
npm run dev       # 启动在 http://localhost:5173，自动代理 API
```

### 环境变量配置（backend/.env）

```env
# AI 功能（必须配置，否则 AI 总结功能不可用）
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# 代理（可选）
PROXY=

# B站Cookie（可选，部分视频需要）
BILIBILI_SESSDATA=
```

## 已验证平台

| 平台 | 解析 | 下载 | AI 总结 |
|------|:----:|:----:|:-------:|
| Bilibili | ✅ | ✅ | ✅ |
| YouTube | ✅ | ✅ | ✅ |
| 抖音 | ✅ | ✅ | ✅ |
| Twitter/X | ✅ | ✅ | ✅ |

## 项目结构

```
video-downloader/
├── backend/
│   ├── main.py                # FastAPI 入口
│   ├── config.py              # 配置
│   ├── api/router.py          # API 路由
│   └── services/
│       ├── video_service.py   # yt-dlp 封装 + 抖音兜底
│       ├── douyin_service.py  # 抖音专用解析（无Cookie）
│       ├── subtitle_service.py# 字幕提取（带时间戳）
│       ├── ai_service.py      # AI 总结/对话/思维导图
│       ├── ai_prompts.py      # Prompt 模板
│       └── export_service.py  # PDF/Markdown 导出
├── frontend/
│   └── src/
│       ├── views/Home.vue           # 主页面（同屏布局）
│       ├── components/
│       │   ├── AiSummaryPanel.vue   # AI 总结面板（4 Tab）
│       │   ├── MindMapView.vue      # 思维导图
│       │   ├── AiChatPanel.vue      # AI 对话
│       │   └── ExportPanel.vue      # 导出
│       ├── composables/
│       │   ├── useDownload.js       # 下载状态管理
│       │   └── useSummarize.js      # AI 总结状态管理
│       └── api/index.js             # API 调用层
└── docs/                            # 项目文档
```

## API 概览

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/parse` | POST | 视频解析，返回标题/封面/格式列表 |
| `/api/download` | POST | 创建下载任务 |
| `/api/download/status/{id}` | GET | 查询下载进度 |
| `/api/download/file/{id}` | GET | 获取下载文件 |
| `/api/ai/summarize` | POST | 启动 AI 视频总结 |
| `/api/ai/summarize/status/{id}` | GET | 查询总结进度与结果 |
| `/api/ai/chat` | POST | AI 对话问答 |
| `/api/ai/export/{id}` | GET | 导出总结（PDF/Markdown） |
| `/api/proxy/image` | GET | 图片代理（绕过防盗链） |

## 生产部署

```bash
# 前端构建
cd frontend && npm run build

# Nginx 配置（推荐）
server {
    listen 443 ssl;
    server_name your-domain.com;

    location / {
        root /path/to/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
    }
}
```

## License

MIT
