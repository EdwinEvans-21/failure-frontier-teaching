# Failure-Frontier Teaching

这是 Failure-Frontier Teaching 实验的第一版本地代码评测器。它接收模型生成的 Python 解答，在受限 Docker 容器中运行公开或隐藏测试，并由宿主机上的可信 runner 输出适合后续实验记录的结构化 verdict。

## 第一版支持范围

- Python 函数题与 `class Solution` 方法题
- JSON 格式的公开测试和隐藏测试
- `exact`、`unordered`、`float` 三种结果比较方式
- 通过、答案错误、运行错误、超时、内存超限、语法错误、提交格式错误和评测器错误
- Docker 无网络、只读文件系统、CPU、内存、进程数和权限限制
- 隐藏测试失败时不返回测试输入、期望答案或失败用例编号

第一版故意只覆盖参数和返回值可被 JSON 表示的题目。链表、树、图节点、自定义交互题和标准输入输出题留到后续版本。

## 项目结构

```text
failure-frontier-teaching/
├── Dockerfile
├── pyproject.toml
├── src/ffjudge/
│   ├── cli.py
│   ├── harness.py
│   ├── models.py
│   └── runner.py
├── examples/palindrome_number/
│   ├── README.md
│   ├── problem.json
│   ├── public_tests.json
│   ├── hidden_tests.json
│   ├── accepted.py
│   ├── wrong.py
│   ├── runtime_error.py
│   ├── time_limit_exceeded.py
│   ├── memory_limit_exceeded.py
│   ├── syntax_error.py
│   └── wrong_*.py
├── examples/exact_monotone_paths/
│   ├── README.md
│   ├── problem.json
│   ├── public_tests.json
│   ├── hidden_tests.json
│   ├── accepted.py
│   └── wrong_*.py
├── examples/minimum_operations_binary_transform/
│   ├── README.md
│   ├── problem.json
│   ├── public_tests.json
│   ├── hidden_tests.json
│   ├── accepted.py
│   └── wrong_*.py
├── examples/sorted_gcd_pair_queries/
│   ├── README.md
│   ├── problem.json
│   ├── public_tests.json
│   ├── hidden_tests.json
│   ├── accepted.py
│   └── wrong_*.py
├── examples/maximum_subarray_sum_after_k_swaps/
│   ├── README.md
│   ├── problem.json
│   ├── public_tests.json
│   ├── hidden_tests.json
│   ├── accepted.py
│   └── wrong_*.py
└── tests/
```

## 安装

先安装 Docker Desktop，并确认终端中的 `docker --version` 可用。然后在项目根目录执行：

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

python -m pip install -e .
ffjudge build
```

## 运行示例

评测正确答案：

```bash
ffjudge judge \
  --submission examples/palindrome_number/accepted.py \
  --problem examples/palindrome_number/problem.json \
  --tests examples/palindrome_number/hidden_tests.json \
  --phase hidden \
  --view internal
```

评测错误答案：

```bash
ffjudge judge \
  --submission examples/palindrome_number/wrong.py \
  --problem examples/palindrome_number/problem.json \
  --tests examples/palindrome_number/hidden_tests.json \
  --phase hidden \
  --view model
