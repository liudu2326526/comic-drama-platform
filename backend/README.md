# Comic Drama Backend (M1)

## 快速开始

```bash
# 1. 配置 .env(MySQL + Redis 连接信息已在 backend/.env,prod/dev 共用一份模板)
#    首次克隆仓库时:cp .env.example .env 并按实际环境填值

# 2. 虚拟环境(必须 Python 3.12+;3.13 当前与 pydantic-core 2.16 不兼容)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 3. 建库(若使用默认 comic_drama/comic_drama_test)
mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" \
  -e "CREATE DATABASE IF NOT EXISTS comic_drama DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
      CREATE DATABASE IF NOT EXISTS comic_drama_test DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 4. 迁移
alembic upgrade head

# 5. 启动 API
uvicorn app.main:app --reload --port 8000

# 6. 冒烟
./scripts/smoke_m1.sh
```

## 测试

```bash
pytest -v
```

需要 `MYSQL_DATABASE_TEST` 指向独立测试库;集成测试会 drop/create/truncate 该库。

## M1 范围

- 项目 CRUD(POST/GET/PATCH/DELETE /api/v1/projects)
- 阶段回退 POST /api/v1/projects/{id}/rollback
- 健康检查 /healthz /readyz
- Celery 应用装配(仅 ping 任务)
- MySQL projects/jobs 表

## M1 不包含

- 小说解析、分镜生成、角色/场景资产、镜头渲染、视频导出 — 见 M2 起
- 真实 AI 调用 — 见 M3a
- 鉴权 — MVP 范围外
- Docker 部署 — 见 Task 15(可选,后续里程碑)
