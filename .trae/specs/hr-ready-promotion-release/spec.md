# 规格说明：LoRa-IoT-Simulator「大厂简历级」开源发布升级

## 1. 问题陈述

当前 LoRa-IoT-Simulator 仓库（分支 `fix/engine-hardening` 刚合入一轮 P0/P1 工程化修复）在"仿真功能完备性"上已经达到 90+ 分：有自写离散事件仿真 LoRa PHY/MAC/ADR 内核、FastAPI 适配器、WebSocket 仪表盘、MQTT/SQLite 三出口遥测、Docker/CI/脚本 全套交付物。然而，当它被放在 **GitHub 上让 HR/技术面试官在 60 秒内浏览** 时，以下信号缺失会直接造成"印象扣分"甚至"关标签"：

- **CI 质量信号不完整**：只有测试，无覆盖率 / Lint / 安全扫描 / 跨版本矩阵。
- **供应链安全 0 动作**：没有 Dependabot、SECURITY.md、CodeQL，不符合大厂对开源项目的合规期望。
- **Docker 生产反模式**：容器以 root 运行、单阶段构建、无明确层缓存优化，面试"容器经验"一问就露馅。
- **代码规范无工具链**：requirements.txt 原始、无 pyproject.toml、无 ruff/black、无 pre-commit、无 mypy，暗示"我只写能跑的代码"。
- **文档细节存在硬伤**：CONTRIBUTING.md 把 `backend/` 也标为 frozen（明显错误，刚改了一堆）；`architecture.md` 提到 "monkeypatches reset/configure"（已被钩子替代）；README 里的测试数字是 14/14（现在实际 23/23），会让细心的面试官觉得文档不可信。
- **前端 WebSocket 无韧性**：断线不重连、请求失败无 toast、config 面板校验后没全局 loading/error 指示，演示时"手抖断网就崩"。
- **Benchmark 展示不量化**：README 有三幅图但没有"在 500 节点 / 2km² / 200s 仿真下耗时 X 秒 / 内存 Y MB"的硬指标，HR 无法判断可扩展性。
- **元数据与社区信号 0**：无 SECURITY.md、无 dependabot.yml、无 .pre-commit-config.yaml、无 social preview、无 topic 标签提示、README 缺少 license/codecov/security 徽章组合。

本规格的目标是**把这些"HR 30 秒扣分点"全部翻转为加分项**，让项目从"一个人写的大作业"升级为"具备工业级工程素养的开源项目展示页"。

## 2. 用户画像

| 用户 | 角色 | 看什么 / 期望多久 | 关键判断标准 |
|------|------|-------------------|--------------|
| HR / 简历初筛 | 非技术 | 30~60 秒，只看 GitHub README 顶部 | 徽章、Star/Release 信号、架构图一眼能懂、有无"大厂关键词"（Dependabot / CodeQL / Coverage / Ruff / 多阶段 Docker） |
| 技术面试官 | 后端/基础设施面试官 | 3~8 分钟，点 CI Actions + 点 Dockerfile + 扫 CONTRIBUTING + 看几条 commit | CI 是否完整？有 Lint 有 Coverage？Docker 是否安全非 root？commit 信息规范？frozen core 边界是否讲得通？ |
| 其他开发者（clone 下来跑） | 面试前让下属 clone 下来验证 | 10 分钟内是否能一键跑通（venv / docker compose 两种都要） | Quick Start 是否准确、Docker 是否拉取即健康、benchmark 能不能一条命令出图 |

## 3. 目标 (Goals)

