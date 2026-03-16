# E2E 批量测试指定账号文件用法设计

## 1. 背景与目标

当前用户常用命令为：

```bash
python -m pytest -c pyproject.toml tests/test_e2e_batch.py --env test --seed 41 -s
```

需求是基于该命令增加“指定账号文件”的能力，统一使用 `--account-file`。

在项目现状中，`conftest.py` 与 `start.py` 已支持参数 `--account-file`，因此本次目标不是新增参数，而是：

1. 给出可直接执行的命令写法；
2. 在 README 中补齐 `--account-file` 的使用示例；
3. 明确路径约定（以项目根目录相对路径为主，同时兼容绝对路径）。

## 2. 已确认约束

经确认，本次范围与边界如下：

1. 不新增 `--account` 参数；
2. 继续只使用 `--account-file`；
3. 交付内容包含：可执行命令 + README 用法补充；
4. 文档以“相对路径为主”进行说明，可顺带注明绝对路径可用；
5. 不改动登录、任务获取、问卷提交等业务逻辑。

## 3. 方案对比与结论

### 方案 A：零代码改动（最终采用）

- 描述：复用既有 `--account-file` 能力，仅补充命令示例和文档说明。
- 优点：风险最低、交付最快、与现有代码完全一致。
- 缺点：不提供 `--account` 简写别名。

### 方案 B：兼容增强（保留 `--account-file` + 新增 `--account`）

- 描述：新增别名参数，同时兼容旧参数。
- 优点：使用体验更短更直观。
- 缺点：需要定义双参数冲突规则，增加维护成本。

### 方案 C：统一入口导向（主推 `start.py`）

- 描述：主推统一入口 `start.py`，pytest 直跑作为补充。
- 优点：命令入口更统一。
- 缺点：改变当前用户习惯，且不能直接解决“pytest 命令怎么写”的问题。

**结论：采用方案 A（零代码改动）。**

## 4. 最终设计

### 4.1 架构设计（零代码）

本次设计采用“能力复用 + 文档显式化”的方式：

1. **能力层不变**：继续使用 `conftest.py` 中现有的 `--account-file` 参数；
2. **入口层不变**：保留 `python -m pytest ...` 与 `python start.py ...` 两条入口；
3. **文档层增强**：在 README 对运行命令和路径规则做补充说明。

### 4.2 组件与职责边界

1. **参数解析单元（`conftest.py` / `start.py`）**
   - 职责：接收并透传 `--account-file`。
   - 边界：不引入新参数，不改变默认值 `data/account.json`。

2. **数据加载单元（`core.utils.datasets.load_accounts`）**
   - 职责：按 `--account-file` 指向路径加载账号数据。
   - 边界：保持现有加载逻辑，不新增格式转换规则。

3. **文档说明单元（`readme.md`）**
   - 职责：提供“可复制即运行”的命令示例，并给出路径约定。
   - 边界：仅更新与本需求直接相关的命令说明，不做无关重构。

### 4.3 数据流

```text
命令行输入 --account-file
  -> pytest 参数解析
  -> conftest.py accounts fixture 读取参数
  -> load_accounts(path) 加载账号列表
  -> test_e2e_batch 使用该账号列表执行批量流程
```

### 4.4 命令规范与示例

1. **pytest 直跑（主示例）**

```bash
python -m pytest -c pyproject.toml tests/test_e2e_batch.py --env test --seed 41 --account-file data/account.json -s
```

2. **统一入口（补充示例）**

```bash
python start.py --env test --suite e2e --seed 41 --account-file data/account.json
```

3. **绝对路径示例（可选）**

```bash
python -m pytest -c pyproject.toml tests/test_e2e_batch.py --env test --seed 41 --account-file D:/PsyTest2.0/data/account.json -s
```

4. **路径规则**
   - 优先使用项目根目录相对路径（如 `data/account.json`）；
   - 绝对路径可用，适用于跨目录执行或 CI 场景。

### 4.5 README 计划变更点

在 README 的“运行批量测试”附近补充：

1. 增加 `--account-file` 示例命令（基于当前用户命令扩展）；
2. 增加一段简短说明：
   - 默认账号文件：`data/account.json`；
   - 可通过 `--account-file` 指定其他文件；
   - 推荐使用项目根目录相对路径。

## 5. 异常处理设计（文档层明确预期）

本次不修改异常处理代码，仅在文档中明确预期行为：

1. **账号文件不存在**：`load_accounts` 返回空列表，`test_e2e_batch` 按现有逻辑 `skip`；
2. **账号文件 JSON 格式错误**：`json.loads` 解析失败，测试报错失败；
3. **账号列表为空**：`test_e2e_batch` 按现有逻辑 `skip`；
4. **路径歧义问题**：通过文档强调“优先使用项目根目录相对路径”，并说明绝对路径可用。

## 6. 测试与验收策略

### 6.1 验证策略

1. 使用带 `--account-file` 的命令执行 e2e，确认参数可生效；
2. 不带 `--account-file` 时回归默认文件行为不变；
3. 对照 README 命令逐条验证可执行性（文档与实现一致）。

### 6.2 验收标准

满足以下条件即视为本需求完成：

1. 用户可通过 `--account-file` 在当前 e2e 命令中指定账号文件；
2. README 中存在可直接复制的 `--account-file` 示例；
3. README 明确“相对路径为主，绝对路径可用”；
4. 不引入 `--account` 新参数；
5. 既有默认行为与业务流程不受影响。

## 7. 非目标（本次不做）

1. 不新增 `--account` 参数或其他别名；
2. 不调整 `load_accounts` 数据结构与业务逻辑；
3. 不重构测试框架分层；
4. 不新增与本需求无关的参数校验策略。
