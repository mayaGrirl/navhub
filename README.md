# NEXA

双语导航站。页面在 `/`，接口在 `/api`，同一域名用反向代理分开。默认语言是英文，可切到中文。

## 能做什么

- 顶部栏目来自数据库。当前对外栏目：每日资讯、AI 工具、跨境电商、午夜媒体、TG 群、其他分类。其他分类收的是公开第三方站点，按行业和地区铺开，包含签证、大事、友情链接和导航站。
- 点进一个栏目后，该栏目下的链接在同一页按分类排开。左侧分类只负责跳到对应区块。同一网址去掉协议、`www` 和末尾斜杠后视为同一条。
- 每日资讯保留最近 24 小时，中文和英文来源放在同一类话题里，来源包括各站 RSS、Google 新闻和百度新闻。摘要入库和展示前都会去掉 HTML 标签和实体，避免把 `&nbsp;`、链接标签原样显示出来。旁边是 GitHub 增量榜和总星标榜，各显示前 10。其下是收藏榜、推荐榜（各 5）和点击榜（10）。
- 午夜媒体整栏是 18+，进入前需要确认年龄，选择保存在浏览器里。链接都是外站，站内不播放视频。
- 注册用户可以提交链接，每月有次数上限。免费和 VIP 的上限不同，VIP 由管理员开通 30 天，没有支付接口。
- 提交后先记下记录，再在后台自动审核：全站没有相同网址，并且网址能打开，才收录并按后台配置加积分。重复或打不开会写明原因。同一小时内反复提交已有网址，后台会报警，管理员可以封禁账号和当时的 IP。
- 积分决定等级，等级 0 到 10。新用户是 Lv.0。每分钟可调用的代理次数由当前等级决定，具体数字在后台改。
- 登录后可以收藏、推荐导航卡片，再点一次取消。同一用户对同一条链接的同一种标记只记一次。首页卡片上的次数是累计值，后台可以改。同一 IP 对同一条链接 30 秒内只计一次点击。
- 登录、注册和关于我们在同一页：左边是介绍，右边是表单。注册需要把滑块拖到最右侧。
- 登录后顶部入口是个人中心：资料、等级规则、收藏推荐、提交链接、免费代理池。图标可以填地址，或上传 PNG、JPG、JPEG、GIF、WEBP，单张不超过 2MB。
- 广告位在后台按页面位置配置。没有内容的广告位不显示。
- 站内搜索在顶栏和页脚，点结果会定位到站内卡片。顶栏还有一组外站搜索引擎，默认 Google。界面是中文时 Google 用中文结果，英文时用英文结果。
- 首页底部栏固定显示，可以关掉。关掉后这次浏览不再出现，刷新会再出现。
- 公开接口要先拿到浏览凭证。代理池令牌接口不走这道限制。
- 管理后台是随机路径。未登录或不是管理员访问该地址会看到 404。登录要先把滑块对齐缺口。验证器可以不绑；绑定并打开两步验证后，登录才要填验证码。链接会标出是系统收录还是用户提交。

会员视频解析不在这个项目里。

## 技术栈

- 前端：Vue 3、Vite、Vue Router、Pinia、vue-i18n。登录、个人中心和后台页面在进入时再加载。
- 后端：FastAPI、SQLAlchemy、MySQL、Redis、PyOTP
- 可选：`proxy-pool/` 是独立的代理池。只有设置了 `PROXY_POOL_URL` 时，抓取才会用它。

## 目录

```
backend/          接口、种子数据、资讯和目录任务
frontend/         Vue 站点
docs/nav.py       本机开启、关闭、重启接口和前端
proxy-pool/       可选代理池
deploy/nginx.conf 同域反代示例
docker-compose.yml
```

主要页面：

| 路径 | 内容 |
| --- | --- |
| `/` | 首页 |
| `/about` `/login` `/register` | 介绍和登录或注册 |
| `/submit` | 个人中心，需登录。`?tab=` 可直接打开资料、等级、收藏、提交或代理池 |
| `/contact` `/advertise` | 联系方式和广告说明 |
| `/<后台路径>` | 管理后台 |

## 初始化部署

本机需要：

- Python 3.11 及以上
- Node.js 20 及以上
- MySQL 8，字符集 `utf8mb4`
- Redis 6 及以上

