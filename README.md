# 星露谷物集图鉴
在《Stardew Valley》的世界里，每一件物品都有属于它的名字与故事。
本项目想把这种温柔带回现实——上传一张照片，系统为它生成像素形态、写下标签与描述，并记录下这一刻的时间。从此，平凡日常也能被珍藏，像素里藏着的是生活本身。

- 前端：React + TypeScript + Vite
- 后端：FastAPI + Pillow
- 存储：Supabase Storage + Supabase PostgREST（可本地兜底）
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

| 页面 | 路由 | 核心功能 | 截图占位 |
|---|---|---|---|
| 开场页 Intro | `/` | 信封+礼物互动、黑屏打字机分镜、可跳过、结束后进入主页 | `![intro](docs/screenshots/intro.png)` |
| 主页 Home | `/home` | 仅两个入口热点：`捕物`、`珍藏` | `![home](docs/screenshots/home.png)` |
| 捕物页 Capture | `/capture` | 上传、检测、生图、标签编辑、拖拽缩放、保存与下载 | `![capture](docs/screenshots/capture.png)` |
| 珍藏页 Collection | `/collection` | 作品分页列表、空态/错误态、放大弹窗、下载 | `![collection](docs/screenshots/collection.png)` |

### 2.1 开场页 `/`

- 信封背景 + 礼物按钮触发开场分镜。
- 黑屏打字机文字逐字播放，支持跳过。
- 开场时会暂停背景音乐，离开后恢复。

### 2.2 主页 `/home`

- 视觉上是单张背景大图，仅两个可点击热点区域：
- `捕物`：进入编辑工作台。
- `珍藏`：进入作品库。

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

### 2.4 珍藏页 `/collection`

- 调用 `/artworks?limit=&offset=` 分页拉取作品。
- 支持空态、加载态、错误态。
- 点击卡片打开大图弹窗查看。
- 支持下载单张作品。

### 2.5 全局音频能力

- 全局背景音乐组件随路由与开场状态自动管理。
- 左上角扬声器按钮可静音/取消静音。
- 点击按钮时带像素风音效反馈。

---

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
- 本地文件存储兜底（缺失 Supabase 配置时启用）

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

## 5. 配置说明（必须看）

### 5.1 环境变量加载顺序

后端会按以下顺序读取：

1. `backend/.env`
2. 根目录 `.env`

建议统一使用根目录 `.env` 管理，避免重复。

### 5.2 必要配置项

至少需要以下组之一：

- 方案 A（推荐）：Supabase + 模型服务
- 方案 B（开发兜底）：不配 Supabase，使用本地存储

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

## 7. 常用开发命令

### 前端

```powershell
cd frontend
npm run test
npm run lint
npm run build
```

### 后端

```powershell
cd backend
pytest
ruff check .
black .
```

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

---

## 9. 静态资源命名要求（避免中文乱码）

`frontend/public` 里下列图片名是代码硬编码引用的，需保持一致：

- `home-bg.png`
- `信封.png`
- `礼物.png`
- `捕物.png`
- `珍藏.png`
- `标签.png`
- `白天时钟.png`
- `夜晚时钟.png`
- `vite.svg`

如果文件名乱码，页面会出现背景/按钮缺图或时钟缺图。

---

## 10. 常见问题排查

### 10.1 保存到珍藏失败（502）

现象：`/save-artwork` 返回 `supabase_upload_failed`。

排查：

1. 检查 `SUPABASE_URL` 是否真实可解析。
2. 检查 key 是否与项目匹配。
3. 检查 bucket 与表是否存在。
4. 查看后端日志中的具体错误码（SSL、401、429、网络超时等）。

### 10.2 珍藏页加载失败（500）

现象：`/artworks` 返回 `supabase_list_failed`。

排查：

1. Supabase 连通性（DNS/TLS）是否正常。
2. `SUPABASE_TABLE` 是否存在且字段匹配。
3. key 权限是否允许读取表数据。

### 10.3 生图失败但页面继续可用

这是预期兜底行为：后端会自动返回本地像素化结果，前端会展示 fallback 提示。

---

## 11. 安全与协作建议

- 不要提交任何真实密钥到仓库。
- `.env` 仅本地保存，提交前检查 `git diff`。
- 第三方 API 调用统一走 `backend/app/clients/`，便于重试、限流和后续替换。

---

## 12. 版本说明与扩展建议

当前已实现核心闭环（上传 -> 检测 -> 编辑 -> 保存 -> 珍藏查看）。后续可扩展：

- 用户鉴权与多用户隔离
- 珍藏搜索/筛选/删除
- 更多风格模板与批量生成
- 生产环境部署（Nginx + HTTPS + CI/CD）
