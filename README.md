# 监管报送项目

本目录作为“监管报送变更影响分析与工单助手”的统一工作目录。当前项目主线是：面向 1104、EAST、客户风险、一表通等监管报送体系，将监管公告、表样、填报说明、会议纪要中的变更要求，定位到具体报送对象、报送项、指标口径、报送系统字段和源系统血缘，生成可复核的影响分析和分类型工单草稿，并将人工确认经验沉淀为可复用知识资产。

一阶段以 1104 非现场监管报表为落脚点，但底层设计保持通用，后续可扩展到 EAST、客户风险和一表通。

## 目录结构

| 目录 | 用途 |
|---|---|
| `frontend-prototype/` | 前端高保真静态原型，包含 HTML、CSS、JS |
| `frontend/` | Vue 3 + Vite + TypeScript 前端工程 |
| `backend/` | Python FastAPI 后端，承载材料上传、任务、变更证据、报送对象定位、血缘影响分析和工单草稿接口 |
| `assets/screenshots/` | 原型页面截图、设计预览图、后续视觉资产 |
| `file/` | 原始监管样本和测试监管材料 |
| `docs/` | 项目过程文档、组件梳理、计划与设计说明 |

## 当前原型

入口文件：

```text
frontend-prototype/index.html
```

可直接用浏览器打开：

```text
file:///Users/jiangqiuping/webproject/监管报送项目/frontend-prototype/index.html
```

已覆盖页面：

- 工作台首页
- 发文任务
- 监管发文加工流程
- 规则资产
- 数据模型与映射
- 复核工单

支持 URL 参数直达页面：

```text
index.html?page=dashboard
index.html?page=documents
index.html?page=task
index.html?page=task&tab=impact
index.html?page=library
index.html?page=metadata
index.html?page=review
```

## 当前文档

| 文件 | 说明 |
|---|---|
| `docs/regulatory-report-lineage-impact-design.md` | 监管报送指标血缘影响分析设计，定义 1104 到 EAST/一表通可复用的通用主线 |
| `docs/1104-report-introduction.md` | 1104 非现场监管报表介绍和一表通背景下的一阶段落脚点说明 |
| `docs/frontend-component-map.md` | Vue 前端技术栈、页面组件、API 契约和联调闭环说明 |
| `docs/regulatory-workflow-implementation.md` | 监管报送变更五步流程化加工、报送对象定位、血缘影响判定和前后端改造设计 |

## 后续约定

- 新增原始监管材料：优先按报送体系独立建目录，例如 `一表通/`、`1104/`、`EAST/`。`file/` 仅保留测试样本或临时资料，不再存放旧主线方案文档。
- 新增页面原型：优先放入 `frontend-prototype/`。
- 新增 Vue 前端代码：优先放入 `frontend/`。
- 新增后端代码：优先放入 `backend/`。
- 新增截图、视觉稿、导出图片：优先放入 `assets/screenshots/`。
- 新增正式方案文档：优先放入 `docs/`。

## 后端启动

后端目录：

```text
backend/
```

启动命令：

```bash
cd /Users/jiangqiuping/webproject/监管报送项目/backend
uv sync
uv run uvicorn app.main:app --reload
```

默认服务地址：

```text
http://127.0.0.1:8000
```

当前后端数据库已切换到本地 MySQL：

```text
Database: reg_reporting
Username: reg_user
Password: reg_pass_123
Host: localhost
Port: 3306
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

当前后端主线已切换为 1104 资金同业报送目录、指标字段、数据字段血缘和工单草稿生成。前端”上传发文 -> 创建任务 -> 影响分析 -> 工单草稿”的流程形态保持不变，后端判断逻辑不再依赖旧样板业务对象库。

数据库表详细说明见 [backend/README.md](backend/README.md#数据库表清单共-22-张)。

监管报送目录接口：

| 方法 | 接口 | 功能 |
|---|---|---|
| `POST` | `/api/reporting/seed-1104` | 初始化一期 1104 资金同业报表目录、指标项、数据字段和血缘样板 |
| `GET` | `/api/reporting/objects?reporting_system_code=1104` | 查询 1104 报表对象 |
| `GET` | `/api/reporting/items?reporting_system_code=1104` | 查询 1104 指标字段 |
| `GET` | `/api/reporting/items/{item_code}/lineage` | 查询报送指标到报送字段、源字段、维度字段的血缘 |

任务流程接口：

| 方法 | 接口 | 功能 |
|---|---|---|
| `POST` | `/api/documents/upload` | 上传监管材料并解析正文 |
| `POST` | `/api/documents/{document_id}/profile` | 基于报送目录和血缘上下文生成文档级任务画像 |
| `POST` | `/api/tasks/from-document/{document_id}` | 从监管材料创建加工任务 |
| `POST` | `/api/tasks/{task_id}/analyze-impact` | 识别 1104 报送变更并根据血缘生成影响项 |
| `POST` | `/api/tasks/{task_id}/generate-ticket` | 生成 1104 资金同业影响分析工单草稿 |
| `GET` | `/api/tasks/{task_id}/workflow` | 聚合返回任务、文档、候选报送项、血缘候选、影响项和工单草稿 |

## 前端启动

前端目录：

```text
frontend/
```

启动命令：

```bash
cd /Users/jiangqiuping/webproject/监管报送项目/frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

默认访问地址：

```text
http://127.0.0.1:5173/
```
