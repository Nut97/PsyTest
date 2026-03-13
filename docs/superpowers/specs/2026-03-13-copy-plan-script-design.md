# 复制方案调用脚本设计（测试环境）

## 1. 背景与目标

测试环境新增接口：

- `POST /api/qt-scale/screeningPlan/copy`
- 请求体：`{"sourcePlanId": 0, "planName": ""}`

当前前端尚未提交对应代码，需要一个可直接执行的调用脚本，用于：

1. 自动登录并获取 token（账号固定写死在脚本内）；
2. 按 `sourcePlanId` 复制方案；
3. 支持 `planName` 为空；
4. 只打印接口响应，不做业务成功断言。

## 2. 已确认约束

本次实现必须满足以下边界：

1. **仅新增一个脚本文件**，不修改其他任何文件；
2. **单文件自包含**，不依赖项目内现有 `core/apis/services` 模块；
3. 必须显式传 `--env`（`dev/test/pre`）；
4. `sourcePlanId` 单个输入；
5. `planName` 可为空；
6. 输出策略为“仅打印响应”。

## 3. 方案对比与结论

### 方案 A：独立脚本直连接口（最终采用）

- 描述：在 `scripts/copy_plan.py` 中完成参数解析、env 读取、登录、复制调用与响应输出。
- 优点：完全满足“单文件、零改动其他文件”的要求；上线路径短。
- 缺点：会复制一部分已有项目能力（如 env 解析、请求组装）。

### 方案 B：脚本复用现有 `core`/`service`

- 描述：脚本仅做入口，底层复用 `TokenManager` / `APIClient`。
- 优点：复用高，维护成本更低。
- 缺点：不满足“单文件完全自包含”的最终约束。

### 方案 C：扩展 `apis/services` 再由脚本调用

- 描述：先抽象 `copy_plan` API/service，再提供调用脚本。
- 优点：结构最工程化。
- 缺点：改动面超出当前需求，不符合“只增一个脚本文件”。

**结论：采用方案 A。**

## 4. 最终设计

### 4.1 文件与入口

- 新增：`scripts/copy_plan.py`
- 运行示例：

```bash
python scripts/copy_plan.py --env test --source-plan-id 123456789
python scripts/copy_plan.py --env test --source-plan-id 123456789 --plan-name ""
python scripts/copy_plan.py --env pre --source-plan-id 123456789 --plan-name "复制方案A"
```

### 4.2 CLI 参数设计

- `--env`：必填，枚举 `dev/test/pre`；
- `--source-plan-id`：必填，单个方案 ID；
- `--plan-name`：可选，默认空字符串 `""`。

参数错误处理约束：

1. 缺少必填参数、`--env` 非法值、`--source-plan-id` 多值/重复传参都视为参数错误；
2. 参数错误统一退出码为 `1`（不使用 argparse 默认退出码 `2`）。

### 4.3 脚本内模块划分（函数级）

建议函数职责如下（均在同一文件内）：

1. `parse_args()`：解析并校验命令行参数；
2. `read_env_file(env)`：读取 `envs/<env>.env`，提取关键配置；
3. `build_url(base_url, path)`：拼接完整 URL；
4. `build_base_headers(config)`：组装请求头（区分必需头与可选兼容头）；
5. `login_and_get_token(config)`：执行登录并提取 `access_token`；
6. `copy_plan(config, token, source_plan_id, plan_name)`：调用复制接口；
7. `print_response(tag, response)`：统一打印状态码与响应体；
8. `main()`：串联流程并控制退出码。

### 4.4 配置读取规则

从 `envs/<env>.env` 读取（**要求文件存在**）：

- `BASE_URL`
- `TIMEOUT_SECONDS`
- `BASIC_AUTH`
- `TENANT_ID`
- `BLADE_REQUEST_USERCODE`
- `BLADE_REQUESTED_WITH`
- `AUTH_PATH`

配置策略：

1. **关键配置必填**：`BASE_URL`、`AUTH_PATH`、`BASIC_AUTH`，任一缺失即退出 `1`；
2. **可选配置**：
   - `TIMEOUT_SECONDS` 缺失时默认 `30`；
   - `TENANT_ID`、`BLADE_REQUEST_USERCODE`、`BLADE_REQUESTED_WITH` 缺失时不强制报错（按空值处理）；