先启动 MySQL 和 Redis。下面按原生安装来写。端口以本机实际为准，示例用 MySQL `3306`、Redis `6379`。若 `3306` 已被占用，把建库、导入和 `DATABASE_URL` 里的端口改成同一个值。

空库起步时建库并授权：

```sql
CREATE DATABASE navhub CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'nav'@'%' IDENTIFIED BY 'navpass';
GRANT ALL ON navhub.* TO 'nav'@'%';
```

接口第一次启动会建表，并写入栏目、等级和目录种子。管理员账号来自 `backend/.env`。

仓库里的 `backups/nav-local.sql` 是一份初始化数据，包含 `navhub`（站点）和 `navproxy`（代理池）。导入时会自己建库，可以不再靠空库种子。Windows 和 Linux 命令相同，把 `mysql` 换成本机客户端的完整路径即可：

```bash
mysql -h 127.0.0.1 -P 3306 -u root -p --default-character-set=utf8mb4 < backups/nav-local.sql
```

数据有变化、需要换一份初始化 SQL 时再导出：

```bash
mysqldump -h 127.0.0.1 -P 3306 -u root -p --default-character-set=utf8mb4 --single-transaction --routines --triggers --set-gtid-purged=OFF --databases navhub navproxy --result-file=backups/nav-local.sql
```

导入后把 `backend/.env` 的 `DATABASE_URL` 指到这台库。

## 环境变量

```bash
copy backend\.env.example backend\.env
```

Linux / macOS：

```bash
cp backend/.env.example backend/.env
```

`.env` 不要提交。常用项：

| 变量 | 作用 |
| --- | --- |
| `DATABASE_URL` | MySQL 连接串，库名 `navhub`，字符集 `utf8mb4` |
| `REDIS_URL` | 会话、登录锁定、注册滑块 |
| `SECRET_KEY` | 会话签名。公开部署前换成随机长串 |
| `ADMIN_GATE` | 后台路径。留空时第一次启动生成 32 位并写回 `.env` |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | 第一次启动写入的管理员 |
| `CORS_ORIGINS` | 允许带登录 Cookie 的前端地址，逗号分隔 |
| `PROXY_POOL_URL` | 代理池地址。留空则抓取不走代理。本地默认 `http://127.0.0.1:8010` |
| `FREE_MONTHLY_QUOTA` / `VIP_MONTHLY_QUOTA` | 每月可提交次数 |
| `MAIL_*` | 发信。`MAIL_PROVIDER=log` 时只记日志，不真正发出 |

示例：

```
DATABASE_URL=mysql+pymysql://nav:navpass@127.0.0.1:3306/navhub?charset=utf8mb4
REDIS_URL=redis://127.0.0.1:6379/0
SECRET_KEY=change-this-secret
ADMIN_GATE=
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=change-me-now
CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
PROXY_POOL_URL=
FREE_MONTHLY_QUOTA=5
VIP_MONTHLY_QUOTA=100
MAIL_PROVIDER=log
```

进程环境变量会覆盖 `.env`。本地若同时开着别的库，先确认当前终端里的 `DATABASE_URL` 指向 `navhub`。

## 本地运行

接口和前端可以一条命令一起开。脚本在 `docs/nav.py`，Windows、Linux、macOS 用法相同。MySQL 和 Redis 需要先自己启动。第一次运行前仍要按下面的步骤装好 `backend/.venv` 和 `frontend/node_modules`。

在项目根目录执行：

```bash
python docs/nav.py start
python docs/nav.py status
python docs/nav.py restart
python docs/nav.py stop
```

Linux / macOS 如果 `python` 不在 PATH 里，把上面的 `python` 换成 `python3`。

| 命令 | 作用 |
| --- | --- |
| `start` | 拉起接口 `127.0.0.1:8000` 和前端 `127.0.0.1:5173`。任一端口已被占用就不再启动，先看 `status` |
| `status` | 看两个端口是否在监听，以及进程号 |
| `restart` | 先关闭再开启 |
| `stop` | 关闭这两个端口上的监听进程。端口上如果有别的程序，也会被关掉 |

脚本每次启动会清空并重写 `.run/api.log`、`.run/web.log`，进程号写在同目录的 `.pid` 文件里。这个目录不进 Git。启动后如果健康检查没通过，终端会打出对应日志的最后几行。浏览器打开 http://127.0.0.1:5173/ ，接口健康检查是 http://127.0.0.1:8000/api/health 。