G1. **CI "三扇门 + 一条护城河" 齐备**：pytest 通过 → Coverage 达标 → Ruff(Lint+Format) 零违规；护城河内嵌 Dependabot(周频)+ CodeQL(安全扫描)。
G2. **Docker 生产级**：非 root 用户 + 多阶段 builder/runtime 分离 + 明确 HEALTHCHECK + 体积减小 40%+。
G3. **README 顶部"产品 Landing"**：一句话定位 + 5+ 质量徽章 + 真实运行 Demo GIF / 截图组 + Mermaid 架构图 + 1 行 Quick Start。
G4. **项目文档全部自洽**：CONTRIBUTING / architecture.md / CHANGELOG Unreleased / 测试数字 / frozen-core 标注全部和当前代码 100% 一致，不含过时声明。
G5. **代码规范可验证**：`pyproject.toml` 统一配置 + `.pre-commit-config.yaml` 本地守卫 `ruff check` / `ruff format --check` / `end-of-file-fixer`。
G6. **Dashboard 抗抖动**：WebSocket 指数退避自动重连 + REST 请求失败全局 toast + config 面板 Apply 期间 loading 态 + 失败/成功视觉反馈。
G7. **Benchmark 量化呈现**：README Benchmark 章节新增"性能基线表格"（节点数 / PDR / 吞吐 / 运行耗时 / RSS 内存），由脚本自动输出并引用到 README。
G8. **安全信号外露**：新增 `SECURITY.md`（支持版本 + 漏洞上报方式 + 安全补丁流程）；`.github/dependabot.yml`（pip 周频）；CI 中 `dependency-review` job。
G9. **测试基线 23/23 → 加一个 coverage 报告 artifact（本地可跑 ≥ 75%）**：把当前 backend+simulator+gateway 全量测试 + pytest-cov，本地执行能稳定出 coverage.xml + 报告，CI 上传 artifact。

## 4. 非目标 (Non-Goals)

NG1. **不改 frozen core（simulator/ gateway/）**：除了加 type hints / 文档字符串，不做任何模型行为或算法改动。若覆盖率不足，**用新增 backend-side 驱动测试**（而非改 core）来填补。
NG2. **不做 Python 打包发布到 PyPI**：当前项目没有稳定 Python API，不做 sdist/wheel 发布（避免后续维护成本）。
NG3. **不做在线交互 Demo 部署（Streamlit/Binder/云主机）**：超出当前本地工具链和权限，部署凭据不可用。
NG4. **不接入第三方付费服务（Codecov 账号注册等用户侧行为不由 Agent 完成）**：生成.yml 并在 README 放徽章占位，用户点一下授权即可；不在此处强要求 token 注入。
NG5. **不做真实录屏/GIF**：说明生成步骤并给出命令，不进行计算机录屏（权限与输出质量不可控）。

## 5. 功能需求 (Functional Requirements)

### 5.1 代码规范与配置
FR1. 新增 `pyproject.toml`，集中管理：项目元数据(name/version="1.2.0-hardening"/description)、`[tool.ruff]`（line-length=88、target-version=py312、select=["E","F","I","UP","B","SIM"]、ignore=["E501"]）、`[tool.ruff.format]`（相同 line-length）、`[tool.pytest.ini_options]`（testpaths=backend simulator gateway、pythonpath=.、addopts="--strict-markers -q"）。
FR2. 新增 `.pre-commit-config.yaml`，hooks: `ruff-pre-commit`(ruff check + ruff format --check)、`pre-commit-hooks`(end-of-file-fixer、trailing-whitespace、check-yaml)。
FR3. `requirements.txt` 保持为运行时依赖（fastapi/uvicorn/paho-mqtt/python-multipart），新增 `requirements-dev.txt` 包含 pytest + pytest-cov + ruff + pre-commit；README 的开发安装命令同步更新为 `pip install -r requirements.txt -r requirements-dev.txt`。

