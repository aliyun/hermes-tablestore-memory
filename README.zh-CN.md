# Hermes TableStore 记忆插件

基于 TableStore 的 Hermes Agent 外接记忆提供器。

这个插件使用官方 `tablestore` Python SDK，并接入 Hermes 的 memory
provider 接口，提供：

- 基于 TableStore Memory API 的长期语义记忆
- 每轮对话完成后的自动记忆写入
- 下一轮对话前的相关记忆预取
- 显式的记忆查询、写入、删除工具

Hermes 内建的 `MEMORY.md` 和 `USER.md` 仍然保留并继续工作；这个插件是在
内建记忆之上增加一个外部记忆后端。

## 功能

- `tablestore_profile`
  查看当前 scope 下已有的记忆。
- `tablestore_search`
  对记忆做语义检索。
- `tablestore_remember`
  写入一条长期记忆。
- `tablestore_forget`
  按 id 删除一条记忆。
- 自动 `sync_turn()`
  在一轮对话完成后，把用户消息和助手回复写入 TableStore。
- 自动 `queue_prefetch()`
  在下一轮前预取相关记忆。
- Hermes 内建 `memory` 工具的写入会自动镜像到 TableStore。

## 依赖条件

- Hermes Agent 版本至少为 `v0.10.0`（`2026-04-16`）或更新版本
- Hermes 所用的 Python 环境能够安装：
  - `tablestore==6.4.5`
  - `alibabacloud-tablestore20201209`
  - `alibabacloud-credentials`
- 有权限创建或访问目标实例的 AK/SK
- 当 memory store 不存在时，具备创建它的权限

`v0.9.0` 可能已经把仓库装进 `~/.hermes/plugins/`，但仍然无法把它识别为
外部 memory provider。如果 `hermes memory status` 仍显示
`Plugin: NOT installed`，请先升级 Hermes。

## 安装

### 推荐方式：从 GitHub 安装

```bash
hermes plugins install yourname/hermes-tablestore-memory
```

或者：

```bash
hermes plugins install https://github.com/yourname/hermes-tablestore-memory.git
```

安装后，Hermes 会把插件放到：

```text
~/.hermes/plugins/tablestore-mem/
```

注意：`hermes plugins install ...` 主要负责安装插件文件，本身不会稳定地把
memory provider 的 Python 运行时依赖也装好。安装后建议二选一：

- 运行 `hermes memory setup` 并选择 `tablestore-mem`，让 Hermes 根据
  `plugin.yaml` 自动安装 `pip_dependencies`
- 或者手动把 SDK 安装到 `hermes` 实际使用的 Python 环境中

手动安装示例：

```bash
uv pip install --python "$(head -n 1 "$(which hermes)" | sed 's/^#!//')" \
  tablestore==6.4.5 \
  alibabacloud-tablestore20201209 \
  alibabacloud-credentials
```

### 手动安装

把这个仓库整体复制到：

```text
~/.hermes/plugins/tablestore-mem/
```

然后在 Hermes 使用的 Python 环境里安装依赖：

```bash
uv pip install --python "$(which python)" \
  tablestore==6.4.5 \
  alibabacloud-tablestore20201209 \
  alibabacloud-credentials
```

如果 Hermes 运行在单独 venv 里，请把 `python` 换成对应解释器。

## 启用

交互式启用：

```bash
hermes memory setup
```

然后在列表里选择 `tablestore-mem`。

这一步也会安装插件声明的缺失 Python 依赖，包括
`tablestore==6.4.5`、`alibabacloud-tablestore20201209`、
`alibabacloud-credentials`。

或者手动启用：

```bash
hermes config set memory.provider tablestore-mem
```

## 配置

密钥类配置建议放到：

```text
~/.hermes/.env
```

所有非敏感配置都应放到：

```text
$HERMES_HOME/tablestore_memory.json
```

### 环境变量

```bash
TABLESTORE_MEMORY_AK=your_access_key_id
TABLESTORE_MEMORY_SK=your_access_key_secret
```

`.env` 中只保留这两个密钥字段。

### `tablestore_memory.json` 示例

```json
{
  "memory_store_name": "hermes_mem",
  "description": "",
  "app_id": "hermes",
  "tenant_id": "",
  "enable_rerank": true,
  "auto_create_store": true,
  "timeout": 30.0,
  "host_label": ""
}
```

首次初始化时，如果 `instance_name` 缺失，插件会：

- 通过阿里云控制面 API 自动创建一个 TableStore VCU 实例
- 把新实例的 `network_type_acl` 设置为 `INTERNET`、`VPC`、`CLASSIC`，
  并把 `NetworkSourceACL` 设置为 `TRUST_PROXY`
