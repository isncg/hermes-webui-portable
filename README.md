# Hermes WebUI Portable

Windows 原生的 Hermes Agent + Hermes WebUI 整合仓库。上游源码以 Git submodule 固定到经过验证的版本，本机适配以可审计补丁保存，不直接 fork 或复制上游源码。

## 固定版本

| 组件 | 上游版本 | 固定提交 |
| --- | --- | --- |
| Hermes Agent | `v0.21.5`（release date `2026.9.24`） | `802ae8544b59f62c97468ed31b55f417ba12e9f2` |
| Hermes WebUI | `v0.52.544` | `687d80333870c3797d6858738621fca13d1bf27a` |

详细锁定信息见 `versions.cmd`。

## 软件依赖

- Windows 10/11 x64。
- Git for Windows，并确保 `git.exe` 位于 `PATH`。
- 能够访问 GitHub 和 Python 包索引的网络，用于首次下载运行时和依赖。
- Windows 自带的 `curl.exe`、`tar.exe`、`certutil.exe` 和 `taskkill.exe`。
- 不需要预装 Python 运行时、PowerShell、Node.js 或 Visual C++ Build Tools。

可在 CMD 中检查环境：

```bat
git --version
curl --version
tar --version
```

`setup.cmd` 会下载并校验固定版本的 `uv`。如果系统带有 Python 官方安装管理器（`py.exe` 或 `pymanager.exe`），setup 会优先用它把官方签名的 Python 3.14.10 解压到仓库内的 `.runtime`；否则由 `uv` 下载项目私有 Python。不会修改系统 Python 或 `PATH`。

依赖直接安装到这个仅供本项目使用的运行时，只接受预编译 Windows wheel，不会创建可能被企业安全策略拦截的虚拟环境启动器，也不会回退到本机编译。在企业策略禁止执行第三方便携 Python 的机器上，需要系统已有 Python 官方安装管理器，但仍不需要用户手工安装具体 Python 版本。

`.runtime` 和 `.cache` 都是可重建目录。旧版本创建的 `.venv` 不再使用，可以手工删除。

## 首次安装

```bat
git clone --recurse-submodules <此仓库地址> hermes-webui-portable
cd hermes-webui-portable
setup.cmd
```

`setup.cmd` 会：

1. 初始化并验证两个固定提交的 submodule。
2. 幂等应用 `patches` 下的本地补丁。
3. 下载固定版本的 `uv` 和项目私有 Python 3.14.10。
4. 仅使用预编译 wheel 安装 WebUI 依赖，并将 Agent editable-install 到同一私有运行时。
5. 创建 `.env`、`workspace`、`data` 和 `var` 运行目录。
6. 运行离线 YAML 后端的回归测试。

只准备源码和补丁、不安装 Python 依赖：

```bat
setup.cmd -SkipInstall
```

只使用 gateway bridge、不安装进程内 Agent 依赖：

```bat
setup.cmd -GatewayOnly
```

## 启动

后台启动（推荐）：

```bat
start.cmd
```

服务器在后台运行。重复执行 `start.cmd` 时会检测已有实例并直接跳过。启动成功后会使用 Chrome 应用窗口打开 <http://localhost:8787/>；未安装到默认路径时只提示地址。双击运行时窗口会在显示结果后等待按键再关闭；在脚本中调用时可设置 `HERMES_START_NO_PAUSE=1` 跳过等待。停止后台服务器：

```bat
stop.cmd
```

局域网访问：

```bat
start-lan.cmd
```

该入口在当前终端前台运行并监听 `0.0.0.0:7878`，按 Ctrl-C 停止。默认使用 7878 端口，可与本地 8787 后台实例同时运行。启动时会直接提示输入本次运行使用的密码（输入内容不回显），不需要修改配置文件；也可以预先设置 `HERMES_WEBUI_PASSWORD` 环境变量来跳过提示。启动后会打印本机的局域网地址，其他计算机使用 `http://<主机IPv4>:7878/` 访问。首次使用时需要允许 Python 通过 Windows 防火墙（专用网络）。如果 7878 端口已被占用，可按同样方式用 `-Port` 指定其他端口。

