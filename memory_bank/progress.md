# 用于记录已完成步骤

- 完成前端初始化（步骤 1）：在仓库根目录创建 `frontend`（Vite React TS 模板），运行 `npm install` 安装依赖，补充缺失的 `@typescript-eslint/tsconfig-utils` 以修复 ESLint，`npm run lint` 通过。暂未开始步骤 2。
- 完成路由与骨架占位（步骤 2）：引入 React Router，新建主页/捕物/珍藏三页骨架；捕物页按左预览约 60% + 右编辑约 40% 布局并预留底部物品栏，珍藏页提供网格占位。新增依赖 `react-router-dom` 并已执行 `npm install` 生成 `package-lock.json`。验证：手动访问 `npm run dev`，仅“捕物/珍藏”可点，三页骨架可切换，比例已大致符合要求（细节尺寸后续再调，已记录为 TODO）。
- 完成全局状态模型（步骤 3）：在 `frontend/src/state/capture-store.ts` 使用 Zustand 定义上传文件、预览 URL、检测框、选中 ID、标签草稿（名称/类别/描述/能量/生命/时间/标签位置/缩放）与保存状态；`setDetectionBoxes` 默认选中面积最大框并为每个框建立草稿；`selectBox` 仅接受有效 ID。新增 Vitest + jsdom 作为测试栈，`npm run test -- run` 通过（验证默认最大面积选中、切换选中 ID），`npm run lint` 通过。
- 完成捕物页静态 UI（步骤 4）：在 `frontend/src/pages/Capture.tsx` 构建左预览/右编辑/下物品栏布局，左侧提供空态木框、识别框层、标签层、时间与金币占位，右侧表单统一对齐并为名称/描述/时间添加更新/重生/同步按钮占位（移除操作提示区），底部新增更换/保存按钮的像素风样式，布局比例调整为约 1.6/1.2 并加长编辑面板高度。验证：`npm run lint`、`npm run test -- run` 均通过。
- 捕物页风格化（步骤 5 持续迭代）：捕物页面换为 2D 像素 RPG 木质室内风，外层深色木质背景，画布嵌入羊皮纸，框选/标签改为像素风深色小标签，表单改为纸张块+木质按钮，物品栏木框化，数值/文字颜色加深；验证通过 `npm run lint`、`npm run test -- --run`。
- 首页按钮交互：主页捕物/珍藏木质按钮增加像素风交互（hover 轻微上浮+亮度提升，按下下压并变暗，去掉黑色阴影和外圈光晕），保持等比例缩放；验证通过 `npm run lint`、`npm run test -- --run`。
- 珍藏页风格化：珍藏页面改为木墙背景 + 木牌标题，卡片为木框+羊皮纸，编号角标，hover 上移/按下收缩的像素硬阴影，网格整齐排列；验证通过 `npm run lint`、`npm run test -- --run`。
- 完成前端像素预览与交互基础（步骤 6）：上传后等比压缩到 720–1600px（目标 1280px），调用 Nano Banana mock 生成像素预览，失败回退本地像素滤镜；自动生成 3–5 个 mock 检测框，物品栏/画布框/表单三联动；标签改为与示例一致的橙色 Stardew 风卡片（名称/类别/描述/能量/生命实时填入，图标/分隔线还原），标签可拖拽缩放不越界；时间支持月/日/时/分编辑和一键同步，显示分两行并驱动表盘指针，能量/生命 0–200 夹紧；左右区域保持 60%/40%，物品栏展示缩略图与编号，保存按钮在可保存时启用。验证：`npm run lint`、`npm run test -- --run` 通过，手动上传/拖拽/切换框/同步时间/拖拽标签均实时更新。
- 后端基础与生成管线（步骤 7）：新增 `backend/` FastAPI 服务，暴露 `/health` `/detect` `/generate-text` `/generate-image` `/save-artwork` `/artworks` 契约；封装阿里云 ObjectDet（优先）/Azure 客户端（401/429/超时错误码映射）+ 稳定兜底框生成，文案生成为独立 LLM（无密钥用星露谷模板兜底），生图服务支持远程模型（如 Gemini 3 Pro Image Preview，失败时本地像素化兜底），Pillow 叠加橙色标签/时间表盘/金币 88888888，并按输入生成稳定哈希文件名；本地存储默认启用，Supabase 客户端保留。验证：`python3 -m pytest backend/app/tests` 覆盖健康检查、检测错误映射、文案兜底、生图兜底、合成哈希一致与列表返回，全数通过。
- 前后端联调与保存/列表流程（步骤 8）：前端新增 `src/api/client.ts` 使用 `VITE_API_BASE` 调用后端；捕物页接入阿里云检测/后端生图/文案生成，检测 0 框空态提示，>20 时分页，生成描述可重试兜底，保存按钮防连点并调用后端 `/save-artwork`，成功提示“已放入珍藏”；珍藏页改为从 `/artworks` 拉取分页数据（每页 12 条），支持翻页与大图查看，空态/错误态提示。验证：后端 `python3 -m pytest backend/app/tests` 通过；前端未跑自动化（待你本地 `npm run lint`/`npm run test`/`npm run dev` 验证）。
- 阿里云检测接入 OSS（步骤 8 扩展）：新增 `backend/app/clients/oss_client.py`（oss2 上传），检测流程改为先上传到 OSS 再调用 ObjectDet；`DetectObjectRequest` 修正为 `image_url` 参数，`.env.example` 增加 OSS 配置项，后端依赖加入 `oss2`。验证待你本地配置 OSS 后复测 `/detect`。
- 修复阿里云 ObjectDet 解析：`DetectObjectResponseBodyDataElements` 使用 `boxes` 列表（x,y,w,h），修正解析以避免 `box` 属性错误导致回退。
- 新增多模态命名：`backend/app/clients/label_client.py` 接入 Gemini 多模态生成中文物体名，`detection_service` 在检测后裁剪图片并回写标签；`config.py` 与 `.env.example` 添加 `LABEL_GEN_*` 配置。
- 取名按钮接入多模态命名：新增 `/generate-label` 路由与 `label_service`，前端“取名”改为裁剪图像调用命名模型并同步刷新描述；取名失败回退兜底名并自动生成描述。