3. 若 `envs/<env>.env` 文件不存在，视为配置错误并退出 `1`。

### 4.5 登录与 token 获取

脚本内定义占位账号常量（后续人工替换真实值）：

- `LOGIN_USERNAME = "TODO_REPLACE_USERNAME"`
- `LOGIN_PASSWORD = "TODO_REPLACE_PASSWORD"`

登录请求：

- 方法：`POST`
- URL：`<BASE_URL><AUTH_PATH>`
- 必需 Header：`Authorization`（Basic）、`Content-Type: application/x-www-form-urlencoded`
- 可选兼容 Header：`Tenant-Id`、`blade-request-usercode`、`blade-requested-with`
- 表单字段：`username/password/grant_type/scope/user_code`

token 提取路径：`data.access_token`。

### 4.6 复制方案请求

- 方法：`POST`
- URL：`<BASE_URL>/api/qt-scale/screeningPlan/copy`
- 必需 Header：`Blade-Auth: bearer <token>`、`Content-Type: application/json`
- 可选兼容 Header：`Tenant-Id`、`blade-request-usercode`、`blade-requested-with`
- Body：

```json
{
  "sourcePlanId": 123,
  "planName": ""
}
```

说明：`planName` 即使为空，也会显式传入字段。

## 5. 数据流

```text
解析参数
  -> 读取 env 配置
  -> 使用固定账号登录获取 token
  -> 调用 copy 接口
  -> 打印登录响应 + 复制响应
```

## 6. 异常处理与退出码

### 6.1 异常处理

捕获并输出以下异常场景：

1. `envs/<env>.env` 不存在；
2. 关键配置缺失（`BASE_URL/AUTH_PATH/BASIC_AUTH`）；
3. 网络异常/超时；
4. 登录响应无法解析 JSON；
5. 登录未获取到 token（`access_token` 为空）。

### 6.2 退出码

- `0`：流程执行并拿到接口响应（不判定业务成功）；
- `1`：脚本执行异常（参数/配置/网络/登录阶段失败等）。

## 7. 输出与日志策略

按“仅打印响应”要求，输出：

1. 登录响应（HTTP 状态码 + body）；
2. 复制响应（HTTP 状态码 + body）。

说明：此处“打印响应”按原样输出响应内容，不增加业务断言。

## 8. 验收标准

满足以下条件即视为设计完成：

1. 项目中仅新增 `scripts/copy_plan.py`；
2. 可执行命令：

```bash
python scripts/copy_plan.py --env test --source-plan-id 10001
python scripts/copy_plan.py --env test --source-plan-id 10001 --plan-name ""
```

3. 脚本会自动登录获取 token；
4. 脚本会调用 `/api/qt-scale/screeningPlan/copy`；
5. 控制台能看到登录与复制接口原始响应；
6. 不依赖修改其他脚本或模块。
7. 未传 `--env` 时，脚本参数校验失败并退出码为 `1`；
8. `--env` 传入非 `dev/test/pre` 时，脚本参数校验失败并退出码为 `1`；
9. `--source-plan-id` 仅接受单个值；多值输入或重复传参时，脚本参数校验失败并退出码为 `1`。
10. 复制请求 JSON 始终包含 `sourcePlanId` 与 `planName` 两个字段；未传 `--plan-name` 时 `planName` 为 `""`。
11. 参数错误场景（缺少必填、非法 `--env`、多值/重复 `--source-plan-id`）统一返回退出码 `1`。
12. 当 `BASE_URL` 缺失时，脚本配置校验失败并退出码为 `1`；
13. 当 `AUTH_PATH` 缺失时，脚本配置校验失败并退出码为 `1`；
14. 当 `BASIC_AUTH` 缺失时，脚本配置校验失败并退出码为 `1`。

## 9. 非目标（本次不做）

1. 不新增 pytest 用例；
2. 不扩展批量复制；
3. 不改造现有 `core/apis/services`；
4. 不引入业务断言与重试策略优化。