前台运行（日志直接输出到当前终端，按 Ctrl-C 停止）：

```bat
server.cmd
```

查看后台状态、健康检查和最近的日志：

```bat
run-webui.cmd -Status
```

`run-webui.cmd` 是底层管理入口，也接受 `-Start`、`-Stop` 和 `-Foreground`。`start.cmd` 与 `server.cmd` 支持用 `-Port 8787` 和 `-BindHost 127.0.0.1` 临时覆盖监听地址。默认打开 <http://127.0.0.1:8787>。Provider、模型和密钥继续从 `%USERPROFILE%\.hermes` 读取；会话默认写入 `%USERPROFILE%\.hermes\webui`；文件工作区位于仓库顶层 `workspace`。

## 配置

首次 setup 会将 `.env.example` 复制为未跟踪的 `.env`。启动前已经存在的进程环境变量优先于 `.env`。

不要在 `.env` 中写入指向某个版本目录的 Agent、WebUI Python 或 workspace 绝对路径；启动器会从自身位置计算：

- `HERMES_WEBUI_AGENT_DIR=<仓库>\hermes-agent`
- `HERMES_WEBUI_PYTHON` 由 setup 写入 `var\runtime-python.txt`，指向实际使用的项目私有 Python。
- `HERMES_WEBUI_DEFAULT_WORKSPACE=<仓库>\workspace`

监听 `0.0.0.0` 前必须设置 `HERMES_WEBUI_PASSWORD`。

## 补丁模型

本仓库只通过 `patches/<组件>/NNNN-*.patch` 保存对上游源码的适配。`scripts/apply-patches.cmd` 按组件内文件名顺序幂等应用补丁：

- 可正向应用：执行 `git apply`。
- 可反向检查：视为已经应用。
- 两者都失败：立即停止，要求升级时人工 rebase 补丁。

应用补丁后 submodule 显示 dirty 是预期行为。不要在 submodule 中提交本地适配；应更新 `patches` 中的补丁。

### Hermes WebUI

- `patches/hermes-webui/0001-offline-yaml-mini.patch`
  - 目的：让完全离线、无法安装 PyYAML/ruamel.yaml 的主机仍能启动 WebUI。缺少 YAML 后端时 `import server` 会在 `api/profiles.py` 阶段失败。
  - 改动：新增纯标准库的 `api/yaml_mini.py`，在 `api/yaml_compat.py` 中增加可选的 `mini` 后端；支持 PyYAML 风格的 YAML 1.1 隐式类型、块/流集合、块/引号标量、注释和单文档标记。
  - 启用条件：同时满足 `HERMES_WEBUI_YAML_MINI` 为真值，且 PyYAML 与 ruamel.yaml 都无法导入。正常安装时后端优先级仍是 `PyYAML > ruamel.yaml > yaml_mini`；未设置该变量时保持上游的 `ImportError` 行为。
  - 失败策略：锚点/别名、合并键、标签、显式键、指令和多文档流会抛出 `UnsupportedYAMLError`，不会静默猜解析结果，避免后续保存时截断用户配置。
  - 验证：`tests/test_yaml_mini_fallback.py`，`setup.cmd` 安装后会运行该回归测试。
- `patches/hermes-webui/0002-desktop-message-width.patch`
  - 目的：桌面端让对话区与输入框使用同一套宽度，并解除用户长消息原有的 60% 宽度限制。
  - 改动：仅修改 `static/style.css`。`>=641px` 时 `--msg-max` 为 `clamp(780px, 60vw, 1100px)`，`>=1600px` 时为 `1600px`；同时调整 `.composer-box`、`.messages-inner` 和 `.msg-row[data-role='user']`。
  - 注意：纯展示层改动，使用 `!important` 覆盖已有布局规则，不涉及后端行为；升级后需做一次桌面宽度视觉检查。
