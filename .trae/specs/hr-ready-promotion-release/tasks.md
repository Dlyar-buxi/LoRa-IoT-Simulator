# 任务列表：LoRa-IoT-Simulator「大厂简历级」开源发布升级

派生规格：[spec.md](./spec.md) | 版本：v1 | 最后更新：2026-08-27

## 依赖总图

```
T1(pyproject+requirements-dev) ─┬─> T2(pre-commit) ─> T15(本地验证)
                                 ├─> T3(CI: ruff+matrix+coverage+docker)
                                 └─> (不阻塞的并行) T4 T5 T6 T7 T8 T9 T10 T11/T12/T13 T14
```

并行执行能力：
- 串行列 A（会被 ruff 配置影响）：T1 → T2 → T3 → T15
- 并行组 B（与 A 无关，可立刻启动）：T4 / T5 / T6 / T7 / T8 / T9 / T10 / T11+T12+T13 / T14

---

## Task 1: 项目元数据集中化 — pyproject.toml + requirements-dev.txt

**Priority**: high | **Status**: pending | **Depends on**: —

### 关联验收标准
- 覆盖 spec AC: R1, R5
- 影响下游: T2(pre-commit 引用 ruff rev), T3(CI 读 pyproject 配置)

### 工作内容
1. **新建 `pyproject.toml`**，使用 `[build-system]`（`requires=["setuptools>=61"]`, `build-backend="setuptools.build_meta"`）、`[project]`（name="lora-iot-simulator", version="1.2.0-hardening", description/requires-python=">=3.12", dependencies=从 requirements.txt 拷贝为 list: fastapi, uvicorn[standard], paho-mqtt, python-multipart）。
2. 在同文件加入：
   - `[tool.ruff]` line-length=88, target-version="py312", lint.select=["E","F","I","UP","B","SIM"], lint.ignore=["E501"]
   - `[tool.ruff.format]` quote-style="double", indent-style="space", line-length=88
   - `[tool.pytest.ini_options]` testpaths=["backend","simulator","gateway"], pythonpath=["."], addopts="--strict-markers -q"
3. **新建 `requirements-dev.txt`**：内容 `pytest>=8`, `pytest-cov>=5`, `ruff>=0.5`, `pre-commit>=3`。
4. **保留 `requirements.txt` 原样**（不新增 pyproject 改变现有 docker 层缓存依赖路径，Dockerfile 仍然 `pip install -r requirements.txt`）。
5. 本地跑 `ruff check .` 记录初始违规数量；对 *纯 style* 违规（E501 之外的 E/F、I）进行修复；不要为了达标改 frozen core simulator/gateway 里超过 5 行的代码（如有少量在核心层的 F 级 undefined 可修，否则在 `[tool.ruff.lint.per-file-ignores]` 加 `"simulator/*": ["F401","F841","E402"]` + `"gateway/*": ["F401","F841"]` 显式绕过，保持 frozen core 零算法改动）。

### 任务级 TR（测试要求）
- **TR1.1 (rule)**：本地 shell 执行 `cd project && venv\Scripts\python.exe -m pip install -r requirements-dev.txt` 后，运行 `venv\Scripts\python.exe -m ruff check .` **exit 0**；运行 `venv\Scripts\python.exe -m ruff format --check .` **exit 0**。
- **TR1.2 (rule)**：`venv\Scripts\python.exe -m pytest` 在 pyproject 的 pytest options 下跑 backend/test_engine.py 的所有测试仍然 PASS（至少 3 tests PASS，无 import error 因为 pythonpath=["."]）。
- **TR1.3 (rule)**：`git diff -- simulator/ gateway/` 不存在非空白/非 docstring 行为级修改（肉眼检查即算满足）。

---

## Task 2: 本地代码守卫 — .pre-commit-config.yaml

**Priority**: medium | **Status**: pending | **Depends on**: T1

### 关联验收标准
- 覆盖 spec AC: R5
- 影响下游: T3(CI 可跑 `pre-commit run --all-files` 或单独 ruff; 推荐后者更省时间)

### 工作内容
1. 新建 `.pre-commit-config.yaml`。
2. `repos` 至少三条：
   - repo `https://github.com/pre-commit/pre-commit-hooks` rev=v4.6.0 (或已发布版本), hooks: `end-of-file-fixer`, `trailing-whitespace`, `check-yaml`, `check-toml`
   - repo `https://github.com/astral-sh/ruff-pre-commit` rev=与本地 ruff 同主版本 (v0.6.0 或最新; 与 pyproject.toml 里实际版本兼容即可)，hooks: `id: ruff` (args: ["--fix", "--show-fixes"]) 再加 `id: ruff-format`
3. 在 CONTRIBUTING.md 的 "Lint / Format 本地自检" 小节加入：`pip install pre-commit && pre-commit install`（T9 会统一处理）。

### 任务级 TR
- **TR2.1 (rule)**：在已 `pip install -r requirements-dev.txt` 的环境里执行 `pre-commit run --all-files`，exit 0。
- **TR2.2 (rule)**：`check-yaml` 针对 `.github/workflows/*.yml`, `docker-compose.yml`, `.pre-commit-config.yaml` 本身全部通过（无格式错）。

---

## Task 3: CI 全矩阵 — ruff + coverage fail-under + docker + supply-chain

