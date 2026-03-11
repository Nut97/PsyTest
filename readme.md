~~~markdown
# Psytest 自动化测试框架

Psytest 是一个面向**心理筛查问卷系统**的模块化自动化测试框架，核心用于验证以下业务链路：

```text
登录 -> 获取任务 -> 获取问卷(getPaper) -> 自动生成答案 -> 提交答案(answerSubmit)
~~~

当前框架聚焦两类测试场景：

- 冒烟测试（Smoke）
- 批量端到端测试（E2E Batch）

同时保留测试数据自动生成能力，便于后续持续扩展和批量验证。

------

## 1. 设计目标

本框架的设计目标如下：

- 模块化：接口、业务、数据、测试职责分离
- 可维护：核心链路集中管理，减少重复代码
- 可扩展：后续可增加报告、平台化、CI/CD、数据库校验
- 可复现：通过 `seed` 控制随机行为，便于问题复盘
- 可落地：适合当前业务直接使用，而不是演示型脚手架

------

## 2. 项目结构

### 2.1 目录树

```text
Psytest/
├─ apis/
│  ├─ __init__.py
│  ├─ auth_api.py
│  └─ screening_api.py
├─ core/
│  ├─ __init__.py
│  ├─ assertions.py
│  ├─ auth.py
│  ├─ http.py
│  ├─ logger.py
│  ├─ settings.py
│  └─ utils/
│     ├─ __init__.py
│     ├─ answers.py
│     ├─ datasets.py
│     └─ passwords.py
├─ data/
│  ├─ account.example.json
│  ├─ account.json
│  ├─ accounts.txt
│  └─ gen_students.py
├─ envs/
│  ├─ dev.env
│  ├─ pre.env
│  └─ test.env
├─ scripts/
│  ├─ gen_accounts.py
│  ├─ launch.cmd
│  ├─ launch.sh
│  ├─ run_e2e.cmd
│  ├─ run_e2e.sh
│  ├─ run_smoke.cmd
│  ├─ run_smoke.sh
│  └─ venv_setup.cmd
├─ services/
│  ├─ __init__.py
│  └─ screening_service.py
├─ tests/
│  ├─ __init__.py
│  ├─ test_e2e_batch.py
│  └─ test_smoke_screening.py
├─ conftest.py
├─ pyproject.toml
├─ requirements.txt
└─ start.py
```

### 2.2 分层职责

#### `apis/`

接口层，只负责定义和调用具体接口，不承担业务编排逻辑。

- `auth_api.py`：登录接口
- `screening_api.py`：筛查任务、获取问卷、提交答案等接口

#### `core/`

框架公共能力层。

- `http.py`：统一 HTTP 请求封装
- `auth.py`：登录和 Token 管理
- `settings.py`：环境配置加载
- `logger.py`：日志输出
- `assertions.py`：通用断言
- `utils/answers.py`：自动生成答案
- `utils/datasets.py`：测试数据读取
- `utils/passwords.py`：密码处理工具

#### `services/`

业务编排层，用于串联完整链路。

- 登录
- 获取任务
- 获取问卷
- 自动组装答案
- 提交答案
- 返回统一结果

#### `data/`

测试数据层。

- `gen_students.py`：随机生成学生测试数据
- `account.json`：测试运行使用的账号文件
- `accounts.txt`：原始账号文本数据

#### `tests/`

测试场景层，仅保留当前最核心的测试入口。

- `test_smoke_screening.py`：单账号冒烟测试
- `test_e2e_batch.py`：多账号批量测试

#### `scripts/`

辅助启动脚本层。

- 快速执行 smoke / e2e
- 快速生成账号
- 快速初始化虚拟环境

------

## 3. 核心业务流程

### 3.1 整体流程

```text
登录
  -> 获取任务列表
  -> 提取 taskId / taskUserId
  -> 调用 getPaper/{taskId}
  -> 解析问卷结构
  -> 自动生成答案
  -> 调用 answerSubmit
  -> 校验提交结果
