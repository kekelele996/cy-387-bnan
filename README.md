# RentFind 租房与物业报修平台

```bash
cp .env.example .env
docker compose up -d --build
```

RentFind 面向房东、租客和物业人员，提供房源发布、搜索预约、合同管理和报修跟踪能力。

## 项目主要功能

- 房源发布：小区、户型、面积、租金、押金、付款方式、照片和设施。
- 搜索筛选：区域、价格、户型、面积、设施，并支持列表和地图视图切换。
- 预约看房：租客选择时间段，房东确认后生成通知。
- 合同管理：生成租赁合同模板并记录租期、租金、双方信息和状态。
- 物业报修：提交故障类型、描述和照片，物业接单并更新进度。
- 角色区分：房东、租客、物业人员拥有不同工作台。

## 物业报修受理闭环

- 住户只能为名下有**有效租约**的房屋报修，否则接口返回 `LEASE_INVALID`。
- 同一房屋、同一故障类型存在未关闭工单时，新报修内容**合并到原工单**并留下合并轨迹。
- 系统按故障类型匹配物业人员**资质**，自动派单给**未完成工单数最少**的人员，并生成预计上门时间。
- 接单、转派、完工均校验**当前责任人与工单状态**；通过数据库条件更新保证并发操作只有一人成功。
- 跨租户访问、非责任人操作、已完工工单的重复操作都会被拒绝。
- 每次状态变化写入处理轨迹，住户端展示预计上门时间，物业台刷新后与接口数据一致。
- 创建、派单、转派、完工的每一步都在同一事务内执行，任一步失败全部回滚。

## 演示账号

首次启动后自动写入演示数据（`python manage.py seed_demo`，幂等）。页面右上角可切换账号。

| 姓名 | 手机号 | 角色 | 说明 |
| --- | --- | --- | --- |
| 陈晨 | 13900000001 | 租客 | 持有海棠公寓有效租约 |
| 林小 | 13900000002 | 租客 | 持有梧桐里有效租约 |
| 宋房东 | 13800000001 | 房东 | 房源发布人 |
| 张师傅 | 13700000001 | 物业人员 | 资质：水电、门锁 |
| 王师傅 | 13700000002 | 物业人员 | 资质：管道、家电 |
| 李师傅 | 13700000003 | 物业人员 | 资质：全部类型 |

## 快速启动方式

首次启动前执行：

```bash
cp .env.example .env
docker compose up -d --build
```

访问地址：http://localhost:18407

后端容器启动时自动执行数据库迁移并写入演示数据。

## 本地开发方式

```bash
cd backend && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
python manage.py migrate && python manage.py seed_demo && python manage.py runserver 0.0.0.0:8000
cd frontend && npm install && npm run dev
```

后端测试：

```bash
cd backend && python manage.py test
```

## 技术栈

| 模块 | 技术 |
| --- | --- |
| 前端 | Vue 3、TypeScript、Element Plus、Vite、高德地图 JS API |
| 后端 | Python、Django、Django REST Framework |
| 数据库 | PostgreSQL |
| 认证 | JWT |
| 部署 | Docker Compose、Nginx |

## 项目目录结构

```text
.
├── backend
│   ├── app
│   │   ├── apps            # users / properties / booking / contract / repair
│   │   ├── constants       # 枚举与错误码
│   │   ├── middleware
│   │   └── utils           # logger / jwt / 统一异常处理
│   ├── database
│   └── manage.py
├── frontend
│   ├── src
│   └── nginx.conf
├── docker-compose.yml
└── README.md
```

## 环境变量说明

| 变量 | 说明 |
| --- | --- |
| COMPOSE_PROJECT_NAME | Compose 项目名，固定为 rentfind |
| DATABASE_URL | Django 连接 PostgreSQL 的地址 |
| DJANGO_SECRET_KEY | Django 密钥 |
| AMAP_KEY | 高德地图 JS API Key |

## Docker 部署说明

Compose 顶层声明 `name: rentfind`，容器名带 `rentfind-` 前缀，数据库和媒体文件分别使用命名卷持久化，前端 Nginx 将 `/api` 代理到后端 `backend:8000`。

## License

MIT
