<p align="center"><img src="assets/media-index-icon.png" alt="MediaIndex" width="150" /></p>

# MediaIndex

MediaIndex 是面向个人 NAS 的**自托管网盘媒体自动化中心**：以 TMDB 与 PanSou 完成发现和资源核对，原生连接夸克与 115，把云端转存、分类命名、智能追更、愿望单、STRM/302、Emby 入库和图文通知串成一条可查看、可追溯、可控制的完整流程。

[![GHCR](https://img.shields.io/badge/GHCR-media--index-2f8f8c?style=flat-square)](https://github.com/users/xudong7587/packages/container/package/media-index)
[![Version](https://img.shields.io/github/v/release/xudong7587/media-index-deploy?style=flat-square&color=6d7cff)](https://github.com/xudong7587/media-index-deploy/releases/latest)
![Docker](https://img.shields.io/badge/deploy-Docker-2496ed?style=flat-square)
![License](https://img.shields.io/badge/license-GPL--3.0-111827?style=flat-square)

📖 **[使用手册](docs/USAGE.md)** · 🐳 **[Docker Compose](docker-compose.yaml)** · 📦 **[最新发布](https://github.com/xudong7587/media-index-deploy/releases/latest)** · 📝 **[更新日志](CHANGELOG.md)** · 📜 **[免责声明](DISCLAIMER.md)**

## 特点与优势

如果你的影片和剧集保存在网盘，真正费时的往往是后续工作：确认内容、选择版本、转存到合适目录、统一命名、补齐更新、让 Emby 能播放，并在失败时知道卡在哪里。MediaIndex 把这些步骤放进一个自托管控制台。

- **完整的媒体工作流**：从发现、搜索和链接输入，到网盘整理、STRM、Emby 与通知，减少在多个脚本之间维护状态的成本。
- **夸克与 115 可以并存**：两个网盘分别设置连接、保存位置、任务和 STRM，按资源与使用习惯选择目标。
- **适合长期维护媒体库**：云下载整理、分类命名、剧集追更、愿望单、全量与增量 STRM 形成持续运行的工作流；STRM 在选定范围内核对映射，路径冲突不会盲目覆盖。
- **自动化范围由你决定**：网盘、目录、定时任务和处理范围由你选择；无法可靠判断的内容进入待确认。
- **搜索与频道独立配置**：PanSou 聚合搜索与 TG 频道追踪分开管理；频道可独立设置正向词、反向词、转存开关和云下载分类。
- **执行过程看得见**：任务中心展示阶段、进度和失败原因，站内通知、活动记录与日志帮助定位问题；企业微信、Telegram、每日运行报告和免打扰可按需使用。
- **桌面与手机统一使用**：发现海报墙、详情面板、网盘工作台和任务入口覆盖日常操作；常用服务按需连接，不用的功能无需配置。

你仍然决定使用哪个来源、保存到哪里、哪些任务可以自动运行；系统执行重复工作，并把不确定的结果交还给你确认。MediaIndex 不提供影视资源、分享链接、账号或第三方服务。

## 工作流程

| 使用场景 | 流程 |
| --- | --- |
| 已确认媒体身份和候选资源 | 发现／追更／愿望单 → 资源核验 → 分类命名与转存 → 正式媒体库 → STRM → Emby。磁力等下载任务先完成云下载，再核验整理。 |
| 现成链接、频道资源或外部下载文件 | 链接／频道／外部投递 → 云下载暂存目录 → 匹配改名与整理 → 正式媒体库 → STRM → Emby。关闭整理开关时停在暂存区。 |
| 外部工具已经完成整理 | Webhook → 核对来源网盘与授权目标 → 定点增量 STRM → Emby 刷新。 |
| 网盘中已有规范媒体目录 | 选择 STRM 来源目录与处理范围 → 首次全量扫描 → 后续增量或定时维护。 |

入库后，Emby 或播放器通过 STRM 访问独立播放入口，再获取网盘直链或范围转发。任务、通知与日志持续记录各环节结果；需要跨盘补齐时，可在 **跨盘转存** 中按已配置的 OpenList 或 CD2 通路处理。

## 部署前准备

MediaIndex 适合拥有 NAS 或常驻 Docker 环境、使用夸克或 115 保存合法授权媒体，并希望维护个人媒体库的用户。

| 项目 | 用途 |
| --- | --- |
| Docker 与 Docker Compose | 运行服务；镜像支持 `linux/amd64` 和 `linux/arm64`，不支持 32 位 ARM。 |
| 持久化目录 | 保存数据库、设置、缓存、任务数据和 STRM。 |
| 夸克或 115 账号 | 使用网盘转存、整理和播放时，至少连接一个。 |
| TMDB API | 推荐，用于海报、详情、季集信息与播出状态。 |
| PanSou | 可选，用于站内聚合搜索。 |
| Emby | 可选，用于媒体库扫描、展示与播放。 |
| OpenList、CD2、企业微信或 Telegram | 可选，用于跨盘复制、通知或消息交互。 |

## Docker Compose 部署

### 1. 下载部署文件

```sh
mkdir -p media-index/data media-index/downloads media-index/strm
cd media-index
curl -fL https://raw.githubusercontent.com/xudong7587/media-index-deploy/main/docker-compose.yaml -o docker-compose.yaml
```

也可直接下载 [docker-compose.yaml](docker-compose.yaml)，在 NAS 的容器管理器中创建 Compose 项目。镜像使用 `ghcr.io/xudong7587/media-index:latest`，Docker 自动选择宿主对应的架构；需要固定版本时，把 `latest` 替换为 [Release](https://github.com/xudong7587/media-index-deploy/releases) 中实际发布的镜像版本标签。

### 2. 修改账号、端口与挂载

启动前编辑 `docker-compose.yaml`：

- 修改 `MEDIA_USER` 和 `MEDIA_PASS`，设置独立的强密码。网页中的第三方服务设置保存在持久化数据中，管理账号由部署配置提供。
- `8000:8000` 是管理面板；`8097:8097` 是 STRM/302 播放入口。端口冲突时修改映射左侧，管理与播放反向代理分别指向对应端口。
- `./data:/app/data` 保存数据库、设置、缓存和任务状态；`./downloads:/downloads` 是本地下载目录；`./strm:/strm` 保存生成的 STRM 及相关文件。
- 将 `./strm` 对应的宿主目录挂载给 Emby 扫描，并确认 MediaIndex 对输出目录有写权限。按实际目录权限设置 `PUID` / `PGID`。

### 3. 启动

```sh
docker compose up -d
docker compose ps
```

打开 `http://<NAS地址>:8000`，使用刚设置的账号登录。只有完成网盘、目录及相关服务配置后，对应的转存、整理和播放能力才可使用。

### 可选：搜索服务与网络代理

Compose 内附带注释形式的 PanSou 服务示例；需要时按文件说明启用，也可连接已有 PanSou。相同 Compose 网络中的服务可通过服务名连接，例如 `http://pansou:8888`。

外部服务无法直连时，在 **全局设置 → 网络代理** 填写容器可访问的代理地址，例如 `http://<代理主机地址>:7890`，并测试连接。代理软件需允许局域网连接；容器内的 `127.0.0.1` 指向容器自身。

也可使用 Compose 中的 `PROXY_URL`、`HTTP_PROXY`、`HTTPS_PROXY` 和 `NO_PROXY`。网页保存的代理配置优先于同名启动默认值；内网服务应按实际网络保持直连。

## 第一次使用

1. **连接网盘**：在 **网盘工作台 → 网盘链接** 中接入夸克或 115，保存并测试连接。两盘分别核对连接状态。
2. **配置影视资料和搜索**：在 **全局设置** 配置 TMDB；需要资源搜索或频道追踪时，到 **网盘工作台 → 资源获取** 配置 PanSou 与 TG。
3. **确认目录规则**：设置正式媒体库、云下载暂存目录、分类路径和命名偏好。先分清暂存目录与正式库。
4. **完成一次小范围入库**：从 **发现** 选择一部熟悉的电影，核对标题、年份、候选文件和最终保存目录，再提交并查看任务回执。
5. **接通播放**：在 **STRM 与 302** 配置来源目录、输出目录和播放器可访问的地址，仅选择要处理的范围；连接 Emby，确认扫描和播放正常。
6. **逐项开启自动化**：再按需启用智能追更、愿望单、频道转存、定时 STRM、通知或跨盘补偿。删除联动需单独确认；115 与夸克的执行开关相互独立。

完整操作请看 **[使用手册](docs/USAGE.md)**。部署后的左侧 **使用手册** 提供按场景组织的帮助，**全局设置 → 链路概览** 用于核对配置和流程。

## 常用场景

| 目标 | 操作入口与要点 |
| --- | --- |
| 找电影、剧集、动漫与综艺 | 在发现页使用榜单、分类与搜索，打开详情核对媒体身份，再选择候选资源。 |
| 处理现成链接 | 提交夸克、115、磁力、ED2K 或 HTTP 链接，按入口选择云下载暂存或已确认身份的入库流程。 |
| 持续补齐连载 | 在订阅与追更中维护任务，查看播出与云端已存进度；“刷新已存”和“生成 STRM”按所选网盘及该任务目录处理。 |
| 等待暂时没有资源的作品 | 加入愿望单，保留媒体身份并等待后续搜索；不确定的候选继续人工确认。 |
| 自动接收频道资源 | 在资源获取中添加 TG 频道，配置过滤和转存方式；实时接收需 Bot 加入频道，只接收加入后的新帖。 |
| 维护已有媒体库 | 配置 STRM 全量／增量扫描；在媒体服务器页面查看 Emby 媒体库、播放会话和最近入库，按需制作媒体库封面。 |
| 用手机查看进度 | 接通企业微信或 Telegram，接收结果并提交指令；在通知设置中选择类别、每日运行报告和免打扰时间。 |
| 排查未完成任务 | 查看任务中心、待确认项、通知与日志，按失败阶段修复配置或重试，分别检查每个网盘的结果。 |

## 更新与备份

更新前保存当前镜像版本，备份 `docker-compose.yaml`、部署环境配置和挂载目录。数据库需要一致性备份时，先停止 MediaIndex，再备份 `./data`；同时按实际使用情况保存 `./strm` 和 `./downloads`。

```sh
docker compose pull
docker compose up -d
docker compose ps
```

更新会重建应用容器，持久化目录应继续使用原来的挂载。保留旧镜像和升级前备份，回退时按对应版本恢复；不要只切换镜像就假定数据库可向后兼容。详细步骤见 [使用手册](docs/USAGE.md)，版本变化见 [更新日志](CHANGELOG.md)。

## 隐私与免责声明

MediaIndex 是个人学习、技术研究与自托管自动化工具，不内置或提供影视资源、网盘分享链接、提取码、账号、Cookie 或规避版权保护的能力。相关搜索、转存、下载、整理、STRM 和删除操作由使用者自行配置账号与第三方服务后触发。

TMDB、PanSou、网盘、OpenList、Emby 等均为独立第三方或用户自部署服务，项目不保证其内容来源、版权状态、准确性、安全性或持续可用性。使用者须确保拥有相关内容的合法访问和使用权，并遵守所在地法律法规、著作权规定及服务条款，禁止用于盗版传播、未经授权分享或其他违法用途。

账号凭据、配置、数据库与缓存属于部署者的私有数据。反馈问题时请隐藏 Cookie、Token、Webhook 密钥、播放链接、真实地址、设备和个人目录信息；不要公开完整配置、数据库或未脱敏截图。对外提供管理入口时应自行配置合适的访问控制。

请自行评估并承担第三方服务费用、账号限制、误操作、数据丢失、隐私泄露及版权纠纷等风险。完整条款见 [DISCLAIMER.md](DISCLAIMER.md)。

## 许可与致谢

MediaIndex 采用 [GNU General Public License v3.0](LICENSE)。第三方组件及其许可证见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

感谢 [Cp0204/quark-auto-save](https://github.com/Cp0204/quark-auto-save)、[tgtodriver](https://github.com/Tech-Solutions-Group/tgtodriver)、[MoviePilot](https://github.com/jxxghp/MoviePilot)、MoviePilot 社区的 115 STRM 助手及相关插件作者，以及 [fish2018/pansou](https://github.com/fish2018/pansou)、OpenList、TMDB 与相关开源项目贡献者。