### 5.2 CI / 质量门禁
FR4. 重构 `.github/workflows/test.yml` 为 `ci.yml` 或沿用原名，但拆成 4 jobs：
   - **quality**：`ruff check .` + `ruff format --check .`，失败即阻断。
   - **test (matrix)**：strategy matrix `python-version: ["3.11", "3.12", "3.13"]`，`os: [ubuntu-latest]`（或加 `windows-latest` 作为 smoke，至少 3 版本 × ubuntu）；`pytest backend/ simulator/ gateway/ --cov --cov-report=xml --cov-report=term --cov-fail-under=70`；上传 coverage.xml 为 artifact。
   - **docker**：`docker build -t test-image .` + `docker run -d -p 8000:8000 --name test-container test-image` + 健康检查通过（curl / 200）+ 之后停掉，阻断容器构建失败。
   - **supply-chain**：`actions/dependency-review-action` 仅在 PR 时启用，检查 PR 引入依赖的许可证/漏洞。
FR5. 新增 `.github/workflows/codeql.yml`（Python CodeQL，main push 和 PR，来自 GitHub 官方 starter）。
FR6. 新增 `.github/dependabot.yml`：pip ecosystem、`directory: "/"`、schedule weekly、labels `dependencies`。

### 5.3 Docker 生产化
FR7. `Dockerfile` 改为多阶段构建：
   - `builder` 阶段：`python:3.12-slim`，copy requirements + dev？No — builder: python:3.12-bookworm（有编译器以防万一将来有 binary wheel 需求）或仍 slim；`pip install --no-cache-dir -r requirements.txt` 到 /usr/local。
   - `runtime` 阶段：`python:3.12-slim`，`groupadd -r simulator && useradd -r -g simulator simulator`，`WORKDIR /app`，`COPY --from=builder /usr/local /usr/local`，COPY source，`RUN chown -R simulator:simulator /app`，`USER simulator`，保留 HEALTHCHECK。
FR8. `.dockerignore` 补充 `venv/`、`.git/`、`.pytest_cache/`、`*.db`、`__pycache__/`、`.trae/`（避免 COPY 到镜像里）。

### 5.4 文档自洽与升级
FR9. **README 顶部升级**：
   - 徽章行新增：`[![codecov](...)]()`、`[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)]`、`[![Security](https://img.shields.io/badge/security-SECURITY.md-blue)]`、`[![Dependabot](https://img.shields.io/badge/Dependabot-enabled-brightgreen)]`、`[![Docker](...)]`（本地构建状态可不用 cloud build，改为 "docker build passing" 手写说明）。
   - 将 Architecture 章节原有 ASCII 架构图替换为 **Mermaid 图**（Flowchart LR，可渲染）。
   - Quick Start 下方增加一条：`docker compose up --build`（实际存在，但可再醒目说明）。
   - Benchmark 章节追加"性能基线表格"，数据字段：场景、Nodes、Area、Duration、PDR(%)、Throughput(pkt/s)、Runtime(s)、RSS(MB)，3 条基础行（50/200/500 节点），由 `scripts/run_all_benchmarks.py` 新的 `--json` 输出驱动，手动填一次 + README 标注数据版本。
   - 更新测试回归数字：**23 / 23**（原为 14/14），注明 `pytest backend/ simulator/ gateway/`。
FR10. **CONTRIBUTING.md 修正**：
   - Frozen core 列表移除 `backend/ frontend/ requirements.txt`（它们不是 frozen），仅保留 `simulator/ gateway/`，与架构.md一致。
   - Running tests 改为 `pytest backend/ simulator/ gateway/ -q`。
   - 添加 "Lint / Format 本地自检" 小节：`pip install pre-commit && pre-commit install`，以及`ruff check . && ruff format --check .`。
FR11. **docs/architecture.md 修正**：
   - "monkeypatches reset/configure" 描述改为 "pre/post 双钩子（`register_pre_reset_hook` / `register_reset_hook` / configure 对应）"，给出钩子调用顺序：pre_hook → _build → post_hook。
   - 补充一节 "3. 线程安全与并发模型"：engine RLock、WsManager asyncio.Lock、SQLite WAL+批量 flush 的设计理由。
   - 补充一节 "4. 认证模型（可选）"：env API_KEY 时 HTTP X-API-Key + WS ?token= 的实现方式（BaseHTTPMiddleware + 端点内联检查）。