- 根据规则拼接数据面 endpoint：
  `https://{instance_name}.cn-beijing.ots.aliyuncs.com`
- 把 `instance_name` 和 `endpoint` 自动写回 `tablestore_memory.json`

之后 Hermes 会一直复用这份已经持久化的实例配置。

自动建实例的真实行为和限制：

- 控制面 bootstrap 和数据面访问都直接使用
  `TABLESTORE_MEMORY_AK` 和 `TABLESTORE_MEMORY_SK`。
- 新创建的实例需要一点时间才能发布可用的公网 endpoint。首次初始化时，
  Hermes 现在会先等待 endpoint DNS 可解析，再对数据面瞬时错误做有限重试。
- 因此，全新 Hermes home 第一次执行 `hermes tablestore-mem doctor`
  可能会明显比平时更久，这是等待新实例变为可访问状态的正常表现。

如果用户没有指定记忆库名，插件会默认使用 `hermes_mem`，并在缺失时自动创建。

当前内置默认值如下：

- `endpoint`: 如果未保存，则在首次实例自举后自动生成并持久化
- `instance_name`: 如果未保存，则在首次实例自举后自动创建并持久化
- `memory_store_name`: `hermes_mem`
- `app_id`: `hermes`
- `tenant_id`: 空字符串，之后会由配置优先解析、会话兜底，最终回退到 `__default__`
- `description`: 空字符串
- `enable_rerank`: `true`
- `auto_create_store`: `true`
- `timeout`: `30`
- `host_label`: 空字符串，即不改变 scope 与 metadata

## Scope 设计

插件使用的 TableStore scope 为：

```text
appId / tenantId / agentId / runId
```

当前四个字段的获取方式如下：

- `appId`
  来源：`tablestore_memory.json` 中的 `app_id`
  默认值：`hermes`
- `tenantId`
  来源：优先取 `tablestore_memory.json` 中的 `tenant_id`
  回退：Hermes 会话中的 `user_id`
  默认值：`__default__`
- `agentId`
  来源：Hermes 当前会话身份，当前实现里主要是 `agent_identity`
  配置 `host_label` 后会追加 `@<host_label>` 后缀
  默认值：`hermes`
- `runId`
  来源优先级：
  1. `gateway_session_key`
  2. `session_title`
  3. 当前 `session_id`
  默认值：仅在以上都为空时回退到 `__default__`

也就是说，需要用户配置的是 `appId`、`tenantId` 以及可选的 `host_label`；
`agentId` 与 `runId` 的其余部分由 Hermes 会话上下文提供，不建议手工管理。

配置来源总结：

- `.env`：只放 `TABLESTORE_MEMORY_AK` 和 `TABLESTORE_MEMORY_SK`
- `tablestore_memory.json`：放 endpoint、instance、memory store、scope 默认值、
  rerank、自动建库、timeout、description
- 会话上下文：作为 `tenantId` 兜底来源的 `user_id`，以及 `agentId`、`runId`

另外，写入和检索使用不同的 scope 策略：

- 写入时：使用当前会话的精确 scope
- 检索时：在当前 `tenantId` 下，将 `agentId=*`、`runId=*`

这样可以实现：

- 记忆写入时保留精确归属
- 检索时按租户维度跨 agent、跨会话召回

### 区分不同机器

多机共享要求 `appId` 与 `tenantId` 完全一致，而 `runId` 由会话派生，因此默认情况下
记忆里并没有任何字段记录它是哪台机器写入的——多台机器只要跑同一个 Hermes profile，
解析出的 `agentId` 就完全相同。

在每台机器上配置 `host_label` 即可显式标记来源：

```json
{
  "host_label": "auto"
}
```

- `auto` 解析为操作系统主机名；填其他非空值时按原样使用
- `A-Za-z0-9._-` 之外的字符会被替换为 `-`，结果截断到 64 字符；若清洗后为空，
  则视为未启用，而不会写入非法的 scope 片段
- 生效后有两处可见：`scope.agentId` 变为 `default@my-laptop`，
  `metadata.host` 变为 `my-laptop`

由于检索时 `agentId` 使用通配符，各机器之间仍能互相读到记忆，启用之前写入的历史
记忆也照常可被召回。如需只看某一台机器，按 metadata 过滤：

```json
{"metadata": {"host": "my-laptop"}}
```

## 验证安装

先确认 Hermes 已识别插件：

```bash
hermes memory status
```

你应该能看到：

```text
Provider:  tablestore-mem
Plugin:    installed
Status:    available
```

之后可以在 Hermes 对话里直接使用，也可以用 CLI 命令验证。

如果插件已经安装，但 Hermes 所使用的 Python 环境里还没有这些 SDK
依赖，需要先安装：