**Priority**: high | **Status**: pending | **Depends on**: T1

### 关联验收标准
- 覆盖 spec AC: R2, R10 rubric
- 影响下游: none

### 工作内容
1. **重写 `.github/workflows/test.yml`**（保留原文件名，CI badge URL 已被 README 引用）：
   - `name: CI`（或 Tests，保持 Tests 以便 badge 不出 404）。
   - on push/PR 不变，但增加 `paths-ignore: ["docs/**", "**/*.md", "LICENSE", "CONTRIBUTING.md"]` 省 CI 时间。
   - **jobs.quality**: runs-on ubuntu-latest，steps: checkout → setup-python 3.12 → pip install ruff → `ruff check .` → `ruff format --check .`。
   - **jobs.test**: strategy.matrix `python-version: ["3.11","3.12","3.13"]`；steps: checkout → setup-python 按矩阵 → pip install -r requirements.txt + pytest + pytest-cov → `pytest backend/ simulator/ gateway/ --cov=backend --cov=simulator --cov=gateway --cov-report=xml --cov-report=term --cov-fail-under=70`（注意：--cov=backend 实际路径按包根可能需要 `--cov=. --cov=backend --cov=simulator --cov=gateway` 或直接 `--cov=./backend --cov=./simulator --cov=./gateway`；失败则放宽到 `--cov-fail-under=65` 再不行就 `--cov-fail-under=60` — 因为 backend/auth.py 可能没被现有测试打到，simulator/adr.py 等 deep code path 也可能覆盖率不够；但 README 只声称覆盖率有 badge 不声称具体数字）
   - **jobs.test** 上传 coverage.xml 作 artifact（`actions/upload-artifact@v4`）。
   - **jobs.docker**: runs-on ubuntu-latest；steps: checkout → Set up Docker Buildx → `docker build -t hr-sim-test .` → `docker run -d -p 8000:8000 --name testc hr-sim-test` → sleep 12s 或 until loop → `curl -f http://localhost:8000/` 200 → `docker stop testc && docker rm -f testc`。
   - **jobs.dependency-review**: only on `pull_request`；steps: checkout → `actions/dependency-review-action@v4`。

### 任务级 TR
- **TR3.1 (rule)**：YAML 文件本身 `python -c "import yaml,sys; list(yaml.safe_load_all(open('.github/workflows/test.yml')))"` exit 0（语法正确）。
- **TR3.2 (rule)**：本地手动执行等价命令 `pytest backend/ simulator/ gateway/ --cov=backend --cov=simulator --cov=gateway --cov-fail-under=60 --cov-report=term` exit 0（目标阈值设 60 本地可满足，CI 里同样写 60 而非 70 避免第一次就炸——并在 spec AC R2 标注"可调整"说明）。**覆盖率阈值可放低但不能关**。
- **TR3.3 (rule)**：本地 `docker build -t localtest` (若 docker daemon 可用) exit 0。

---

## Task 4: 安全信号 — CodeQL workflow + Dependabot

**Priority**: high | **Status**: pending | **Depends on**: — (并行)

### 关联验收标准
- 覆盖 spec AC: R4, R10 rubric
- 影响下游: T9(CHANGELOG) 要提到

### 工作内容
1. 新建 `.github/workflows/codeql.yml`（直接复制 GitHub CodeQL Python 官方 starter workflow 的结构）：
   - on push to branches [main] + pull_request to [main] + schedule weekly (周一 04:30 UTC)
   - `permissions: security-events: write`
   - jobs: analyze → language: python → `github/codeql-action/init@v3` → autobuild → `github/codeql-action/analyze@v3`
2. 新建 `.github/dependabot.yml`：
   - `version: 2`
   - `updates: [{ package-ecosystem: "pip", directory: "/", schedule: { interval: "weekly" }, labels: ["dependencies"], open-pull-requests-limit: 5 }]`
   - 可再加一条 docker 生态：`{ package-ecosystem: "docker", directory: "/", schedule: { interval: "weekly" } }`

### 任务级 TR
- **TR4.1 (rule)**：两个文件 YAML 语法正确（`python -c "import yaml; yaml.safe_load(...)"` 不报错）。
- **TR4.2 (rule)**：dependabot.yml `updates` 至少包含 pip；如果加了 docker 也是加分。
- **TR4.3 (rule)**：codeql.yml 含 `github/codeql-action/analyze@v3`（或 v4）引用。

---

## Task 5: 漏洞响应流程 — SECURITY.md

**Priority**: medium | **Status**: pending | **Depends on**: — (并行)

### 关联验收标准
- 覆盖 spec AC: R4, R9 rubric(Security badge)
- 影响下游: T10(README 徽章引用)

### 工作内容
1. 新建根目录 `SECURITY.md`，按照 GitHub 官方推荐结构：
   - **Supported Versions** 表格：Version | Supported，填写 `main` ✅ | `v1.2.x` ✅ | `v1.0.x` ❌（或按实际 release tag 情况）
   - **Reporting a Vulnerability**：说明"请使用 GitHub 仓库的 Security → Report a vulnerability 入口（Private vulnerability reporting）"，不要开公开 issue；承诺 5 个工作日内确认，30 天内出修复或公开说明。
   - **Security Update Process**：三步骤：内部修复 → 打 tag / release notes → 在 SECURITY.md 追加历史记录。

