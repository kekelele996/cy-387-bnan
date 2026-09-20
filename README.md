# RentFind 租房与物业报修平台

```bash
cp .env.example .env
docker compose up -d --build
```

RentFind 面向房东、租客和物业人员，提供房源发布、搜索预约、合同管理，以及**完整的物业报修受理闭环**：有效租约校验、同类故障工单合并、资质匹配派单、乐观锁并发控制、处理轨迹全程留痕。

## 项目主要功能

- 房源发布：小区、户型、面积、租金、押金、付款方式、照片和设施。
- 搜索筛选：区域、价格、户型、面积、设施，并支持列表和地图视图切换。
- 预约看房：租客选择时间段，房东确认后生成通知。
- 合同管理：生成租赁合同模板并记录租期、租金、双方信息和状态。
- **物业报修闭环**：
  - 住户只能为**名下持有有效租约**的房屋报修，租约到期/无租约一律拒绝；
  - 同一房屋、同一故障类型存在未关闭工单时，新报修**自动合并到原工单**并补充轨迹；
  - 物业人员按故障类型匹配**处理资质**，系统在合格人员中选**未完成工单数最少者**派单；
  - 接单、转派、完工均校验**当前责任人与工单状态**；转派还校验新责任人资质；
  - 并发操作通过「状态 + 责任人 + version」条件 UPDATE 保证**只有一次成功**，跨租户、已完成工单操作返回 4xx；
  - 每次状态变化（提交/接单/转派/完工）都写入处理轨迹，任一步失败整笔事务回滚；
  - 住户端展示**预计上门时间**与完整轨迹；物业工作台筛选、刷新后数据与接口完全一致。
- 角色区分：房东、租客、物业人员拥有不同工作台，JWT 登录鉴权。

## 快速启动方式（Docker Compose）

首次启动前执行：

```bash
cp .env.example .env
docker compose up -d --build
```

容器启动时后端会自动执行数据库迁移并写入演示数据（可用 `SEED_DEMO=false` 关闭）。

访问地址：http://localhost:18407

演示账号（密码均为 `demo1234`）：

| 账号 | 角色 | 说明 |
| --- | --- | --- |
| zhangsan | 租客 | 对「海棠公寓」持有生效租约，可正常报修 |
| lisi | 租客 | 租约已到期，报修会被拒绝 |
| shui | 物业人员 | 水电资质 |
| suo | 物业人员 | 门锁资质 |
| guan | 物业人员 | 管道资质 |
| jia | 物业人员 | 家电 + 水电资质 |

## 本地开发方式

```bash
# 后端
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 0.0.0.0:8000

# 前端
cd frontend
npm install
npm run dev
```

后端测试（含并发、合并、回滚、跨租户拒绝等 14 个用例）：

```bash
cd backend
python manage.py test app.apps.repair
```

## 报修闭环接口

| 方法与路径 | 角色 | 说明 |
| --- | --- | --- |
| `POST /api/auth/login/` | 公开 | JWT 登录 |
| `POST /api/auth/register/` | 公开 | 注册（物业人员必须选择资质） |
| `GET  /api/repairs/my-houses/` | 租客 | 名下有有效租约、可报修的房屋 |
| `GET  /api/repairs/` | 租客 | 我的工单（预计上门时间 + 轨迹） |
| `POST /api/repairs/` | 租客 | 提交报修（支持照片，自动合并） |
| `GET  /api/repairs/desk/` | 物业 | 工单池，可按状态/故障类型筛选 |
| `POST /api/repairs/<id>/accept/` | 物业 | 接单（自动匹配最少负载合格人员，可带预计上门时间） |
| `POST /api/repairs/<id>/transfer/` | 物业 | 转派（仅当前责任人，校验新责任人资质） |
| `POST /api/repairs/<id>/complete/` | 物业 | 完工（仅当前责任人） |

统一响应信封：`{ "success": true, "data": ..., "error": null }`；失败时 `error.code` 为错误码（如 `NO_ACTIVE_LEASE`、`STAFF_NOT_QUALIFIED`、`NOT_CURRENT_OWNER`、`TICKET_COMPLETED`、`CONFLICT`）。

## 并发与一致性设计

- **工单合并**：数据库层建立部分唯一索引 `uniq_open_ticket_per_house_fault`（同一房屋+故障类型只允许一个未关闭工单），服务层在事务内先查后插并捕获唯一约束冲突，并发提交时一笔新建、另一笔合并。
- **状态流转**：接单/转派/完工均在单事务内完成，最终更新使用带 `status / assignee / version` 条件的 `UPDATE ... version = version + 1`，匹配 0 行即按最新状态返回精确业务错误，天然防止重复接单与并发双写。
- **回滚保证**：状态更新与轨迹写入同一事务，轨迹写入失败则状态、责任人、版本全部回滚。
- **派单公平性**：合格资质人员按当前未完成工单数升序、同负载按入职先后排序。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| 前端 | Vue 3、TypeScript、Element Plus、Vite、Vue Router |
| 后端 | Python、Django、Django REST Framework |
| 数据库 | PostgreSQL（本地开发可用 SQLite） |
| 认证 | JWT（djangorestframework-simplejwt） |
| 部署 | Docker Compose、Nginx |

## 项目目录结构

```text
.
├── backend
│   ├── app
│   │   ├── apps
│   │   │   ├── users/          # 用户、角色、资质、JWT
│   │   │   ├── properties/     # 房屋、有效租约模型与查询服务
│   │   │   ├── repair/         # 报修工单、轨迹、领域服务、接口、测试
│   │   │   ├── booking/
│   │   │   └── contract/
│   │   ├── constants/          # enums.py 枚举、errors.py 错误码
│   │   ├── middleware/
│   │   ├── utils/              # logger、统一异常处理
│   │   ├── settings.py
│   │   └── urls.py
│   ├── database/init.sql
│   ├── entrypoint.sh           # 容器启动：迁移 + 种子数据
│   └── manage.py
├── frontend
│   └── src
│       ├── api/                # 请求封装与报修接口
│       ├── components/         # 工单轨迹等组件
│       ├── constants/
│       ├── stores/
│       ├── types/
│       └── views/              # 登录、住户台、物业台
├── docker-compose.yml
├── .env.example
└── README.md
```

## 环境变量说明

| 变量 | 说明 |
| --- | --- |
| COMPOSE_PROJECT_NAME | Compose 项目名，固定为 rentfind |
| POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD | 数据库名、账号、密码 |
| DATABASE_URL | Django 连接 PostgreSQL 的地址 |
| DJANGO_SECRET_KEY | Django 密钥 |
| DJANGO_DEBUG | 是否开启调试 |
| SEED_DEMO | 容器启动时是否写入演示数据，默认 true |
| AMAP_KEY | 高德地图 JS API Key |

## Docker 部署说明

Compose 顶层声明 `name: rentfind`，容器名带 `rentfind-` 前缀；PostgreSQL 配置 healthcheck，后端等待数据库健康后启动；数据库和媒体文件使用命名卷持久化；前端 Nginx 将 `/api` 与 `/media` 反向代理到 `backend:8000`。端口：前端 18407、后端 19407。

## License

MIT