```

隐藏测试失败的输出类似：

```json
{
  "verdict": "WRONG_ANSWER",
  "phase": "hidden",
  "message": "A hidden case failed."
}
```

`--view internal` 用于写入实验日志，包含通过数量和代码执行时间。`--view model` 用于反馈给 teacher 或 student；隐藏阶段只包含宿主机构造的 verdict、phase 和固定消息，不包含输入、expected、actual、原始输出、原始异常文本、通过数量、失败位置或运行时间。

完成 editable install 后，运行不依赖第三方测试框架的单元测试：

```bash
python -m unittest discover -s tests
```

不要把临时设置 `PYTHONPATH=src` 作为正式安装流程。

## 信任边界与单用例协议

完整测试文件只由宿主机 runner 读取。runner 保存 `expected`，并为每个测试用例启动一个独立容器。容器工作区只包含：

- `solution.py`
- 当前用例的 `args` 与 `kwargs`
- 入口配置和该用例的执行时限

容器看不到 `expected`、完整 `tests.json` 或其他测试用例。容器 worker 只返回 JSON 可表示的 `actual`，或 `syntax_error`、`runtime_error`、`time_limit_exceeded` 等受控执行状态；它不生成 `ACCEPTED` 或 `WRONG_ANSWER`。最终比较、verdict 和反馈脱敏都在宿主机完成。

submission 写入的 stdout/stderr 不会作为 verdict 使用。runner 对两条输出流分别最多保留末尾 1 MiB，并丢弃超出部分，以容纳最大合法 JSON 结果，同时避免无限输出在宿主机无限累计。保留内容仅供内部协议处理，不会进入隐藏阶段的 model feedback。

代码执行时限由容器内 worker 计时；Docker 启动使用单独的宽限时间。宿主机仍有外层 watchdog。容器结束后 runner 通过 `docker inspect` 检查 `State.OOMKilled`，只有该值为 `true` 时才生成 `MEMORY_LIMIT_EXCEEDED`，随后在 `finally` 中删除容器。

## 题目协议

当前第一道实验题是 [LeetCode 9 - Palindrome Number](https://leetcode.com/problems/palindrome-number/)，在本项目中定位为 easy sanity/control problem。它主要验证评测管线、严格返回类型和简单成功样本，不预期产生大量 teacher failure。项目只使用简短的自有题意表述，不复制原始完整题面。

入口为 `Solution.isPalindrome(x)`：`x` 是一个 32 位有符号整数，返回值必须是 Python `bool`。由于使用严格 `exact` 比较，整数 `1` 不能代替 `True`，整数 `0` 也不能代替 `False`。公开测试只保留少量典型情况；具体隐藏输入不会出现在 README、公开题意、model feedback 或测试摘要中。

`problem.json` 定义入口、比较方式和资源限制：

```json
{
  "problem_id": "lc-0009-palindrome-number",
  "title": "Palindrome Number",
  "difficulty": "easy",
  "role": "sanity_control",
  "source_url": "https://leetcode.com/problems/palindrome-number/",
  "entrypoint": {
    "kind": "class_method",
    "class_name": "Solution",
    "method": "isPalindrome"
  },
  "comparison": "exact",
  "limits": {
    "time_seconds": 0.5,
    "memory_mb": 64,
    "cpus": 1.0,
    "pids": 32
  }
}
```

测试文件是 JSON 数组：

```json
[
  {"args": [121], "expected": true},
  {"args": [-121], "expected": false},
  {"args": [10], "expected": false}
]
```

`exact` 要求 JSON 值的类型和值都一致，因此 `true` 与 `1` 不相等。`unordered` 当前只适用于元素可排序的最外层序列，不提供递归的无序集合语义。

`custom` 使用代码内注册的宿主机可信 checker，不从题目配置动态导入代码。`lc-3988-exact-monotone-paths` 当前只是 `medium_upper_construction_candidate`，由 `exact_monotone_paths` checker 验证任意合法构造，不比较唯一标准网格。具体隐藏输入与可行性标签不会出现在公开说明或 model feedback 中。

`lc-3980-minimum-operations-binary-transform` 已作为 `medium_dp_candidate` 加入实验题集，使用 `Solution.minOperations(s1, s2)` 与 `exact` 比较。题目采用项目自有的简短表述，正式隐藏输入、最优操作序列和中间 DP 状态不会写入 README 或 model feedback。

`lc-3312-sorted-gcd-pair-queries` 已作为 `hard_number_theory_candidate` 加入实验题集，使用 `Solution.gcdValues(nums, queries)` 与 `exact` 比较。公开说明不包含正式隐藏输入输出、GCD 计数分布、累计计数或失败用例位置。

`lc-3962-maximum-subarray-sum-after-k-swaps` 已作为 `hard_optimization_candidate` 加入实验题集，使用 `Solution.maxSum(nums, k)` 与 `exact` 比较。公开说明不包含正式隐藏输入输出、最优区间、交换元素、交换收益或有序统计结构的中间状态。

## Docker 端到端测试

端到端测试默认跳过，避免普通单元测试意外构建镜像。安装并启动 Docker 后执行：

```bash
docker --version
ffjudge build

# Windows PowerShell
$env:FFJUDGE_RUN_DOCKER_TESTS = "1"
python -m unittest discover -s tests -v

# macOS / Linux
FFJUDGE_RUN_DOCKER_TESTS=1 python -m unittest discover -s tests -v
```

该套件覆盖 AC、WA、RE、Syntax Error、TLE、MLE、隐藏测试文件不可见、伪造 verdict 无效、无限输出受限、退出 137 不误判为 MLE，以及无残留 `ffjudge` 容器。

## 与 Failure-Frontier Teaching 的接口

每次尝试应至少记录：题目 ID、模型 ID、prompt 版本、attempt 编号、生成代码、verdict、phase、通过用例数、总用例数、运行时间和时间戳。评测器本身只负责可靠地产生 verdict；teacher 的失败反思、frontier report 和下一轮 prompt 由之后的实验编排层负责。

建议实验中将公开测试结果提供给模型调试，而隐藏测试只提供粗粒度 verdict。最终性能统计应只使用从未进入模型上下文的隐藏测试。

## 安全说明

不要直接在宿主机上运行模型生成的代码。Docker 隔离可以显著降低风险，但它不等同于强安全沙箱；第一版适合单机研究原型，不应作为面向不可信公众的在线评测服务。submission 仍与轻量 worker 处于同一容器和 Python 进程中，可以干扰 worker 协议或主动终止进程；这类行为会被宿主机视为受控错误，但本项目没有提供抵御容器逃逸、内核漏洞、侧信道或同机资源争用的强隔离。
