# TruthCast Web

`web/` 是 TruthCast 的前端控制台，基于 Next.js 16、React 19、Tailwind CSS 4 和 shadcn/ui 构建，负责承载事实核查、舆情预演、公关响应、历史回放、对话工作台与实时监测台等完整交互流程。

## 功能概览

- 首页：输入待分析文本，启动全链路核查
- 结果页：查看风险初判、主张、证据链和综合报告
- 预演页：按阶段流式展示舆情预演结果
- 公关响应页：生成澄清稿、FAQ 和多平台话术
- 历史页：查看历史任务、详情、反馈与任务回放
- 对话工作台：基于后端编排进行会话式分析与追问
- 实时监测台：查看监测窗口、订阅规则、预警清单与分析结果

## 技术栈

- Next.js 16 (App Router)
- React 19
- Tailwind CSS 4
- shadcn/ui
- Zustand
- SWR
- Axios
- ECharts

## 本地启动

在项目根目录下先确保后端可用，再启动前端：

```bash
cd web
npm install
cp .env.example .env.local
npm run dev
```

默认访问地址：

- 前端：`http://localhost:3000`
- 后端：`http://127.0.0.1:8000`

## 环境变量

前端当前只依赖一个公开环境变量：

```ini
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
```

它用于指定后端 API 地址，默认值也会回退到 `http://127.0.0.1:8000`。

## 目录结构

```text
web/
├── src/
│   ├── app/                 # 页面路由
│   ├── components/          # 布局与业务组件
│   ├── hooks/               # 自定义 hooks
│   ├── lib/                 # 工具函数与 i18n 映射
│   ├── services/            # API 请求封装
│   ├── stores/              # Zustand 状态管理
│   └── types/               # TypeScript 类型定义
├── public/                  # 静态资源
└── .env.example             # 前端环境变量示例
```

## 主要页面

- `/`：分析输入主页
- `/result`：核查结果页
- `/simulation`：舆情预演页
- `/content`：公关响应页
- `/history`：历史记录页
- `/chat`：对话工作台
- `/monitor`：实时监测台
- `/monitor/subscriptions`：订阅编排页
- `/monitor/alerts`：预警清单页

## 构建与检查

```bash
npm run build
npm run lint
```

## 说明

- 页面文案默认以中文为主。
- 前端会对部分后端英文标签做中文映射。
- 流式预演、历史回放、错误重试等能力依赖后端对应接口正常工作。