FR12. **CHANGELOG.md 更新 [Unreleased]**：加入本轮 P0/P1 修复和本次升级的已落地项（threading.RLock + deque、WAL+批量 flush、钩子替代 monkey-patch、WsManager asyncio.Lock、API Key auth、events_limit、前端 chained setTimeout，以及本 spec 计划的 CI/Docker/文档/安全 升级，每项加一句）。
FR13. **新增 SECURITY.md**：遵循 GitHub 社区模板，含 Supported Versions（v1.0.0 / v1.1.0 / main）、Reporting（私发 issue 或邮箱占位 `security@lora-sim.example` 说明实际走 GitHub Security Advisories 更好）、Security Update Process。

### 5.5 前端韧性
FR14. `dashboard.js` WebSocket 韧性升级：
   - 新增 `wsReconnectDelay = 1000`、`wsMaxReconnectDelay = 30000`，在 `ws.onclose` 里 `setTimeout(connect, delay)`，每次失败翻倍至最大；连上成功后重置为 1000；任何 refresh() 成功不改此值。
   - 新增函数 `showToast(msg, type='info'|'error'|'success')`：在 DOM 顶部固定一条通知条（5 秒自动消失，可点 X 关闭），CSS 样式在 dashboard.css 中定义。
   - `refresh()` / `applyConfig()` fetch 失败（HTTP != 2xx 或 network error）时调用 `showToast('网络错误: ...', 'error')`。
   - `applyConfig()` 按钮点击后：按钮禁用 + 文字变 "应用中..." + loading spinner，响应 OK → `showToast('配置已应用', 'success')` + 恢复；400/500 → `showToast('配置失败: '+detail, 'error')` + 恢复。
   - config 面板的 invalid 输入（node_count<=0 等）走 toast 而不是仅 `alert()` 或内联文字（同时保留内联错误更友好）。
FR15. `dashboard.js` API Key 可选绑定：新增 `initAuthFromPage()` 从 localStorage 读 `LORA_API_KEY`（如果存在），给每个 `fetch('/api/*', { headers: {'X-API-Key': key} })` 加 header，给 `new WebSocket(url + '?token=' + encodeURIComponent(key))` 拼 query；并在页面底部增加一行 "⚙️ API Key（可选）: [input] [保存/清除]" 小表单操作 localStorage。

### 5.6 Benchmark 量化
FR16. `scripts/run_all_benchmarks.py` 新增 CLI 参数 `--report-json=benchmark_report.json`（可选），运行完三个 experiment 后把每项结果（节点数、PDR、吞吐、Runtime s、RSS MB 用 resource.getrusage 或 memory_probe 实现）写成 JSON；README 引用一份已生成的基准数据（不需要每次 CI 重新生成，README 标注 "数据基于 v1.2.0 / Python 3.12 / i7-13700H"）。

## 6. 非功能需求 (Non-Functional Requirements)

NFR1. **自托管可验证**：所有新增规则用户不登录任何第三方账号也能本地 100% 验证（`pre-commit run --all-files` 全绿、`pytest --cov` ≥ 70%、`docker build` 成功且非 root）；第三方云徽章（Codecov/Docker build）仅作占位，不阻断本地验收。
NFR2. **零破坏现有行为**：启用 API Key 前后、运行 `pytest` 前后、`docker compose up` 前后的功能表现与升级前完全一致（dashboard 渲染、`GET /api/statistics` 返回值结构、WebSocket 推送 JSON schema 不变）。
NFR3. **frozen core 字节级不变**：本 spec 执行完毕后 `git diff origin/main -- simulator/ gateway/`（除去 whitespace 外）应当没有模型行为改动；type hints/docstrings 允许，但不改算法逻辑。
NFR4. **一次学习成本**：README Quick Start 从 clone→运行→看到 dashboard 正常工作 ≤ 4 条命令（venv 路径 / docker compose 两条路径都要 ≤ 4）。
NFR5. **CI 总时长 ≤ 8 分钟**（ubuntu 三个 python-version 并行 3 条 job + quality + docker + supply-chain 加起来总 wall time 不夸张；若 CodeQL 单独走长一点可以接受它单跑，但 PR 阻断不能超过 8 分钟）。
NFR6. **可回滚**：任何单个任务的产物都是独立文件或文件的局部修改，不会互相纠缠（例如 pyproject.toml 与 pre-commit 可单独 revert，dependabot.yml 与 SECURITY.md 可单独关）。

