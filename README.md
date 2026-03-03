# 星露谷物集图鉴
在《Stardew Valley》的世界里，每一件物品都有属于它的名字与故事。
本项目想把这种温柔带回现实——上传一张照片，系统为它生成像素形态、写下标签与描述，并记录下这一刻的时间。从此，平凡日常也能被珍藏，像素里藏着的是生活本身。

- 前端：React + TypeScript + Vite
- 后端：FastAPI + Pillow
- 存储：Supabase Storage 
- 模型能力：对象检测、命名、文案、生图

---

## 1. 项目简介

本项目围绕「星露谷风格」体验设计：

1. 用户上传或拖拽一张照片。
2. 系统自动检测多个物体，默认选中最大物体。
3. 用户编辑该物体标签（名称/类别/描述/数值/时间），并实时看到左侧预览变化。
4. 系统生成最终合成图并保存到珍藏。
5. 在珍藏页分页查看历史作品、放大查看、下载作品。

---

## 2. 页面与功能（逐页详解）

你可以把每个页面截图放到 `docs/screenshots/`，并替换下方占位图。
| 页面 | 路由 | 核心功能 |  
|---|---|---|
| 开场页 Intro | `/` | 信封+礼物互动、黑屏打字机分镜、可跳过、结束后进入主页 | 
| 主页 Home | `/home` | 仅两个入口热点：`捕物`、`珍藏` |
| 捕物页 Capture | `/capture` | 上传、检测、生图、标签编辑、拖拽缩放、保存与下载 |
| 珍藏页 Collection | `/collection` | 作品分页列表、空态/错误态、放大弹窗、下载 |

### 2.1 开场页 `/`

- 信封背景 + 礼物按钮触发开场分镜。
- 黑屏打字机文字逐字播放，支持跳过。
- 开场时会暂停背景音乐，离开后恢复。
<img width="1620" height="750" alt="3818bcc12cea07af2cc5452007c45b9a" src="https://github.com/user-attachments/assets/2fe12fcb-bfe4-4ace-9898-b4723cc97ee8" />
<img width="695" height="404" alt="image" src="https://github.com/user-attachments/assets/45b79568-8bc5-4d13-831e-3985bec1eb7f" />

### 2.2 主页 `/home`

- 视觉上是单张背景大图，仅两个可点击热点区域：
- `捕物`：进入编辑工作台。
- `珍藏`：进入作品库。
<img width="1546" height="854" alt="e580d416eb3a1e9f2c811b5e3b1655c8" src="https://github.com/user-attachments/assets/a8d6c812-df29-46df-8324-e66f2df06702" />

### 2.3 捕物页 `/capture`

#### A. 上传与预处理

- 支持文件选择与拖拽上传。
- 图片会自动按长边缩放到 720~1600 区间（目标约 1280）。
- 上传后并行执行：
- 物体检测（`/detect`）
- 像素风生图（`/generate-image`，失败时本地像素化兜底）

#### B. 识别与选择

- 自动展示检测框，可直接点击框切换当前物体。
- 右下物品栏同步展示识别结果。
- 超过 20 个物体时分页浏览（每页 20）。
- 默认选中最大面积物体。

#### C. 标签编辑（右侧面板）

- 名称：可手改，可调用「重写」（`/generate-label`）。
- 类别：可切换（菜品/食物/采集/家具/手工艺品/杂物）。
- 描述：可手改，可调用「重写」（`/generate-text`）。
- 数值：`Energy` / `Health`，支持步进。
- 时间：月/日/时/分可编辑，支持一键同步当前时间。

#### D. 画布交互（左侧预览）

- 标签卡可拖拽与缩放，边界约束避免拖出画布。
- 右上时间组件可拖拽与缩放。
- 预览内容与右侧编辑区实时联动。

#### E. 保存、下载、跳转

- 保存按钮调用 `/save-artwork`。
- 保存前会尝试用 `html2canvas` 先抓取前端合成预览；失败则回退后端合成。
- 保存成功后可直接下载作品，或跳转珍藏页。
<img width="1124" height="881" alt="62a28ba8e29607859976e5e9b8209424" src="https://github.com/user-attachments/assets/e9173eb1-f1d9-4535-b427-8c14e07a53f4" />

### 2.4 珍藏页 `/collection`

- 调用 `/artworks?limit=&offset=` 分页拉取作品。
- 支持空态、加载态、错误态。
- 点击卡片打开大图弹窗查看。
- 支持下载单张作品。
<img width="1190" height="650" alt="33233df41fd2f6dcac8753651a8bce45" src="https://github.com/user-attachments/assets/ecb277c0-83c4-4f21-8a7f-2262915ff0ec" />
<img width="1158" height="821" alt="8b2c8f8ac23ba5b36b9eaea51ad7cd3b" src="https://github.com/user-attachments/assets/f2fb2d3a-59ae-4678-83e4-2b641af71952" />

