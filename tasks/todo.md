# 架构评估与优化方案

> 评估日期：2026-06-10 ｜ 基线版本：v0.3.3 ｜ 测试状态：24/24 通过（`python3 -m unittest discover -s tests`）

## 一、总体评估结论

架构整体**合理**。这是一个 "SKILL.md 协议 + 确定性 Python 脚本 + 文件化工作区" 的 agent skill 包，核心设计决策都站得住：

| 设计决策 | 评价 |
|---|---|
| 分层清晰：SKILL.md（协议）/ references（知识）/ scripts（自动化）/ assets/templates（产物骨架）/ tests / evals | ✅ 职责边界明确 |
| `xhs_cli_utils.py` 作为唯一进程边界：不 import 上游包、校验 `ok/schema_version` envelope、不读写 cookie | ✅ 安全且抗上游漂移 |
| `publish_note.py` 作为唯一发布边界：默认 dry-run、Markdown 泄漏检测、action log、发后验证 | ✅ 写操作防护到位 |
| 01→06 编号产物 + `diagnose_workspace.py` 实现可恢复的状态机 | ✅ 跨会话续作的关键 |
| 零第三方依赖（仅标准库） | ✅ 可移植性好 |
| lessons/*.json → playbook.md 的客户偏好学习闭环 | ✅ 思路好，但实现有缺陷（见 P0-2） |
| 工作区数据放 `~/.growth/vault/`，与 skill 包分离 | ✅ 客户数据不进 repo |

主要问题集中在：**构建产物入库、playbook 双格式冲突、跨脚本重复代码、测试覆盖不均、遗留路径兼容逻辑堆积**。以下按优先级列出。

---

## 二、优化任务清单

### P0 — 正确性 / 一致性风险

- [ ] **P0-1 解决 `dist/openclaw/` 构建产物入库的漂移风险**
  - 现状：`dist/openclaw/` 是 `build_openclaw.py` 的全量拷贝并提交进 git，约占仓库一半体积。任何 scripts/references 改动后忘记重新 build 就会发布过期代码（目前靠人肉保持同步）。
  - 方案（二选一）：
    - a) 把 `dist/` 加入 `.gitignore`，发布时由 CI / release 流程现场构建（推荐）；
    - b) 保留入库，但加一个测试用例：运行 `build_openclaw.py` 后断言 `dist/` 与源文件无 diff，防止静默漂移。

- [ ] **P0-2 统一 playbook.md 的双格式冲突**
  - 现状：`build_playbook.py` 生成"分节模板"格式（Title Preferences 等小节），而 `learn_client_edits.py` 的 `write_playbook` 生成"规则表格"格式。`playbook_utils.load_playbook_rules` 只能解析表格格式——先跑 `build_playbook.py` 再跑 `learn_client_edits.py` 会整体覆盖前者，且模板格式下所有生成器读到 0 条规则。
  - 方案：确立 **lessons/*.json 为机器可读的唯一事实源**，playbook.md 仅作为人类可读渲染视图；`load_playbook_rules` 改为从 lessons 汇总（或生成 playbook.json），废弃或重写 `build_playbook.py` 使其与表格格式兼容。

- [ ] **P0-3 修复 `publish_note.py` 发布成功但验证失败时的误报**
  - 现状：`xhs post` 成功后若后续 `my-notes` 验证调用抛 `XhsCliError`，整体走异常路径、退出码非零，action log 记成失败——但笔记实际已发出。重试会导致重复发布。
  - 方案：把 post 与 verify 拆成两段 try；post 成功即记录 note_id 与成功日志，verify 失败单独降级为 `DONE_WITH_CONCERNS` 类输出。
  - 顺带：日志里 `native_body_check: {"markdown_leaks": []}` 是硬编码常量，应记录真实检测结果。

- [ ] **P0-4 统一默认工作区根路径常量**
  - 现状：`diagnose_workspace.default_workspace_root()` 返回 `~/.growth`，`init_client_workspace.default_workspace_root()` 返回 `~/.growth/vault`，同名函数语义不同；`PLATFORM = "xiaohongshu"` 在 4+ 个文件重复定义。
  - 方案：抽到共享模块（如 `scripts/workspace_paths.py`），单点定义 vault 根、platform 名、`REQUIRED_FILES` 清单。

### P1 — 结构 / 可维护性

- [ ] **P1-1 收敛跨脚本重复代码**
  - `parse_metadata`：`build_daily_ops.py` 自带一份，应改用 `workspace_parsing`；
  - `read_text`：`learn_client_edits.py` 重复定义；
  - 日历表格解析：`learn_client_edits.extract_calendar_rows` 与 `build_daily_ops.parse_calendar_rows` 逻辑重复；
  - `slugify`：`collect_xhs_research.py`（保留 CJK）与 `init_client_workspace.py`（仅 ASCII）两份实现行为不一致，需统一或明确命名区分；
  - 标题特征启发式：`collect_xhs_research.infer_hook_angle` 与 `generate_content_calendar.infer_title_family/title_features` 对 question/number/warning 的判定逻辑三处重复，应抽成共享的 title heuristics 模块。

- [ ] **P1-2 拆分 `collect_xhs_research.py`（786 行）**
  - 现状：单文件混合了 CLI 参数、关键词播种、xhs 编排（重试/限速）、证据脱敏落盘、Markdown 报告渲染五种职责。
  - 方案：至少拆出 `research_report.py`（build_markdown 及表格渲染）与采集编排两层；`run_and_record` 的重试与限速逻辑可下沉到 `xhs_cli_utils`，让其他需要节流的脚本复用。

- [ ] **P1-3 清理 `diagnose_workspace.py` 的遗留布局兼容逻辑**
  - 现状：`discover_workspace_dirs` + `workspace_layout_priority` 同时支持 3 种历史目录布局（git 历史上有两次工作区迁移），优先级打分难以理解和测试。
  - 方案：提供一次性 `migrate_workspace.py`，把旧布局迁到 `~/.growth/vault/<profile>/xiaohongshu/`；发现逻辑只认规范布局 + 打印"检测到旧布局，请先迁移"的提示，删除优先级打分。

- [ ] **P1-4 补齐测试盲区并加 CI**
  - 现状：`collect_xhs_research` 有 465 行高质量测试（fake xhs 二进制方案很好），但最复杂的 `generate_content_calendar.py`（535 行）、`learn_client_edits.py`（模式检测阈值逻辑）、`score_health.py`、`diagnose_workspace.py` 完全没有测试；仓库无 CI 配置。
  - 方案：
    - 为 calendar 生成（playbook 规则注入、benchmark 锚定）、edits 模式检测（emoji/标题长度/发文量阈值）、health 评分（tier 边界、exit criteria）补单测；
    - 加 GitHub Actions：`unittest discover` + P0-1 的 dist 同步检查。

- [ ] **P1-5 健康评分阈值与 references 文档解耦风险**
  - 现状：`score_health.py` 硬编码 tier 边界（200/500/2000/2万/10万）、exit criteria（≥5 篇、均播 ≥500、互动率 ≥3%），同样的数字在 `references/diagnosis-rubric.md` 里以文档形式存在，两处可能漂移。
  - 方案：阈值集中到单一数据文件（如 `assets/diagnosis-thresholds.json`），脚本读取、reference 文档引用之；或至少加注释互相锚定 + 测试断言关键阈值。

### P2 — 打磨 / 低风险改进

- [ ] **P2-1 evals.json 缺少执行器**
  - 现状：`evals/evals.json` 定义了 2 个场景与 assertions（file_exists / behavior_check），但仓库内没有任何 runner 消费它。
  - 方案：要么写一个最小 eval runner（至少跑通 file_exists 断言），要么在 README 标明这是给外部评测框架用的描述性文件。

- [ ] **P2-2 SKILL.md 中运行时硬编码**
  - 现状：front-matter description 写死 "Use when **Codex** needs..."，但同一份 SKILL.md 也分发到 OpenClaw（dist）并配有 `agents/openai.yaml`，措辞与多运行时分发矛盾。
  - 方案：description 改为运行时中立的措辞（"Use when the agent needs..."）。

- [ ] **P2-3 `collect_xhs_research.run_and_record` 小瑕疵**
  - 非临时性错误返回前也会执行 `sleep_between_commands`（多睡一次无意义）；循环正常结束的 `unknown_failure` 分支实际不可达，可简化。

- [ ] **P2-4 `score_health.py` 缺少时间窗口**
  - 现状：对 metrics.csv 全量行取均值，老数据会稀释近期表现，与"诊断当前账号状态"的意图不符。
  - 方案：加 `--recent N`（默认取最近 10 条）或按日期窗口过滤，报告中注明取样范围。

- [ ] **P2-5 证据脱敏的可追溯性权衡需文档化**
  - 现状：`sanitize_evidence` 会从落盘证据中剥离 `user_id`/url/token 等字段，副作用是证据不可复跑（无法用证据反查账号）。这是合理的安全取舍，但未在 README / references 中说明。
  - 方案：在 `references/research-rubric.md` 或 README 补一段"证据脱敏策略与影响"。

- [ ] **P2-6 增加 CHANGELOG**
  - 现状：只有 VERSION 文件（0.3.3），版本间变更只能翻 git log。
  - 方案：加 `CHANGELOG.md`，release 时与 VERSION、dist 构建一起更新。

---

## 三、建议执行顺序

1. **第一批（修正确性）**：P0-2 → P0-3 → P0-4（都是小改动，互不冲突）
2. **第二批（防回归）**：P1-4 加 CI 与测试，再做 P0-1（dist 策略需要 CI 配合）
3. **第三批（重构）**：P1-1 → P1-2 → P1-3（有测试兜底后再动结构）
4. **第四批**：P1-5 与 P2 项按需穿插

## 四、明确不建议做的事

- **不要把 scripts/ 改造成 pip 包**：skill 的分发模型就是 agent 直接 `python3 scripts/foo.py`，扁平脚本 + 少量共享模块是正确形态，引入打包/安装步骤反而破坏可移植性。
- **不要给生成器引入 LLM 调用**：标题/日历生成器输出机械候选是刻意设计——确定性脚本产骨架、agent 负责润色，这个分工应保持。
- **不要合并 `_library` 与 `<profile>` 工作区**：平台语料与客户交付态分离是该架构的核心约束，SKILL.md 已有清晰规则。