- `patches/hermes-webui/0003-windows-workspace-blocked-roots.patch`
  - 目的：修复 Windows 上合法的 `D:\dev\...` 项目被误判为系统目录的问题。POSIX 名称在 Windows 上是驱动器相对路径，旧规则把 `/dev` 解析成当前盘的 `\dev`。
  - 改动：`api/workspace.py` 在 Windows 上改用 `%SystemRoot%`、`%WINDIR%`、`%ProgramFiles%`、`%ProgramFiles(x86)%`、`%ProgramW6432%` 和 `%ProgramData%` 作为禁止根目录；POSIX 根目录和 `/private/...` 只保留在 POSIX 平台。远程终端的 POSIX 形态路径仍会被拒绝。
  - 验证：新增 `tests/test_workspace_blocked_roots_windows.py`，并让原 POSIX 测试在 Windows 上跳过；当前 Windows 用例 23 项通过。

- `patches/hermes-webui/0004-clarify-choice-display.patch`
  - 目的：修复 clarify 选项交互的两个问题——点击选项后的回显被插到对话文字之前；退出会话再重新打开后，回显从消息列表消失。
  - 改动：`api/models.py` 增加 clarify tool 结果解析与展示投影（支持单题、批题、多选，重复投影幂等）；`api/streaming.py` 在 SSE done 等展示 payload 出口注入回显行，并在模型请求清洗阶段剔除该行；`api/routes.py` 在 `GET /api/session`、fork、share、duplicate、compression-recovery 的展示出口统一投影；`static/messages.js` 点击选项后把回显追加到 live assistant turn 块栈末尾，不再改写 `S.messages` 后整屏重渲染；`static/ui.js` 避免把回显行当成可编辑的最后一条用户消息。
  - 说明：回显行是展示层合成行（`_clarify_response`），不写入 `session.messages`/sidecar，也不进入模型上下文；每次加载都从 clarify tool 结果重新投影，因此刷新或切换会话后位置不变且不会重复。
  - 验证：新增 `tests/test_clarify_choice_display_row.py`，覆盖解析、批题多选、幂等、展示出口注入、模型请求清洗和客户端回显位置。

### Hermes Agent

- `patches/hermes-agent/0001-dual-stack-oauth-callback.patch`
  - 目的：修复 Windows 上浏览器把 `localhost` 解析为 `::1`、而登录回调只监听 `127.0.0.1` 时无法完成授权的问题；同时避免两个登录进程通过 `SO_REUSEADDR` 共用 1455 端口后，旧监听器截获回调。
  - 改动：`hermes_cli/auth_device_flow.py` 在同一端口同时绑定 IPv4 与 IPv6 回环地址，IPv6 使用 `IPV6_V6ONLY`；Windows 使用 `SO_EXCLUSIVEADDRUSE` 且不再设置 `SO_REUSEADDR`；IPv6 绑定失败且 `localhost` 不解析到 IPv6 时退回仅 IPv4。`hermes_cli/auth_codex_browser.py` 补充端口占用和浏览器连接失败提示。
  - 注意：1455 端口已被占用时仍会回退到设备码登录。
  - 验证：`tests/hermes_cli/test_auth_codex_browser_login.py` 和 `tests/hermes_cli/test_browser_connect_dual_stack.py`。
- `patches/hermes-agent/0002-windows-system-proxy-fallback.patch`
  - 目的：Clash 等工具通常只写 Windows 用户级系统代理，OpenAI SDK/httpx 不会自动读取；仅配置系统代理时直连被墙主机会超时。
  - 改动：`agent/process_bootstrap.py` 在没有任何 `*_PROXY` 环境变量时读取注册表 `HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings` 的 `ProxyEnable`、`ProxyServer` 和 `ProxyOverride`；支持 `host:port` 与 `http=...;https=...` 两种格式，把 WinINET 的 `10.*` 形式转换为 CIDR，结果缓存 30 秒；回环地址和 `ProxyOverride` 条目始终直连。
  - 注意：环境变量代理保持原有优先权和 `NO_PROXY` 匹配行为；注册表读取失败会静默关闭该兜底，不影响原有配置。`<local>` 被忽略，只影响无点主机名，不会影响 LLM API 主机。当前没有针对注册表兜底的独立自动化测试，现有环境变量代理测试通过。

