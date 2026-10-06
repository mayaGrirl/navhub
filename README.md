# NEXA

双语导航站。页面在 `/`，接口在 `/api`，同一域名用反向代理分开。默认语言是英文，可切到中文。

## 能做什么

- 顶部栏目来自数据库。当前对外栏目：每日资讯、AI 工具、跨境电商、午夜媒体、TG 群。
- 点进一个栏目后，该栏目下的链接在同一页按分类排开。左侧分类只负责跳到对应区块。
- 每日资讯只保留当天内容，中文和英文来源放在同一类话题里。旁边是 GitHub 增量榜和总星标榜，各显示前 10。
- 午夜媒体整栏是 18+，进入前需要确认年龄。链接都是外站，站内不播放视频。
- 注册用户可以提交链接，每月有次数上限。免费和 VIP 的上限不同，VIP 由管理员开通 30 天，没有支付接口。
- 登录、注册和关于我们在同一页：左边是介绍，右边是表单。注册需要把滑块拖到最右侧。
- 登录后顶部入口是个人中心，可以改昵称和密码，也可以提交链接。图标可以填完整图片地址，或从本机上传。
- 广告位在后台按页面位置配置。没有内容的广告位不显示。
- 站内搜索在顶栏和页脚。顶栏还有一组外站搜索引擎。
- 管理后台是随机路径，并且要先完成验证器。未登录或不是管理员访问该地址会看到 404。

会员视频解析不在这个项目里。

## 技术栈

- 前端：Vue 3、Vite、Vue Router、Pinia、vue-i18n、Element Plus
- 后端：FastAPI、SQLAlchemy、MySQL、Redis、PyOTP
- 可选：`proxy-pool/` 是独立的代理池。只有设置了 `PROXY_POOL_URL` 时，抓取才会用它。

## 目录

```
backend/          接口、种子数据、资讯和目录任务
frontend/         Vue 站点
proxy-pool/       可选代理池
deploy/nginx.conf 同域反代示例
docker-compose.yml
```

主要页面：

| 路径 | 内容 |
| --- | --- |
| `/` | 首页 |
| `/about` `/login` `/register` | 介绍和登录或注册 |
| `/submit` | 个人中心，需登录 |
| `/contact` | 联系方式 |
| `/<后台路径>` | 管理后台 |

## 初始化部署

需要本机已有：

- Python 3.11 及以上
- Node.js 20 及以上
- MySQL 8，字符集 `utf8mb4`
- Redis

建库（空库起步时）：

```sql
CREATE DATABASE navhub CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'nav'@'%' IDENTIFIED BY 'navpass';
GRANT ALL ON navhub.* TO 'nav'@'%';
```

接口第一次启动会建表，并写入栏目、等级和目录种子。管理员账号来自下面的 `.env`。

仓库里的 `backups/nav-local.sql` 是一份初始化数据，包含 `navhub`（站点）和 `navproxy`（代理池）。导入时会自己建库，可以跳过空库种子：

```bash
mysql -h 127.0.0.1 -P 3306 -u root -p --default-character-set=utf8mb4 < backups/nav-local.sql
```

备份本身不进 Git。需要重新导出时：

```bash
mysqldump -h 127.0.0.1 -P 3307 -u root --default-character-set=utf8mb4 --single-transaction --routines --triggers --set-gtid-purged=OFF --databases navhub navproxy --result-file=backups/nav-local.sql
```

端口按实际 MySQL 修改。导入后把 `backend/.env` 的 `DATABASE_URL` 指到这台库。

## 本地运行

先启动 MySQL 和 Redis。数据库名 `navhub`，字符集 `utf8mb4`。

`backend/.env` 示例：

```
DATABASE_URL=mysql+pymysql://nav:navpass@127.0.0.1:3306/navhub?charset=utf8mb4
REDIS_URL=redis://127.0.0.1:6379/0
SECRET_KEY=change-this-secret
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=change-me-now
CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
PROXY_POOL_URL=
FREE_MONTHLY_QUOTA=5
VIP_MONTHLY_QUOTA=100
```

`.env` 不要提交。

接口：

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

前端。Windows 上请直接用 Vite，不要把 `--host` 交给 `npm run dev`，否则参数会被吃掉：

```bash
cd frontend
npm install
.\node_modules\.bin\vite --host 127.0.0.1 --port 5173
```

打开 http://127.0.0.1:5173/ 。

也可以在项目根目录执行 `docker compose up`。Compose 里的 MySQL 用户是 `nav` / `navpass`，映射本机 `3306`。

## 管理员

后台入口只认 `backend/.env` 里的 `ADMIN_GATE`。留空时第一次启动会生成 32 位随机码并写回 `.env`。改掉这段并重启接口后，只认新地址；旧地址接口返回 404，页面会回到首页。

用默认账号登录后打开 `http://127.0.0.1:5173/<那段路径>`。默认账号是 `admin@example.com` / `change-me-now`。公开部署前必须改掉邮箱、密码和 `SECRET_KEY`。管理员要先绑定验证器，后台编辑接口才会放行。

后台可以维护栏目、分类、链接、单页、广告和用户。广告按位置分组，例如首页轮播、各栏目信息流、页脚、登录页、个人中心右侧。

## 定时任务

接口进程起来后会启动三个任务，第一次执行时间是错开的，避免同时占满 CPU。

| 任务 | 第一次 | 之后 |
| --- | --- | --- |
| 资讯 | 2 分钟 | 每 5 分钟。只保留当天，过期行会删掉 |
| GitHub 排行 | 20 分钟 | 每 24 小时。近 24 小时、周、月和总星标 |
| 目录补齐 | 45 分钟 | 每 2 天。每日资讯以外的栏目，包括其他分类。已有网址跳过 |

目录来源是公开导航页，例如 AMZ123 的 AI 页、TT123、ThePornDude 的公开列表，以及 Telegram 公开目录。抓取会拒绝内网地址。

进程重启后，这三段等待会重新计算。

## 账号

- 注册邮箱会转成小写，数据库里邮箱唯一。
- 注册要完成滑块验证。验证码由服务端签发，约两分钟内有效，只能用一次，并且必须拖到最右侧。
- 登录失败多次会暂时锁定。
- 会话放在 Redis，Cookie 名 `nav_session`，约 12 小时。
- 个人中心可以改昵称和密码。改密码要先填当前密码，新密码至少 8 位。

## 广告和上传

广告图片地址和跳转地址在后台填写。个人中心右侧预留 `account-1`、`account-2`。

用户上传的图标保存在 `frontend/public/uploads/`，只接受 2MB 以内的图片。这个目录不进 Git。

## 部署

按「初始化部署」装好 MySQL、Redis，导入 `backups/nav-local.sql` 或让接口首次启动建表。然后：

1. 复制 `backend/.env.example` 为 `backend/.env`，改掉数据库地址、`SECRET_KEY`、管理员邮箱和密码。
2. 按「本地运行」安装依赖并启动接口和前端，或在项目根目录执行 `docker compose up`。Compose 里的 MySQL 用户是 `nav` / `navpass`，映射本机 `3306`。已有 SQL 时，可先把备份导入 Compose 的 MySQL，再启动接口。
3. `deploy/nginx.conf` 把 `/` 转到前端，把 `/api` 转到接口。

生产环境应关掉调试、更换密钥，并限制后台路径不要出现在公开页面上。首页底部栏可以关掉，关掉后这次浏览不再显示，刷新页面会再出现。