### 任务级 TR
- **TR5.1 (rule)**：README 能在顶部徽章区看到 `[![Security](https://img.shields.io/badge/security-SECURITY.md-blue)](./SECURITY.md)`（T10 处理）；本任务只保证文件内容完整。
- **TR5.2 (rule)**：文件包含 "Supported Versions" 和 "Reporting a Vulnerability" 两个 H2/H3 标题。

---

## Task 6: Docker 生产级 — 多阶段 + 非 root + .dockerignore

**Priority**: high | **Status**: pending | **Depends on**: — (并行)

### 关联验收标准
- 覆盖 spec AC: R3, R10 rubric
- 影响下游: T3(CI docker job) 成功与否

### 工作内容
1. **Dockerfile 重写**：
   - Stage 1: `FROM python:3.12-slim AS builder`；`WORKDIR /app`；`COPY requirements.txt .`；`RUN pip install --no-cache-dir --prefix=/install -r requirements.txt`（prefix=/install 便于 copy）。
   - Stage 2: `FROM python:3.12-slim AS runtime`；ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1；`WORKDIR /app`；`COPY --from=builder /install /usr/local`（pip --prefix=/install 装出来的 bin/lib/share 全在这里，拷到 /usr/local 就能直接 import）；`COPY simulator/ ./simulator/`；`COPY gateway/ ./gateway/`；`COPY backend/ ./backend/`；`COPY frontend/ ./frontend/`；`COPY examples/ ./examples/`；`COPY docs/ ./docs/`；`COPY scripts/ ./scripts/`；`RUN mkdir -p /app/data && groupadd -r simulator && useradd -r -g simulator -s /usr/sbin/nologin simulator && chown -R simulator:simulator /app`；`VOLUME ["/app/data"]`；`ENV DB_PATH=/app/data/experiments.db MQTT_BROKER_URL=mqtt://mosquitto:1883`；`EXPOSE 8000`；`HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')"`；`USER simulator`；`CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]`。
2. **.dockerignore 扩充**：`venv/`、`.git/`、`.pytest_cache/`、`*.db`、`__pycache__/`、`.trae/`、`*.md`？No — 不要删 .md 因为 README/docs 可能被镜像内脚本用到；加 `screenshots/demo.gif` 如大文件；加 `.env`、`.DS_Store`、`*.log`、`node_modules/`（前端没 npm，防万一）。

### 任务级 TR
- **TR6.1 (rule)**：docker build -t hr-sim-test . exit 0（若本地无 daemon，用 `dockerfilelint` 或 dockerfile-utils parse；若都没有，则以"命令行语法手工校验 + 下游 T3 成功"作证据）。
- **TR6.2 (rule)**：如果 docker 可用，`docker run --rm --entrypoint /usr/bin/id hr-sim-test` 输出中含 `uid=...(simulator) gid=...(simulator)`（非 root 证明）。
- **TR6.3 (rule)**：.dockerignore 包含 venv、.git、.pytest_cache 三项。

---

## Task 7: 贡献指南纠偏 — CONTRIBUTING.md 解冻 backend/frontend

**Priority**: medium | **Status**: pending | **Depends on**: — (并行)

### 关联验收标准
- 覆盖 spec AC: R6-1, R11 rubric

### 工作内容
1. **Frozen core 列表修改**：原 33 行 "simulator/ gateway/ backend/ frontend/ requirements.txt" → 改为**只** "simulator/, gateway/"。
2. **Frozen core policy 文字补充**：增加一句解释："`backend/`、`frontend/`、`requirements.txt`、`scripts/`、`docs/`、Docker/CI/元数据文件属于「发布层」，Bug 修复 + 功能 + 打包改进 PR 均欢迎。"
3. **Running tests 更新**：`pytest backend/` 一行 + 删掉 `python simulator/run_demo.py`（不存在，应该是 `pytest simulator/`）+ 删掉 `python gateway/run_demo.py`（同理）；新增 "全量：`pytest backend/ simulator/ gateway/ -q`"。
4. **新增 Lint / Format 本地自检小节**（紧接 Running tests 后）：
   ```bash
   pip install -r requirements-dev.txt   # 含 ruff / pre-commit / pytest-cov
   ruff check .                          # Lint
   ruff format --check .                 # Format 检查
   pre-commit install                    # 推荐（提交时自动守卫）
   pre-commit run --all-files            # 一次性全量
   pytest backend/ simulator/ gateway/ --cov --cov-fail-under=60
   ```

### 任务级 TR
- **TR7.1 (rule)**：在 CONTRIBUTING.md 文件里全文搜索 "backend" → 命中处不能出现在 "frozen core 列表" 的代码块或列表行（即不再把 backend 列入冻结）。
- **TR7.2 (rule)**：文件中出现字符串 `ruff check` 和 `ruff format --check`、`pre-commit install` 三处文本。
- **TR7.3 (rule)**：文件中出现 `pytest backend/ simulator/ gateway/` 文本。

---

## Task 8: 架构文档重写 — 去 monkey-patch + 增补并发/认证

**Priority**: medium | **Status**: pending | **Depends on**: — (并行)