## 3. 技术栈与外部能力

### 3.1 前端

- React 19 + TypeScript + Vite
- React Router（页面路由）
- Zustand（捕物状态、音频状态）
- html2canvas（前端预览合成抓图）

### 3.2 后端

- FastAPI（API 服务）
- Pydantic v2（请求/响应契约）
- Pillow（标签与时间组件图像合成）
- httpx（外部模型/API 调用）

### 3.3 数据与存储

- Supabase Storage：存储最终合成图
- Supabase PostgREST：作品记录读写（`artworks` 表）


### 3.4 外部模型与 API（重点）

| 能力 | 优先方案 | 备选/兜底 | 对应接口 |
|---|---|---|---|
| 对象检测 | 阿里云 ObjectDet（可配 OSS 公网图） | Azure Computer Vision；再兜底固定框 | `POST /detect` |
| 中文命名 | Gemini 多模态 或 Qwen-VL | 失败保留原标签 | `POST /generate-label` |
| 文案生成 | 通用 LLM API 或 Qwen | 模板文案兜底 | `POST /generate-text` |
| 像素生图 | Qwen Image Edit / 豆包 Seedream / Gemini | 本地像素化兜底 | `POST /generate-image` |
| 作品保存 | Supabase（Storage + 表记录） | 本地存储（非 Supabase 模式） | `POST /save-artwork` |

---

## 4. 后端 API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 健康检查 |
| POST | `/detect` | 物体检测 |
| POST | `/generate-label` | 命名（中文物品名） |
| POST | `/generate-text` | 生成描述文案 |
| POST | `/generate-image` | 生成像素风图 |
| POST | `/save-artwork` | 保存作品 |
| GET | `/artworks` | 分页查询作品 |
| GET | `/config/storage` | 当前存储模式（supabase/local） |
| GET | `/config/image-gen` | 生图配置状态与预期模式 |

---

## 5. 配置说明

### 5.1 环境变量加载顺序

后端会按以下顺序读取：

1. `backend/.env`
2. 根目录 `.env`

建议统一使用根目录 `.env` 管理，避免重复。

### 5.2 必要配置项

Supabase + 模型服务

核心变量参考 `backend/.env.example`：

- Supabase：`SUPABASE_URL`、`SUPABASE_KEY`、`SUPABASE_BUCKET`、`SUPABASE_TABLE`
- 检测：`ALIYUN_*` 或 `AZURE_CV_*`
- 生图：`IMAGE_GEN_ENDPOINT`、`IMAGE_GEN_KEY`、`IMAGE_GEN_MODEL`
- 文案：`TEXT_GEN_PROVIDER`、`TEXT_GEN_ENDPOINT`、`TEXT_GEN_KEY`、`TEXT_GEN_MODEL`
- 命名：`LABEL_GEN_PROVIDER`、`LABEL_GEN_ENDPOINT`、`LABEL_GEN_KEY`、`LABEL_GEN_MODEL`
- OSS（部分模型链路需要公网图）：`OSS_*`

前端变量：

- `VITE_API_BASE`（默认 `http://127.0.0.1:8001`）

### 5.3 Supabase 必须正确配置

若你要求「必须走 Supabase」，请确认：

1. `SUPABASE_URL` 是 Dashboard 的真实 Project URL：
   `https://<project-ref>.supabase.co`
2. `SUPABASE_KEY` 与该项目匹配（建议 service role key）。
3. `SUPABASE_BUCKET` 已存在且可写。
4. `SUPABASE_TABLE`（默认 `artworks`）存在并可插入/查询。

---

## 6. 本地启动（Windows PowerShell）

### 6.1 前端

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 4173
```

访问：`http://127.0.0.1:4173`

### 6.2 后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

健康检查：`http://127.0.0.1:8001/health`

---


## 8. 目录结构

```text
.
├─ frontend/
│  ├─ src/
│  │  ├─ pages/           # Intro/Home/Capture/Collection
│  │  ├─ components/      # 背景音乐、扬声器开关
│  │  ├─ state/           # Zustand 状态
│  │  └─ api/             # 前端 API 调用封装
│  └─ public/             # 静态资源（背景/图标/音乐/字体）
├─ backend/
│  ├─ app/
│  │  ├─ routers/         # API 路由
│  │  ├─ services/        # 业务编排
│  │  ├─ clients/         # 第三方服务客户端
│  │  ├─ models/          # Pydantic 模型
│  │  └─ tests/           # 后端测试
│  └─ requirements.txt
└─ memory_bank/           # PRD、架构、进度、技术说明
```