```bash
uv pip install --python "$(head -n 1 "$(which hermes)" | sed 's/^#!//')" \
  tablestore==6.4.5 \
  alibabacloud-tablestore20201209 \
  alibabacloud-credentials
```

## CLI 命令

当 `memory.provider` 设置为 `tablestore-mem` 后，可以直接使用：

```bash
hermes tablestore-mem add "用户偏好简洁回答"
hermes tablestore-mem add "用户喜欢 Rust" --metadata source=manual --metadata topic=preferences
hermes tablestore-mem add "同步写入这条记忆" --sync
hermes tablestore-mem search "简洁回答"
hermes tablestore-mem search "Rust" --top-k 10
hermes tablestore-mem doctor
```

说明：

- `hermes tablestore-mem add` 通过 provider 写入一条记忆
- `hermes tablestore-mem add` 默认异步写入；传入 `--sync` 才会等待写入完成
- `hermes tablestore-mem search` 返回 JSON 检索结果
- 搜索是语义检索和排序结果。写入刚完成时，尤其是异步写入场景，某个精确字面值
  不一定会立刻出现在结果顶部；应将其视为“最终一致”而不是“严格同步可见”。
- `hermes tablestore-mem doctor` 执行只读诊断
- `--metadata KEY=VALUE` 可以重复使用
- 这些 CLI 命令只有在 `tablestore-mem` 是当前激活的 memory provider 时才会注册

`doctor` 命令会执行只读诊断，包括：

- 初始化 provider
- 通过 `get_memory_store` 调用 `DescribeMemoryStore`
- 调用 `ListMemories`
- 返回结构化 JSON，方便用户直接贴出来排障

当 `instance_name` 缺失时，一次成功的 `doctor` 也意味着：自动建实例已经
完成、生成的 endpoint 已可访问、且新实例已经能够承载数据面的记忆请求。

## 运行说明

- 插件直接调用 `tablestore.OTSClient` 的 memory 方法
- 当 `instance_name` 缺失时，插件会先通过阿里云控制面 OpenAPI 自动创建实例
- 首次自动创建实例后，插件还会立即开放公网/VPC/经典网络访问 ACL，并设置
  `NetworkSourceACL=TRUST_PROXY`
- OTS SDK 负责请求签名和鉴权
- `is_available()` 现在只要求本地存在 `AK/SK`；缺失实例时会在初始化阶段自动自举
- `sync_turn()` 使用后台线程，避免阻塞主代理循环
- 显式 `tablestore_remember` 写入默认也是异步，除非传入 `sync=true`
- 搜索和预取默认启用 rerank，可通过配置或调用参数关闭
- `tablestore_remember` 的一次写入，后端可能会抽取成多条结构化记忆单元

## 常见问题

### 插件显示 “not available”

通常是以下配置缺失：

- `TABLESTORE_MEMORY_AK`
- `TABLESTORE_MEMORY_SK`
- 或 Hermes 当前 Python 环境里还没安装依赖 SDK

运行：

```bash
hermes memory status
```

### 鉴权失败

请检查：

- endpoint 是否真的是 OTS endpoint，而不是别的业务网关
- endpoint 是否符合自动生成规则
  `https://{instance_name}.cn-beijing.ots.aliyuncs.com`
- AK/SK 是否对该实例有权限
- SDK 是否已经安装：
  - `tablestore==6.4.5`
  - `alibabacloud-tablestore20201209`
  - `alibabacloud-credentials`

### 搜索结果不是原始输入文本

这是正常现象。`AddMemories` 可能会把原始输入抽取、归一化成多条结构化记忆，
所以搜索返回的可能是抽取后的事实，而不是完全逐字一致的原文。

### 首次写入较慢

第一次写入可能会比普通请求更慢，因为插件可能需要先完成以下一个或两个步骤：

- 自动创建新的 TableStore 实例，并为该实例开启
  `INTERNET`/`VPC`/`CLASSIC` 网络访问 ACL 以及 `TRUST_PROXY` source ACL
- 当默认库 `hermes_mem` 尚不存在时，自动创建记忆库

另外，brand-new 实例创建后的公网 endpoint 可能还有一个 DNS 传播窗口。
Hermes 现在会在首次初始化时主动等待这段窗口，因此第一次成功命令可能会明显
比平时更慢，这是正常现象。

当前默认超时是 `30` 秒。

## 仓库结构

这个仓库已经按 Hermes 可直接安装的格式组织好了：

```text
.
├── __init__.py
├── cli.py
├── CHANGELOG.md
├── plugin.yaml
├── README.md
├── README.zh-CN.md
├── after-install.md
└── LICENSE
```

仓库根目录就是插件根目录。

## 许可证

本项目采用 MIT License，详见 [LICENSE](./LICENSE)。