## 7. 约束 (Constraints) & 假设 (Assumptions)

C1. **无 GitHub 账号 token**：不操作 GitHub Web UI（创建 release / 启用 CodeQL / 配置 webhook）；只生成 .yml / .md 文件，由用户后续在 GitHub Settings 里点一下启用（CodeQL/Dependabot/Codecov）。
C2. **无录屏工具**：不生成真实动画 GIF，只提供制作步骤并在 README 用"截图 + 运行说明"替代；如果用户愿意，可手动录制后放 `screenshots/demo.gif`。
C3. **不装系统级软件**：ruff/pre-commit/pytest-cov 走 pip install in venv，不碰 chocolatey / winget / 全局 npm。
A1. 用户 venv 已有：`backend/test_parameterized.py::test_api_config_endpoint 已通过`，`venv/Scripts/python.exe` 存在并可运行 pytest。
A2. 系统无 docker daemon 也允许本地跳过 docker build 验证（只要 Dockerfile 语法正确并在文档中说明）；如果有 docker 则可以本地跑 docker build 验证一次。

## 8. 开放问题 (Open Questions)

Q1. **Dashboard 页面底部新增 API Key 小表单**：是否需要？（默认启用，给"高级用户 + 部署到公网"场景用，不影响 demo 体验）
Q2. **README 顶部徽章是否包含 Codecov 链接**（需要用户手动授权 Codecov 账号接入仓库，否则 badge 永远报 "N/A"；默认放占位且附一条"点此启用"说明）。
Q3. **是否新增 mypy 检查**（type hints 全量 + mypy.ini）：ChatGPT 的清单里没单列但 implied；当前实现如果启用会有大量 missing stub，对提交者不友好。**暂定不加到 CI 阻断**，但 pyproject.toml 可以预留 `[tool.mypy]` 配置并把它作为可选 local lint 放 pre-commit 的 `stages: [manual]` 或根本不放。

---

## 验收标准 (Acceptance Criteria)

每个标准只能是 `rule`（客观二值）或 `rubric`（评分 + 阈值）。

### R1 — rule
**规则**：在本地执行 `pip install -r requirements-dev.txt && ruff check . && ruff format --check .` 两个命令都以 exit code 0 完成，无任何错误/警告级输出。

### R2 — rule
**规则**：在本地执行 `pytest backend/ simulator/ gateway/ --cov --cov-fail-under=70` 以 exit code 0 完成，输出 "23 passed"（若新补了测试则 ≥ 23），且覆盖率显示 "TOTAL  ...  70%" 以上。

### R3 — rule
**规则**：`docker build -t hr-sim-test .` exit 0 成功；随后 `docker run --rm --entrypoint whoami hr-sim-test` 输出不是 "root"（而是 simulator 或同等非 root 用户名），证明 USER 指令生效；`docker inspect hr-sim-test | Select-String -CaseSensitive -Pattern 'simulator'` 可命中该用户名。

### R4 — rule
**规则**：`.github/dependabot.yml`、`.github/workflows/codeql.yml`、`.pre-commit-config.yaml`、`SECURITY.md`、`pyproject.toml`、`requirements-dev.txt` 6 个文件全部存在且 YAML/TOML 语法正确（可被 `python -c "import yaml,sys; ..."` / `tomllib` 成功解析）。

