# Failure-Frontier Teaching

一个用于研究模型生成算法代码的本地评测与实验运行框架。项目的核心可复用产物是 `ffjudge`：它在受限 Docker 容器中执行不可信提交，而在可信宿主机上完成测试保管、结果比较和脱敏 verdict 生成。

## 当前状态：阶段性收尾

Failure-Frontier Teaching 的原始研究假设目前**没有得到足够强的证据支持**。已完成的探索性实验适合用于提出后续问题，但不应被表述为对教学材料、失败继承或任一条件优越性的验证性结论。

本阶段暂停的原因：

- 现有重复与谱系实验的样本规模、题目异质性和条件比较资格不足以稳定支持原假设；
- 若干值得继续研究的方向（例如基于失败信息的修复、verdict 驱动的迭代、代码—反馈链）与既有工作存在实质重叠，继续前需要先完成更严格的文献定位与差异化设计；
- 题库审计显示“AC”本身不是语义正确性的充分证据：公开/隐藏覆盖与最大约束压力测试需要持续独立审计。

这不是项目失败的结论。相反，评测器、可信数据边界、实验产物协议、可恢复运行机制和题库审计工具已经构成可用于后续研究的基础设施。

## 可复用的评测基础设施

`ffjudge` 提供以下能力：

- 支持 Python 函数题和 `class Solution` 方法题；
- 宿主机保存完整测试、期望值和 oracle，容器只接收当前调用参数与执行配置；
- 支持 `exact`、`unordered`、`float` 及注册的 `custom` comparator；
- 统一输出 AC、WA、RE、TLE、MLE、SYNTAX_ERROR、提交格式错误与评测器内部错误等结构化 verdict；
- Docker 无网络、只读文件系统、非 root 用户、CPU、内存、PID 和执行时限约束；
- 代码执行时间由容器内 worker 计量；Docker 启动开销不计入题目时限；
- 模型可见的隐藏阶段反馈只包含粗粒度 verdict，不包含隐藏输入、期望值、实际值、用例位置、通过进度或 judge 私有诊断；
- 单用例隔离执行、容器清理和宿主机 OOM 判定。

它适合用于后续的代码生成、调试、修复、agent 训练与评测研究，但不应作为面向不可信公网用户的强安全沙箱。Docker 隔离显著降低风险，却不等同于抵御容器逃逸、内核漏洞、侧信道或同机资源争用的安全边界。

## 题库与测试原则

题目资产位于 `examples/lc-*`。每题通常包括：

- `problem.json`：入口、比较方式和资源限制；
- `public_tests.json`：可公开使用的测试；
- `hidden_tests.json` 与 `stress_tests.json`：仅可信宿主机可读取的正式测试；
- `accepted.py`：参考实现；
- `mutants.json` 和语义 mutant：用于检验测试杀伤性；
- 在适用时提供独立小规模 oracle、复杂度 canary 或 custom checker。

不要把隐藏输入、期望输出、失败用例编号、oracle 中间状态、judge 内部日志或模型的私有实验材料写入 README、公开报告、prompt 或 model feedback。

近期审计已发现少量历史 Teacher AC 在新鲜独立 oracle 或最大约束复放下为 WA/TLE。这说明后续使用题库时应把“AC”理解为“通过当前评测集”，而不是自动等同于数学正确；应持续使用独立 oracle、语义 mutant 和最大约束压力测试进行校准。

## 安装

先安装并启动 Docker Desktop，然后在仓库根目录执行：

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

python -m pip install -e .
ffjudge build
```

不要把临时的 `PYTHONPATH=src` 作为正式安装流程。

## 基本使用

```bash
ffjudge judge \
  --submission examples/lc-0009-palindrome-number/accepted.py \
  --problem examples/lc-0009-palindrome-number/problem.json \
  --tests examples/lc-0009-palindrome-number/public_tests.json \
  --phase public \
  --view internal
```

隐藏阶段的模型视图应使用 `--view model`。它只获得允许暴露的 verdict，而完整测试与 comparison 仍留在宿主机。

## 测试

普通测试：

```bash
python -m unittest discover -s tests
```

Docker 端到端测试默认跳过。Docker 可用时执行：

```bash
# Windows PowerShell
$env:FFJUDGE_RUN_DOCKER_TESTS = "1"
python -m unittest discover -s tests -v

# macOS / Linux
FFJUDGE_RUN_DOCKER_TESTS=1 python -m unittest discover -s tests -v
```

## 实验记录与可重复性

真实模型调用、smoke test 和正式运行产物应写入仓库外目录，且不得提交 API key、Authorization header 或完整环境变量。每次实验至少记录：

- Git commit、runner/baseline 标识、配置与 prompt hash；
- 模型、请求参数、token usage 和响应元数据；
- 题目、条件、尝试轮次、submission hash、verdict 与运行时间；
- 基础设施错误与模型失败的区分；
- 运行恢复关系，以及每个角色实际 Judge 提交次数。

正式的可比较实验应在运行前冻结题库、runner、Docker 基础镜像、配置和 prompt，并在运行后再次校验；不要把 smoke 数据混入正式数据，也不要根据运行中的模型结果修改实验条件。

## 后续工作的建议

恢复研究前，建议先完成：

1. 对原假设和相邻文献进行明确的差异化定位；
2. 预注册可检验的机制假设、主要指标、排除规则和样本量计划；
3. 将题库质量审计（独立 oracle、mutant 杀伤、最大约束性能）作为实验前置门槛；
4. 将“基础设施错误”“当前测试集 AC”和“经独立验证的正确性”分开报告；
5. 优先使用冻结配置下的配对、重复和多题分层分析，而非从少量探索性结果中推断普遍规律。

## 项目结构

```text
failure-frontier-teaching/
├── src/ffjudge/             # judge、harness、models、runner、CLI
├── examples/lc-*/           # 题目、测试、reference、mutant、checker
├── experiments/             # 运行器、配置、baseline 与离线分析
├── tools/                   # 题库生成、校验、审计和报告工具
├── tests/                   # 普通与 Docker E2E 回归
├── Dockerfile
└── pyproject.toml
```

## 许可与使用边界

本仓库是研究原型与本地实验基础设施。使用者负责评估其所在环境的安全需求、第三方模型 API 条款、题目版权/平台条款以及实验伦理要求。