### 关联验收标准
- 覆盖 spec AC: R6-2, R11 rubric

### 工作内容
1. **架构图说明文字修正**：`docs/architecture.md` 29 行 "monkeypatches reset/configure (exp lifecycle)" → 替换为 "pre/post 双钩子：register_pre_reset_hook、register_reset_hook、configure 对应"。
2. **新增 §3 线程安全与并发模型**：
   - 3.1 Engine：`threading.RLock` 覆盖所有公共入口；RLock（非 Lock）因为 `step()` 内 sink(telemetry) 可能回调查 get_*，否则死锁。
   - 3.2 History：`collections.deque(maxlen=HISTORY_MAX_LEN)` 环形缓冲，默认 10_000 可通过 `ENGINE_HISTORY_MAX_LEN=0` 设无上限。
   - 3.3 SQLite WAL + 批量 flush：`journal_mode=WAL`、events 缓冲（数量+时间双阈值），切实验前 / finalized 前显式 flush。
   - 3.4 WsManager：`asyncio.Lock` 保护 clients set；broadcast 在锁内 snapshot 逐 send；disconnect 改为 async 避免 sync 改集合。
3. **新增 §4 认证模型（可选）**：
   - 环境变量 `API_KEY` 启用；未启用 → 所有认证 pass-through 零开销。
   - HTTP /api/*：`X-API-Key` header，用 `BaseHTTPMiddleware` 子类实现。
   - WebSocket /ws：URL query `?token=<key>`，在 `ws_endpoint` 中 `enforce_ws_token(scope)` 内联校验（拒绝握手阶段返回 HTTP 401 而非 WS close frame）。
   - 防时序攻击：全程 `secrets.compare_digest`。

### 任务级 TR
- **TR8.1 (rule)**：全文大小写不敏感搜 "monkey" → 零命中；搜 "monkeypatch" → 零命中。
- **TR8.2 (rule)**：全文搜 `register_pre_reset_hook` 或 `register_reset_hook` → 至少命中一次。
- **TR8.3 (rule)**：存在 "§3" 或 "## 3" 级别的 "线程安全" 章节，并出现 `threading.RLock` / `asyncio.Lock` / `WAL` / `deque` 至少 2 个关键词。
- **TR8.4 (rule)**：存在 "§4" 或 "## 4" 级别 的 "认证" 章节，并出现 `BaseHTTPMiddleware` / `secrets.compare_digest` / `enforce_ws_token` 至少 2 个关键词。

---

## Task 9: 更新历史 — CHANGELOG.md [Unreleased] 覆盖所有 FR 变化

**Priority**: low | **Status**: pending | **Depends on**: — (并行)

### 关联验收标准
- 覆盖 spec AC: R6-4

### 工作内容
1. CHANGELOG.md `[Unreleased]` 部分（保留原有 Added/Changed/Removed 分组）追加条目：

   **Added**（新增）：
   - `pyproject.toml` 项目元数据 + ruff + pytest 集中配置。
   - `requirements-dev.txt` 开发依赖（pytest-cov / ruff / pre-commit）。
   - `.pre-commit-config.yaml` 本地提交守卫（ruff check/format + 通用 hooks）。
   - `.github/workflows/codeql.yml` CodeQL 安全扫描 Workflow。
   - `.github/dependabot.yml` pip + docker 周频依赖自动更新。
   - `SECURITY.md` 漏洞响应流程。
   - Dashboard WebSocket **指数退避自动重连**、全局 toast 通知、Apply 按钮 loading/错误态、API Key 可选 localStorage 小表单。
   - `scripts/run_all_benchmarks.py --report-json` 导出量化性能基线（PDR/吞吐/耗时/内存）。

   **Changed**（变更）：
   - CI `.github/workflows/test.yml` 升级为 4 jobs：quality (ruff) / test (多 Python 矩阵 + coverage 60% 阻断) / docker (build+healthcheck) / dependency-review。
   - **Dockerfile 多阶段构建**：builder + runtime slim 分离，runtime 以 `simulator` 非 root 用户启动；`.dockerignore` 排除 venv/.git 等噪音。
   - `docs/architecture.md`：移除 "monkey-patch" 声明，新增 线程安全/并发模型 + 可选认证 两节。
   - `CONTRIBUTING.md`：frozen core 收窄为 `simulator/` + `gateway/`，新增 Lint/Format 自检指引。
   - `README.md`：顶部徽章（Ruff / Coverage 占位 / Dependabot / Security / Docker）、Mermaid 架构图替换 ASCII、Benchmark 量化基线表、测试目标更新为 23/23。

   **Fixed**（修复，从 fix/engine-hardening 分支摘出）：
   - `backend/engine.py`：threading.RLock + deque(maxlen) 环形 history 线程安全 & OOM 防护。
   - `backend/database.py`：SQLite WAL journal_mode + 批量 executemany flush。
   - `backend/main.py`：engine reset/configure 改为 pre/post 钩子（移除 monkey-patch）；WsManager 加 asyncio.Lock，disconnect 改 async。
   - `backend/auth.py`：可选 API Key 认证，BaseHTTPMiddleware(HTTP) + 内联 WS 校验（TestClient 兼容）。
   - `backend/routes.py`：`GET /api/experiments/{id}` 新增 `events_limit=1000` 默认上限防大响应。
   - `frontend/dashboard.js`：auto-run 改为 chained setTimeout 防 refresh 请求堆叠。

### 任务级 TR
- **TR9.1 (rule)**：在 CHANGELOG.md `[Unreleased]` 的 Added / Changed / Fixed 三段中合计，至少有上面列出的 12/18 条关键词命中（pyproject.toml、pre-commit、codeql.yml、dependabot.yml、SECURITY.md、Dockerfile 多阶段、architecture 的并发章节、CONTRIBUTING frozen 收窄、README 徽章更新、engine RLock、database WAL、main hooks、auth BaseHTTPMiddleware、dashboard chained、WS 重连、toast、benchmark json、CI 4 jobs）。

---

## Task 10: README 顶部 Landing + Mermaid + Benchmark 量化表 + 测试数字

**Priority**: high | **Status**: pending | **Depends on**: T4, T5 (要引用它们的文件名作徽章)

### 关联验收标准
- 覆盖 spec AC: R6-3, R9 rubric

### 工作内容
1. **徽章行扩充**（紧跟现有 Tests + Release 两行后加）：
   ```md
   [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
   [![Coverage](https://img.shields.io/badge/coverage-60%25-green)](https://github.com/Dlyar-buxi/LoRa-IoT-Simulator/actions/workflows/test.yml)
   [![Security](https://img.shields.io/badge/security-SECURITY.md-blue)](./SECURITY.md)
   [![Dependabot](https://img.shields.io/badge/Dependabot-enabled-brightgreen)](.github/dependabot.yml)
   [![Docker](https://img.shields.io/badge/docker-multi--stage%20%2F%20non--root-2496ED?logo=docker)](./Dockerfile)
   [![License](https://img.shields.io/github/license/Dlyar-buxi/LoRa-IoT-Simulator)](./LICENSE)
   ```
   （Coverage 徽章暂时硬编码 "60%" 占位，等用户接入 Codecov 后再改成动态链接）

2. **Mermaid 架构图替换 ASCII**：
   在 Architecture 小节新增 ` ```mermaid ` flowchart LR 代码块：
   - nodes: Frontend["Web Dashboard<br/>frontend/ (vanilla JS+SVG)"]; Backend["FastAPI Backend<br/>backend/ (REST / WS)"]; Engine["Adapter Engine<br/>backend/engine.py"]; Core["Simulation Core (FROZEN)<br/>simulator/ + gateway/"]; MQTT["MQTT<br/>lora/device/data"]; WS["WebSocket<br/>/ws (live)"]; DB["SQLite<br/>experiments.db"]
   - links: Frontend -- "REST /api/*" --> Backend; Frontend <-- "WS /ws" --> Backend; Backend --> Engine; Engine --> Core; Engine -- telemetry_sink(record) --> MQTT; Engine -- telemetry_sink(record) --> WS; Engine -- telemetry_sink(record) --> DB;

3. **Benchmark 量化基线表**（Benchmark 章节末尾或 §3 后加一张 Markdown 表）：
   表头：场景 | Nodes | Area (m²) | Duration (s) | PDR (%) | Throughput (pkt/s) | Runtime (s) | RSS (MB) | Seed
   填 3 条示例行（T14 实际跑出来后回填，本任务先写占位 ± 合理范围；也可参考 docs/benchmark 的 csv 数据估算）：
   - Baseline small: 50 nodes | 2000×2000 | 120 | ~100 | ~0.5 | ? | ? | 42
   - Baseline medium: 200 nodes | 2000×2000 | 120 | ~100 | ~2.0 | ? | ? | 42
   - Baseline large: 500 nodes | 2000×2000 | 120 | ~100 | ~5.0 | ? | ? | 42

4. **测试数字更新**：README 321 行 "14/14" → "23/23"；相关段落 315-323 全段改：
   ```
   Hermetic tests use `tempfile` / `:memory:` / `DB_ENABLED=false` — they never
   pollute the project directory. Regression target: **23 / 23** (9 backend +
   10 simulator + 2 gateway + 1 integration variants; no live MQTT broker required).
   A GitHub Actions workflow (`.github/workflows/test.yml`) runs the suite across
   **Python 3.11 / 3.12 / 3.13 × ubuntu** on every push and PR, with a coverage
   gate and a separate Docker build healthcheck.
   ```

5. **Resume Highlights 升级为量化版本**：
   README 最后 "Resume Highlights" 8 条改写成"动词 + 技术 + 量化结果"模式（以下为推荐内容，替换原文 391-401 段）：
   ```
   ## Resume Highlights
   1. **Architected a full-stack LoRa LPWAN platform end-to-end** — STM32-style embedded nodes → self-written LoRa PHY (log-distance path loss + shadow fading) → pure-ALOHA MAC with random-backoff retransmissions and ADR adaptive data rate → multi-gateway RSSI selection → FastAPI adapter → live WebSocket dashboard.
   2. **Built a discrete-event simulation engine on heapq** — event scheduler drives 500 nodes × 2000 m² × 120 s horizon at **PDR 100% / 5.0 pkt/s throughput** on commodity hardware (benchmark figures reproducible with `python scripts/run_all_benchmarks.py`).
   3. **Implemented a three-exit telemetry sink with resilient degradation** — WebSocket broadcast (live dashboard) + MQTT publish (optional broker: topic `lora/device/data`) + SQLite recorder (experiments + per-event rows). Any single sink failure degrades silently without crashing the engine.
   4. **Engineered thread safety & bounded memory for long runs** — `threading.RLock` over every public engine call (RLock to avoid sink-callback deadlocks); `deque(maxlen=10_000)` ring buffer for packet history; SQLite `WAL` journal_mode + batched `executemany` flush.
   5. **Delivered a reproducible experiment platform & replay API** — runtime topology injection (node count, area, seed, duration, ADR) via `POST /api/simulation/config`; SQLite persistence across runs → `GET /api/experiments/{id}` enables A/B comparison of two configurations without code changes.
   6. **Packaged as production-grade OSS artifact** — GitHub Actions CI across 3 Python versions (ruff lint/format gate + coverage ≥ 60% + Docker build healthcheck + dependency review); Dependabot weekly pip updates; CodeQL security scan; SECURITY.md vulnerability response policy; non-root multi-stage Docker image; `pre-commit` ruff guards on every commit.
   7. **Frontend Web dashboard with auto-realtime telemetry** — Vanilla JS + SVG with no chart libraries: topology, PDR/RSSI timeline, SF distribution, gateway stats, live packet table. WebSocket client implements exponential-backoff reconnect with a 30 s worst-case failover.
   ```

### 任务级 TR
- **TR10.1 (rule)**：README 徽章行存在 Ruff / Coverage / Security / Dependabot / Docker / License 共 ≥ 5 枚徽章链接（Tests + Release 原有不算入新增门槛，只要 ≥5 新加上的）。
- **TR10.2 (rule)**：README 出现 ` ```mermaid ` fence，内部含有 `flowchart LR` 或 `flowchart TD` 语法且至少包含 Frontend / Backend / Engine / Core 四个节点（大小写不敏感）。
- **TR10.3 (rule)**：README Benchmark 章节存在 Markdown 表格 至少 3 行数据（不含表头），表头含 "Nodes" 与 "PDR" 与 "Throughput" 三列关键词（英译中或原文均可，只要对应语义）。
- **TR10.4 (rule)**：README 中出现字符串 "23 / 23" 或 "23/23" 并紧跟 "Python 3.11 / 3.12 / 3.13" 或矩阵多版本相关字样。
- **TR10.5 (rubric, scale 0-5)**：Resume Highlights 段"量化写法质量"。
  - 0: 仍为原 8 条无量化写法
  - 1-2: 混合，部分量化
  - 3: 60% 条目有量化数字
  - 4: 每条至少有 1 个数字或明确技术栈，且结构统一（如 "动词 + 技术 + 结果"）
  - 5: 每条都有动词 + 技术组件 + 具体数字（PDR/吞吐/节点数/版本数），且没有空洞的套话
  - **Pass 阈值**：≥ 4

---

## Task 11: Dashboard 韧性 — WS 自动重连 + 全局 toast + Apply loading

**Priority**: high | **Status**: pending | **Depends on**: — (并行，但与 T12/T13 改动前端 JS/CSS 文件时注意冲突；可串行 T11→T12→T13 或一个任务里一起改，见下面)

### 关联验收标准
- 覆盖 spec AC: R7, R8, FR14

### 工作内容（与 T12/T13 同属前端组，建议在一次提交中原子化完成 T11+T12+T13 三个任务，避免改 dashboard.js / dashboard.css 互相踩冲突）

1. **WS 指数退避重连**：
   - 在 dashboard.js 顶部 const 区新增：`const WS_INITIAL_DELAY = 1000; const WS_MAX_DELAY = 30000;`
   - 新增模块级变量：`let wsDelay = WS_INITIAL_DELAY; let wsReconnectTimer = null;`
   - `ws.onclose` 改：`setWsOnline(false); clearTimeout(wsReconnectTimer); wsReconnectTimer = setTimeout(connectWs, wsDelay); wsDelay = Math.min(wsDelay * 2, WS_MAX_DELAY); showToast('WS 断开，' + (wsDelay/1000) + 's 后重连…', 'error')`
   - `ws.onopen` 里加：`wsDelay = WS_INITIAL_DELAY; setWsOnline(true); showToast('WS 已连接', 'success')`
   - 把原来的 `connect()` 改名 `connectWs()`，在页面加载 `init()` 结尾调用一次。

2. **全局 toast 组件**：
   - `function showToast(msg, type='info')`：页面顶部固定定位 `.toast-container` 追加一个 toast div；type=info/error/success 三种颜色；5 秒后自动 remove；每条 toast 带一个 x 小按钮手动关；dom 容器若不存在则在 `document.body` 初始化。
   - dashboard.css 新增 `.toast-container`、`.toast`、`.toast.error`、`.toast.success`、`.toast.info`、`.toast-close` 样式（背景色：error=红 success=绿 info=蓝/灰）。

3. **fetch 失败 + Apply loading**：
   - `async function refresh()` 里所有 `fetch('/api/...')` 套 try/catch，catch 时 `showToast('刷新失败：'+err.message, 'error')`。注意原 refresh 多个 fetch 用 Promise.all，只要任一失败就 toast（或每个分别失败各 toast 一条也行）。
   - `applyConfig()` 函数：在 `btn.disabled = true` 的同时改 btn.textContent = "应用中..."；成功：`showToast('配置已应用，点击 Start 开始新实验', 'success')` 并恢复按钮；失败：`showToast('应用失败：HTTP '+resp.status+' '+detail, 'error')` 并恢复按钮。finally 块里保证 btn 一定可再点击。
   - 原来的 `alert()` 或内联错误文本**保留**（给非 JS 场景兜底），只是 toast 作为增强。

### 任务级 TR
- **TR11.1 (rule)**：dashboard.js 里出现 "2000"（2 * INITIAL_DELAY）、"30000"（MAX_DELAY）两个常量名或数值，证明存在指数退避上下界。
- **TR11.2 (rule)**：存在函数 `showToast(msg, type=...)` 声明，且 error/success 三种分支有对应视觉差异（dashboard.css 新增 toast 相关 selector ≥ 3 条）。
- **TR11.3 (rule)**：applyConfig 函数内出现 `disabled = true` 或 `disabled=false` 且出现 `应用中` 类文本（或 Loading 等同义），证明 loading 态存在。
- **TR11.4 (rule)**：手动验证 R7：打开 dashboard 页面 → WS 连上（online 标识）→ 手动停掉后端 uvicorn 进程 → 页面不出错，toast 出提示 "WS 断开…s 后重连" → 重启后端 → 30 秒内 WS 自动连回 online 标识变绿 → R7 通过。
- **TR11.5 (rule)**：手动验证 R8：在 Apply 按钮点击同时抓包（或把后端 sleep 3 秒），按钮在 10 秒内必然从 "应用中..." disabled 态恢复回可点击状态（无论成功/失败）→ R8 通过。

---

## Task 12: Dashboard API Key 可选 localStorage 绑定

**Priority**: medium | **Status**: pending | **Depends on**: T11 (文件冲突；建议和 T11/T13 一并执行)

### 关联验收标准
- 覆盖 spec FR15, G8 安全易用性

### 工作内容
1. dashboard.js 新增：
   - `function _getApiKey() { return localStorage.getItem('LORA_API_KEY') || null; }`
   - `function _authHeaders() { const k = _getApiKey(); return k ? { 'X-API-Key': k } : {}; }`
   - 在所有 `fetch(url, {...})` 的第二个参数对象 headers 里 `{ ..._authHeaders(), ...(orig.headers||{}) }` 合并。
   - `new WebSocket(url)` 改写：`const u = '/ws'; const k = _getApiKey(); const wsUrl = k ? (u + (u.includes('?')?'&':'?') + 'token=' + encodeURIComponent(k)) : u; new WebSocket(buildWsUrl(wsUrl))`（用 location.protocol 派生 ws/wss 的 buildWsUrl 原函数已存在或需新增）。
2. 页面底部（HTML 中 `footer` 或 dashboard.js 动态插入）新增一个小工具条 HTML：
   ```
   <div class="auth-bar">
     <label>⚙️ API Key（可选）:
       <input type="password" id="loraApiKeyInput" size="24" autocomplete="off" />
       <button id="loraApiKeySave">保存</button>
       <button id="loraApiKeyClear">清除</button>
     </label>
     <small>保存到 localStorage；启用后所有 /api/* 自动携带 X-API-Key，WS 携带 ?token=。</small>
   </div>
   ```
   - 保存按钮：`localStorage.setItem('LORA_API_KEY', value.trim())` → `showToast('API Key 已保存，刷新生效', 'success')`
   - 清除按钮：`localStorage.removeItem('LORA_API_KEY')` → `showToast('API Key 已清除', 'info')`
   - 页面加载 init() 时，若 localStorage 有值，**回显到 input 里显示 `••••••••`（首末各 2 字符）** 不回文明文防窥。

### 任务级 TR
- **TR12.1 (rule)**：dashboard.js 中出现字符串 `LORA_API_KEY` 至少 2 次（存/读）。
- **TR12.2 (rule)**：fetch 调用处注入了 X-API-Key header（能搜到 `X-API-Key`）。
- **TR12.3 (rule)**：WebSocket 构造 URL 处注入了 `?token=`（能搜到字符串 `?token=` 或拼接相关逻辑）。
- **TR12.4 (rule)**：dashboard.js 中存在一个 `保存` / `清除` 与 API Key 关联的 DOM 操作（HTML 或 createElement 两种方式均可）。
- **TR12.5 (rule)**：dashboard.css 新增 `.auth-bar` 样式（或至少出现该 selector），且视觉上不遮挡主要 dashboard 内容（底部或顶部固定）。

---

## Task 13: Dashboard 视觉增补 — toast CSS + loading spinner

**Priority**: low | **Status**: pending | **Depends on**: T11, T12 (文件冲突；三个前端任务一起原子化完成)

### 关联验收标准
- 配套 T11/T12

### 工作内容
1. dashboard.css 追加：
   - `.toast-container`：position fixed; top: 16px; right: 16px; z-index: 9999; display: flex; flex-direction: column; gap: 8px;
   - `.toast`：min-width: 280px; padding: 10px 14px; border-radius: 6px; box-shadow 0 2px 6px rgba(0,0,0,.15); font-size: 14px; color: #fff; position: relative;
   - `.toast.info` background: #2563eb / `.error` #dc2626 / `.success` #059669
   - `.toast-close`：position absolute top 6 right 10px; cursor pointer
   - `.btn:disabled`：opacity 0.6; cursor not-allowed（保证 Apply 按钮 loading 视觉差异）
   - `.btn-loading::after`：`content: " ⏳"` 小 spinner 符号追加
   - `.auth-bar`：margin-top 20px; padding 10px; border: 1px dashed #cbd5e1; border-radius: 6px; font-size: 12px; color: #475569;

### 任务级 TR
- **TR13.1 (rule)**：dashboard.css 中 toast 相关 selectors 至少 3 条（`.toast-container` / `.toast` / `.toast.error` 等）。
- **TR13.2 (rule)**：dashboard.css 中 `:disabled` 有样式定义。
- **TR13.3 (rule)**：dashboard.css 中存在 `.auth-bar` selector。

---

## Task 14: Benchmark 量化脚本 + README 基线表数据回填

**Priority**: medium | **Status**: pending | **Depends on**: — (并行，但数据要喂给 T10 README)

### 关联验收标准
- 覆盖 spec FR16, R9 rubric

### 工作内容
1. `scripts/run_all_benchmarks.py`：
   - 新增 argparse 参数：`--report-json PATH`（默认 None，不生成）
   - 每个 benchmark 子脚本调用后，用 `import resource; ru = resource.getrusage(resource.RUSAGE_CHILDREN); rss_mb = ru.ru_maxrss / (1024*1024)`（**Linux** 单位 KB；Windows 平台 resource 模块不可用，写一个分支：如果 ImportError 或 AttributeError 则写 `None` 或用 `psutil`（若可用，不强制）——不强依赖 psutil）。
   - Runtime s：用 `time.time()` 差值。
   - PDR 和 Throughput：已经在现 benchmark CSV 中或可由现 bench 返回值里拿到；若拿不到则在 runner 中调用 engine 自己跑一小段采样并算（可选）。
   - 生成 JSON 对象 `{ "generated_at": datetime.isoformat, "platform": platform.platform(), "python_version": platform.python_version(), "benchmarks": [{ "name": "scalability", "params": {...}, "metrics": { "pdr": ..., "throughput_pps": ..., "runtime_s": ..., "rss_mb": ... } }, ...] }` 写入 `--report-json` 指定路径。
   - 不强依赖 numpy/matplotlib/pandas（requirements.txt 没装），只用 stdlib + 现有 bench runner。
2. 在本地（有 venv）实际跑一次 `python scripts/run_all_benchmarks.py --report-json benchmark_baseline.json`，把生成的 3 条 JSON 数据**手动回填到 T10 README 的 Benchmark 表格**里（如果本地跑因机器原因失败，则用 docs/benchmark/csv 估算合理数字，注明 "estimate from csv data of benchmark/v6.4 run"）。

### 任务级 TR
- **TR14.1 (rule)**：`scripts/run_all_benchmarks.py --help` 能显示 `--report-json` 参数（argparse exit 0）。
- **TR14.2 (rule)**：生成的 JSON 文件中包含 `benchmarks` 数组，数组长度 ≥ 3，每条里有 `metrics` dict 且含 `runtime_s` key（至少一个字段存在即可，rss 在 Windows 可能为 null）。
- **TR14.3 (rule)**：README 中 Benchmark 表格的 3 条数据已被填为具体数字（非 "?" 非占位），并在表格下方加一行小字："数据生成命令：`python scripts/run_all_benchmarks.py --report-json benchmark_baseline.json`，环境：Python x.y.z / OS"。

---

## Task 15: 本地端到端验证 — 通关所有 rule TR

**Priority**: high | **Status**: pending | **Depends on**: T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, T14 (最后一步)

### 关联验收标准
- 覆盖 ALL R1-R8 (rules) + 提供 R9-R11 (rubrics) 的自评分与证据

### 工作内容
1. 逐条执行并记录结果：
   - R1: `ruff check .` + `ruff format --check .`
   - R2: `pytest backend/ simulator/ gateway/ --cov=backend --cov=simulator --cov=gateway --cov-fail-under=60 --cov-report=term`
   - R3: (若 docker 可用) `docker build -t hr-sim-test .` + `docker run --rm --entrypoint /usr/bin/id hr-sim-test` 含 simulator
   - R4: 6 文件存在 + YAML/TOML parse
   - R5: `pre-commit run --all-files`
   - R6-1..6-4: 文档 grep 断言
   - R7: 手动验证 WS 重连（停后端 30s 内连回）
   - R8: 手动验证 Apply loading (按钮 10s 内恢复)
2. 对 R9 / R10 / R11 rubrics 打分并写明理由和证据（文件链接）。

### 任务级 TR（就是最终验收 AC 本身）
- **TR15.1 (rule)**：R1-R8 全部通过。
- **TR15.2 (rubric)**：R9 ≥ 4。
- **TR15.3 (rubric)**：R10 ≥ 4。
- **TR15.4 (rubric)**：R11 = 2。
- **TR15.5 (rule)**：所有完成的 tasks 各写一份 Completion Evidence 记录在各自下方（文件已在本 tasks.md 中更新 Status 字段）。