```

### 3.2 接口关系说明

#### `getPaper`

用于获取当前任务对应的筛查问卷。

示例路径：

```text
/api/qt-scale/app/screening/getPaper/2031286854852067329
```

也就是：

```text
/api/qt-scale/app/screening/getPaper/{task_id}
```

#### `answerSubmit`

用于提交整份答卷。

提交体核心结构如下：

```json
{
  "taskUserId": "xxx",
  "basicInfoData": null,
  "gaugeAnswerDTOList": [
    {
      "gaugeId": "xxx",
      "completeAnswerDTOList": [
        {
          "subjectId": "xxx",
          "answer": "选项文本",
          "taskUserId": "xxx",
          "answerIntervalTime": 123,
          "identificationQuestion": "0"
        }
      ]
    }
  ]
}
```

------

## 4. 自动答案生成逻辑

### 4.1 数据来源

答案生成基于 `getPaper` 返回内容自动提取，主要读取以下结构：

```text
data
└─ gaugeDtos
   └─ gaugeSubjectVOList
      └─ gaugeSubjectOptionDtoList
```

### 4.2 生成规则

每道题执行以下逻辑：

1. 自动读取题目 ID
2. 自动读取当前题目的全部选项
3. 根据答案模式选择一个选项
4. 将选项文本写入 `answer`
5. 自动补充 `answerIntervalTime`
6. 自动补充 `taskUserId`
7. 最终按量表分组组装到 `gaugeAnswerDTOList`

### 4.3 兜底处理

由于题目选项数量可能不一致，实际问卷中可能出现：

- 2 个选项
- 3 个选项
- 4 个选项
- 5 个选项
- 7 个选项

因此框架不写死选项个数，而是动态读取选项列表，并做统一兜底，保证：

- 不漏题
- 不因选项数量变化而报错
- 每题至少能生成一个答案

------

## 5. 随机种子（seed）说明

### 5.1 什么是 seed

`seed` 是随机数种子，用于让随机行为可复现。

### 5.2 当前框架中 seed 的用途

`seed` 会影响以下行为：

- 自动答案选择
- 答题时间生成
- 测试数据生成（`gen_students.py`）

### 5.3 示例

```bash
python start.py --env test --suite smoke --seed 42
```

含义：

- 每次运行生成相同的随机答案
- 每次运行生成相同的随机时间
- 便于复现问题

### 5.4 为什么常用 42

`42` 只是常见默认值，没有业务特殊含义。
你也可以使用任意数字，例如：

```bash
--seed 1
--seed 100
--seed 9999
```

------

## 6. 运行环境要求

推荐环境：

- Python 3.10 及以上

支持平台：

- Windows
- Linux
- macOS

------

## 7. 安装与初始化

### 7.1 进入项目根目录

```bash
cd Psytest
```

### 7.2 创建虚拟环境

```bash
python -m venv .venv
```

### 7.3 激活虚拟环境

#### Windows

```bash
.venv\Scripts\activate
```

#### Linux / macOS

```bash
source .venv/bin/activate
```

### 7.4 安装依赖

```bash
pip install -r requirements.txt
```

### 7.5 验证 pytest 是否可用

```bash
python -m pytest --version
```

### 7.6 验证项目测试是否能被正确收集

```bash
python -m pytest -c pyproject.toml --collect-only -q
```

正常情况下应收集到：

```text
tests/test_e2e_batch.py::test_e2e_batch
tests/test_smoke_screening.py::test_smoke_screening
```

------

## 8. 环境配置

环境配置文件位于：

```text
envs/
├─ dev.env
├─ test.env
└─ pre.env
```

### 8.1 推荐优先使用 `test.env`

示例：

```env
BASE_URL=http://society-platform-test.scqtkj.com
AUTH_TOKEN=
TIMEOUT_SECONDS=15

BASIC_AUTH=Basic c2FiZXIzOnNhYmVyM19zZWNyZXQ=
TENANT_ID=000000