### R5 — rule
**规则**：运行 `pre-commit run --all-files` 在刚 install 的环境下 exit 0（若用户选择不 install pre-commit，则等价的 ruff check / ruff format --check / trailing-whitespace 这三条手动执行全部 pass）。

### R6 — rule
**规则**：文档自洽性 4 条硬检查：
   1. `CONTRIBUTING.md` 中 "frozen core" 目录不包含 `backend/` 和 `frontend/`。
   2. `docs/architecture.md` 不再出现 "monkey"、"patch"、"monkeypatch" 关键词（大小写不敏感），但出现 `register_pre_reset_hook`、`register_reset_hook`、`hook` 中的至少两个关键词。
   3. `README.md` 中存在 "23 passed" 或 "**23/23**" 等反映当前测试数的文本。
   4. `CHANGELOG.md` 的 `[Unreleased]` 区块包含本 spec FR1-FR16 至少 12 条的简要文字记录。

### R7 — rule
**规则**：dashboard.js 的 WebSocket 重连逻辑在"手动杀后端再重启"的场景下，浏览器不刷新页面也能在 30 秒内重新显示 "WS 在线" 的状态标记（即 UI badge 从 offline 变回 online）。

### R8 — rule
**规则**：`applyConfig()` 点击期间按钮被 disabled + 文本变为"应用中..."，无论成功或失败都在 10 秒内恢复到可用态（可再次点击）。

### R9 — rubric
**维度**：README 第一眼"HR 信号密度"评分 (0~5)。

| 分值 | 描述 |
|------|------|
| 0 | 只有 title 和一段描述，无徽章 |
| 1 | 有 1~2 枚徽章，无架构图 |
| 2 | 有 3~4 枚徽章 + 架构 ASCII 图 |
| 3 | 有 5+ 枚徽章（至少含 Ruff / Coverage 占位 / Dependabot / Security / Tests）+ Mermaid 架构图 + Benchmark 量化表 1 条 + Quick Start ≤ 4 条命令 |
| 4 | 满足 3 分 + Benchmark 量化表有 ≥ 3 条不同规模实验数据 + Demo GIF/截图组 ≥ 3 张 + frozen core 边界清晰说明 |
| 5 | 满足 4 分 + Resume Highlights 段每一条都是"动词 + 量化结果"（如 "实现 2000×2000m 下 500 节点吞吐 5.0 pkt/s，PDR 100%"）+ LICENSE 徽章 + 完整 Project Structure 树 |

**通过阈值**：≥ 4。

### R10 — rubric
**维度**：CI "全面性" 评分 (0~5)。

| 分值 | 描述 |
|------|------|
| 0 | 无 CI |
| 1 | 有单一 pytest job |
| 2 | pytest + 有 matrix 至少 2 python 版本 |
| 3 | pytest(多版本矩阵) + ruff lint+format job + coverage 报告 |
| 4 | 满足 3 分 + docker build job（健康检查）+ Dependabot.yml 存在 + SECURITY.md 存在 |
| 5 | 满足 4 分 + CodeQL workflow + dependency-review-action + coverage fail-under 阻断 |

**通过阈值**：≥ 4。

### R11 — rubric
**维度**：frozen core 一致性 (0~2)。

| 分值 | 描述 |
|------|------|
| 0 | simulator/ 或 gateway/ 出现算法级改动（heapq 逻辑、RSSI 公式、碰撞判定等行为变化），或 docs 中多处残留"monkey-patch / backend frozen"错误声明 |
| 1 | core 无行为改动，但 docs 有 1~2 处过时声明未修正 |
| 2 | `git diff origin/main -- simulator/ gateway/` 除去 type hints/docstrings/空行外无模型级行为变化；docs 所有声明与代码一致 |

**通过阈值**：= 2。