三个进程也可以分开开。接口和前端都只监听本机。

接口，Windows：

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

接口，Linux / macOS：

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

前端。Windows 上请直接调用 Vite，不要把 `--host` 交给 `npm run dev`，否则参数会被吃掉：

```bash
cd frontend
npm install
.\node_modules\.bin\vite --host 127.0.0.1 --port 5173
```

Linux / macOS：

```bash
cd frontend
npm install
./node_modules/.bin/vite --host 127.0.0.1 --port 5173
```

可选代理池。先建库 `navproxy`，复制 `proxy-pool/.env.example` 为 `proxy-pool/.env`，再在 `proxy-pool` 目录执行：

```bash
pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 8010
```

需要走代理抓取时，把站点 `PROXY_POOL_URL` 设为 `http://127.0.0.1:8010` 并重启接口。

也可以在项目根目录用 Docker 一次拉起 MySQL、Redis、接口和前端：

```bash
docker compose up
```

Compose 里的 MySQL 用户是 `nav` / `navpass`，root 密码 `navroot`，映射本机 `3306`。已有 SQL 时，先 `docker compose up mysql -d`，把 `backups/nav-local.sql` 导入该实例，再启动其余服务。公开部署前改掉 Compose 里的 `SECRET_KEY`、管理员邮箱和密码。

## 管理员

后台入口只认 `backend/.env` 里的 `ADMIN_GATE`。留空时第一次启动会生成 32 位随机码并写回 `.env`。改掉这段并重启接口后，只认新地址；旧地址接口返回 404，页面会回到首页。

登录地址是 `http://127.0.0.1:5173/` 加上 `ADMIN_GATE`。邮箱和密码是同一份文件里的 `ADMIN_EMAIL`、`ADMIN_PASSWORD`。登录页要把滑块拖到缺口上，缺口和形状每次刷新都会变。

公开部署前必须改掉邮箱、密码、`ADMIN_GATE` 和 `SECRET_KEY`。验证器可以不绑。绑定之后，只有打开两步验证开关，登录才要填验证码。后台可以新增管理员、重置密码、重置验证器，并禁用账号或 IP。被禁用的账号和 IP 不能再登录前台或后台。

后台可以维护栏目、分类、链接、资讯、单页、公告、广告、采集、等级、积分规则、用户、邮件、反馈和代理。弹框公告只在前台页面出现，进入管理后台不会弹出。链接列表能改收藏数和推荐数。报警页可以封禁账号和 IP。广告按位置分组，例如首页轮播、各栏目信息流、页脚、登录页、个人中心右侧。

## 后台采集

采集页在管理后台，分「采集任务」和「待收录」。

- 新建任务要选栏目和分类。填了指定网址就只采那一页；网址留空则按关键词搜索站点。间隔最少 1 分钟，默认 1440 分钟（一天）。保存后会立刻跑一次。
- 任务可以手动开始、停止、改间隔、看最近日志，也可以删除。删除时，这条任务里还没收录的结果会一起删掉。
- 抓到的站点先进入「待收录」，不会直接上首页。点收录后才写成已发布链接，来源记为采集。站内或待收录里已经有的网址会跳过。
- 单页最多取 40 个链接。页面如果是 RSS 或 Atom，优先读条目；否则读页面上的链接。
- 采集请求走 `PROXY_POOL_URL` 里的代理池，并且拒绝内网地址。没配代理池、池里没有可用代理，或页面打不开时，任务状态是失败，原因写在日志里。
- 接口每分钟检查一次已启用、当前没在跑的任务。距上次运行已超过该任务的间隔，就再跑一遍。接口重启时，正在跑的任务会标成已停止，不会接着跑。
- 栏目列表里，链接类栏目有「全网采集」开关。打开后大约每 24 小时跑一轮，每分钟最多处理一个栏目，每个栏目最多搜 8 个可见分类，每个分类最多收 8 条新网址。关键词是栏目名加分类名。新网址直接发布到对应分类，已有网址跳过，不改已有收藏和点击数。搜索全部失败时，一小时后再试。关掉后，这个栏目不再全网搜索，目录补齐也不会再抓它。首页栏目没有这个开关。全网搜索要走代理池。

## 定时任务

接口进程起来后会启动下面这些后台循环。资讯、GitHub 排行和目录补齐的第一次执行时间是错开的，避免同时占满 CPU。