SCREENING_TASK_LIST_PATH=/api/qt-scale/app/screening/task/page
SCREENING_GET_PAPER_PATH=/api/qt-scale/app/screening/getPaper/{task_id}
SCREENING_SUBMIT_PATH=/api/qt-scale/app/screening/answerSubmit
SCREENING_TASK_STATUSES=1
ALLOW_EMPTY_SUBMIT=0
```

### 8.2 关键配置项说明

| 配置项                     | 说明                   |
| -------------------------- | ---------------------- |
| `BASE_URL`                 | 环境根地址             |
| `AUTH_PATH`                | 登录接口路径           |
| `SCREENING_TASK_LIST_PATH` | 任务列表接口           |
| `SCREENING_GET_PAPER_PATH` | 获取问卷接口           |
| `SCREENING_SUBMIT_PATH`    | 提交答案接口           |
| `SCREENING_TASK_STATUSES`  | 默认任务状态筛选       |
| `ALLOW_EMPTY_SUBMIT`       | 是否允许无任务时不失败 |

------

## 9. 测试数据管理

### 9.1 账号文件格式

运行测试默认读取：

```text
data/account.json
```

示例：

```json
[
  {
    "数据集名称": "数据1",
    "studentNum": "20230001",
    "password": "加密后的密码"
  }
]
```

### 9.2 原始账号文件

也可以维护：

```text
data/accounts.txt
```

格式为一行一个账号：

```text
20230001
20230002
20230003
```

然后通过脚本生成 `account.json`。

------

## 10. 测试数据生成逻辑

### 10.1 `gen_students.py` 的定位

`data/gen_students.py` 是当前测试数据生成主入口，用于随机生成指定数量的学生数据。

### 10.2 你的实际使用逻辑

当前推荐使用方式如下：

1. 运行 `gen_students.py`
2. 生成指定数量的随机测试数据
3. 将生成结果手动覆盖到 `account.json`
4. 或在批量测试时直接指定对应数据文件
5. 进入整套测试流程

这种方式是合理的，因为它把“测试数据生成”和“自动化执行”解耦了。

### 10.3 示例命令

```bash
python data/gen_students.py --count 10 --seed 42
```

### 10.4 说明

生成的数据通常会包含：

- 学生基础信息
- 身份证号
- 年龄
- 年级
- 班级
- 家长信息
- 可用于登录的账号信息

你可以根据实际输出结果：

- 手动复制覆盖到 `data/account.json`
- 或在批量测试时指定新的账号文件

------

## 11. 启动方式

### 11.1 统一入口启动

推荐使用 `start.py` 作为统一入口。

#### 冒烟测试

```bash
python start.py --env test --suite smoke --seed 42
```

#### 批量 E2E 测试

```bash
python start.py --env test --suite e2e --seed 42
```

### 11.2 直接使用 pytest 运行

#### 运行冒烟测试

```bash
python -m pytest -c pyproject.toml tests/test_smoke_screening.py --env test --seed 42 -s
```

#### 运行批量测试

```bash
python -m pytest -c pyproject.toml tests/test_e2e_batch.py --env test --seed 42 -s
```

------

## 12. 推荐验证顺序

建议严格按以下顺序验证，定位问题最快。

### 12.1 验证依赖安装

```bash
python -m pytest --version
```

### 12.2 验证测试收集

```bash
python -m pytest -c pyproject.toml --collect-only -q
```

### 12.3 验证账号数据是否已准备

检查：

```text
data/account.json
```

### 12.4 验证登录

```bash
python -c "from core.settings import load_settings; from core.auth import TokenManager; from core.utils.datasets import load_accounts; s=load_settings('test'); a=load_accounts('data/account.json')[0]; t=TokenManager(settings=s).get_token(a); print('TOKEN_OK' if t else 'TOKEN_FAIL')"
```

### 12.5 验证任务列表

```bash
python -c "from core.settings import load_settings; from core.utils.datasets import load_accounts; from services.screening_service import ScreeningService; s=load_settings('test'); a=load_accounts('data/account.json')[0]; svc=ScreeningService(settings=s, account=a); print('LOGIN=', bool(svc.ensure_login())); tasks=svc.list_task_refs(); print('TASK_COUNT=', len(tasks)); print('FIRST_TASK=', {'paper_task_id': tasks[0].paper_task_id, 'task_user_id': tasks[0].task_user_id} if tasks else 'NO_TASK')"
```

### 12.6 验证 getPaper 和答案生成

```bash
python -c "from core.settings import load_settings; from core.utils.datasets import load_accounts; from services.screening_service import ScreeningService; from core.utils.answers import summarize_paper, build_submit_payload; s=load_settings('test'); a=load_accounts('data/account.json')[0]; svc=ScreeningService(settings=s, account=a); svc.ensure_login(); task=svc.list_task_refs()[0]; paper=svc.fetch_paper(task.paper_task_id); summary=summarize_paper(paper); payload=build_submit_payload(paper, task.task_user_id, seed=42); print(summary); print('GAUGE_COUNT=', len(payload['gaugeAnswerDTOList']))"
```

### 12.7 运行 smoke

```bash
python -m pytest -c pyproject.toml tests/test_smoke_screening.py --env test --seed 42 -s
```

### 12.8 运行 e2e

```bash
python -m pytest -c pyproject.toml tests/test_e2e_batch.py --env test --seed 42 -s
```

------

## 13. 常见问题排查

### 13.1 `pyproject.toml` 找不到

原因通常是：

- 文件名写错
- 当前目录不是项目根目录

正确文件名必须是：

```text
pyproject.toml
```

### 13.2 pytest 收集失败

优先检查：

- 目录是否完整
- 是否在项目根目录执行
- 是否缺少依赖
- 是否某个 Python 文件粘贴时格式损坏

### 13.3 登录失败

优先检查：

- `data/account.json` 是否存在
- 账号密码是否正确
- `BASIC_AUTH` 是否正确
- `TENANT_ID` 是否正确
- `AUTH_PATH` 是否与真实环境一致

### 13.4 没有任务

优先检查：

- 当前账号是否真的有待执行任务
- `SCREENING_TASK_STATUSES` 是否正确
- 任务列表接口返回是否为空

### 13.5 提交接口失败

优先检查：

- `SCREENING_SUBMIT_PATH` 是否与真实环境一致
- `taskUserId` 是否正确
- `getPaper` 返回结构是否完整
- 提交 payload 是否符合当前版本要求

------

## 14. 当前框架的优势

### 14.1 适合当前业务直接落地

不是为了展示而拼凑的样例工程，而是围绕当前筛查业务设计。

### 14.2 结构清晰

- 接口层只负责接口
- 业务层只负责链路
- 测试层只负责场景
- 数据层独立管理

### 14.3 易于扩展

后续可以继续增加：

- Allure 报告
- Jenkins / GitLab CI
- 数据库结果校验
- 分环境批量执行
- 高分 / 低分 / 中位分答案模式
- 平台化管理界面

------

## 15. 后续建议

推荐你下一阶段继续补充：

1. 高分 / 低分 / 中位分答题模式
2. 更完整的业务断言
3. Allure 报告输出
4. CI/CD 持续执行
5. 数据生成与执行的标准化脚本

------

## 16. 推荐日常命令

### 16.1 安装依赖

```bash
pip install -r requirements.txt
```

### 16.2 生成测试数据

```bash
python data/gen_students.py --count 10 --seed 42
```

### 16.3 运行冒烟测试

```bash
python start.py --env test --suite smoke --seed 42
```

### 16.4 运行批量测试

```bash
python start.py --env test --suite e2e --seed 42
```

### 16.5 仅收集测试项

```bash
python -m pytest -c pyproject.toml --collect-only -q
```

------

## 17. 总结

Psytest 当前版本已经具备以下能力：

- 基于真实接口链路的自动化执行
- 自动解析问卷并生成答案
- 支持随机数据与批量测试
- 支持可复现随机行为
- 保持结构清晰，适合长期维护

当前这套结构不是“删到最少”的极简工程，而是一个更偏**商业化、工程化、可持续使用**的自动化测试框架。

如需继续升级，建议下一步优先完善：

- 答题模式策略
- 报告体系
- 平台化入口
- CI/CD 集成

```
如果你愿意，我下一条可以继续给你补一版**带 Mermaid 流程图的 README**，视觉上会更适合正式项目文档。
```