两个组件的补丁分别按文件名顺序应用，当前补丁之间没有顺序依赖。新增补丁时沿用四位序号前缀，并在本节补充目的、启用条件、失败行为和验证方式。

## 升级

1. 在单独分支更新 submodule 到目标上游提交。
2. 更新 `versions.cmd` 和 README 的版本锁定信息。
3. 运行 `git -C hermes-webui reset --hard` 和 `git -C hermes-agent reset --hard` 清除旧补丁工作树。
4. 运行 `setup.cmd -SkipInstall`，检查现有补丁是否仍可应用。
5. 若补丁冲突，以新版源码重新实现同一改动并重新生成 patch，禁止用旧文件整文件覆盖新版。
6. 删除并重建 `.runtime` 和 `.cache`，再运行完整 `setup.cmd`。
7. 验证 `/health`、历史会话、Provider/模型、gateway 模式和进程内 Agent 模式。
8. 提交新的 submodule gitlink、版本锁和补丁；旧提交仍可通过 superproject 历史回滚。

## 安全边界

所有 Windows 入口和安装脚本均为 `.cmd`，不调用或依赖 PowerShell。Python 和 `uv` 均安装在仓库内部；后台进程管理使用项目私有 Python 的标准库和 Windows 自带的 `taskkill.exe`，如果 `taskkill.exe` 被安全策略拦截，则回退到 Win32 `TerminateProcess`。

补丁和启动脚本不使用命令混淆、重命名或编码拼接来规避安全检查。

## ChatGPT OAuth 登录（便携版）

便携版提供 `hermes.cmd`，它等价于安装版的 `hermes` 命令，不会修改系统 `PATH`。

1. 登录 ChatGPT 账户（只写入 OAuth 凭据，不修改现有 provider/model）：

   ```bat
   .\chatgpt-login.cmd
   ```

   默认会打开浏览器完成 OpenAI 授权（最多等待 180 秒），回调地址为 `http://localhost:1455/auth/callback`。1455 端口被其他登录进程占用时会自动回退到设备码方式；该端口现在采用独占绑定，不会再出现新旧两个登录进程同时等待、回调被旧进程截获的情况。若浏览器提示无法连接 `localhost`，请关闭残留的登录窗口后重试，或改用 `--device-code`（本机代理/安全软件拦截 `localhost` 时也需要用它）。

   等价的手动命令（浏览器登录）：

   ```bat
   .\hermes.cmd auth add openai-codex --type oauth --browser
   ```

   无浏览器或远程终端环境可使用设备码方式：

   ```bat
   .\chatgpt-login.cmd --device-code
   ```

2. 查看登录状态：

   ```bat
   .\hermes.cmd auth status openai-codex
   ```

3. 交互式选择模型（在确认选择前不会修改配置）：

   ```bat
   .\choose-model.cmd
   ```

   或直接运行：

   ```bat
   .\hermes.cmd model
   ```

   在列表中选择 `OpenAI Codex`，再选择需要的 GPT 模型。

4. 重启 WebUI 后即可使用。

凭据保存在 `%HERMES_HOME%\auth.json`（默认 `%USERPROFILE%\.hermes\auth.json`），与 Codex CLI 的 `~/.codex` 分开。OAuth 登录需要能够访问 `auth.openai.com` 和 `chatgpt.com`，并且 ChatGPT 账户具有相应的 Codex 使用权限。

`hermes.cmd` 依赖 setup 安装的 Agent 依赖。如果之前使用了 `setup.cmd -GatewayOnly`，请重新运行完整的 `setup.cmd`。