| 任务 | 第一次 | 之后 |
| --- | --- | --- |
| 资讯 | 启动后 2 分钟 | 每 5 分钟。保留最近 24 小时，更早的行会删掉 |
| GitHub 排行 | 启动后 20 分钟 | 每 24 小时。近 24 小时、周、月和总星标 |
| 目录补齐 | 启动后 45 分钟 | 每 2 天。只抓栏目列表里打开了「全网采集」的栏目，例如 AI 工具、跨境电商、午夜媒体、TG 群、其他分类。已有网址跳过 |
| 后台采集 | 启动后 1 分钟 | 每 1 分钟检查一次。每个任务按自己的间隔跑，见上一节 |
| 定时邮件 | 启动后 1 分钟 | 每 1 分钟检查一次。到了发送时间就按任务里的收件范围发信；没填重复间隔的任务发完就停用 |

目录补齐只处理栏目列表里打开了「全网采集」的栏目，已有网址跳过，抓取会拒绝内网地址。对应来源是：

| 栏目 | 来源 |
| --- | --- |
| AI 工具 | 内置站点名单，加上 AMZ123 的 AI 页 |
| 跨境电商 | 内置站点名单，加上 TT123 |
| 午夜媒体 | 内置站点名单，加上 ThePornDude 的公开列表 |
| TG 群 | 内置频道名单，加上 Telegram 公开目录 |
| 其他分类 | 内置的行业、地区、签证、大事、友情链接和导航站 |

用户提交的链接不在这张表里。提交后马上审核；接口启动时也会把还在审核中的用户提交再审一遍。

进程重启后，资讯、GitHub 排行和目录补齐的等待会重新计算。采集任务、定时邮件和栏目全网采集看的是上次运行时间，不会因为重启把间隔清零。全网采集每次只处理一个到期栏目。

## 账号

- 注册邮箱会转成小写，数据库里邮箱唯一。
- 注册要完成滑块验证。验证码由服务端签发，约两分钟内有效，只能用一次，并且必须拖到最右侧。
- 登录失败多次会暂时锁定。
- 会话放在 Redis，Cookie 名 `nav_session`，约 12 小时。
- 个人中心可以改昵称和密码。改密码要先填当前密码，新密码至少 8 位。
- 被封禁的账号不能登录，也不能再提交。

## 积分和审核

后台「每个有效链接获得的积分」默认是 1，只在自动审核通过时加一次。站内已有的网址不加分。

等级门槛和每分钟代理次数也可以在后台改。默认大致是：0 级 0 分、每分钟 5 次；1 级 10 分、每分钟 10 次；之后逐级提高，最高 10 级。

提交记录每页 10 条，显示名称、图标、一级栏目、二级分类和审核说明。没有图标时用名称首字母。已收录的记录可以回到首页并高亮那条链接，网址在当前浏览器新开一页。

## 手机端

宽度在 860 像素以内时，页面不横向滑动。栏目、分类和说明放不下就换行。左上角返回和右上角菜单固定在屏幕顶部。

## 广告和上传

广告图片地址和跳转地址在后台填写。个人中心右侧预留 `account-1`、`account-2`。

用户上传的图标保存在 `frontend/public/uploads/`，只接受 2MB 以内的 PNG、JPG、JPEG、GIF、WEBP。这个目录不进 Git。

## 部署

按「初始化部署」装好 MySQL、Redis，导入 `backups/nav-local.sql` 或让接口首次启动建表。然后：

1. 复制 `backend/.env.example` 为 `backend/.env`，改掉数据库地址、`SECRET_KEY`、`ADMIN_GATE`、管理员邮箱和密码。`CORS_ORIGINS` 改成实际上线的站点地址。
2. 按「本地运行」安装依赖。开发时启动接口和 Vite。正式环境先构建前端：

```bash
cd frontend
npm run build
```

产物在 `frontend/dist`。接口仍用 uvicorn 监听 `8000`，前面加进程守护。

3. `deploy/nginx.conf` 是同域反代示例：`/api` 转到接口，`/` 转到前端。文件里的 `api`、`web` 是 Compose 服务名。原生部署时把它们改成 `127.0.0.1:8000` 和前端静态目录或预览端口。

生产环境应更换密钥，后台路径不要出现在公开页面上。首页底部栏可以关掉，关掉后这次浏览不再显示，刷新页面会再出现。
