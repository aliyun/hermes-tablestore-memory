# Hermes TableStore Memory Provider

TableStore-based external memory provider for Hermes Agent.

This plugin uses the official `tablestore` Python SDK and Hermes' memory
provider interface to add:

- semantic long-term memory backed by TableStore memory APIs
- automatic turn sync after each completed conversation turn
- prefetch of relevant memories before the next turn
- explicit memory tools for inspect/search/store/delete operations

The built-in `MEMORY.md` and `USER.md` stores remain active. This plugin adds
one external memory backend alongside them.

## Features

- `tablestore_profile`
  Lists memories in the current scope.
- `tablestore_search`
  Runs semantic search over stored memories.
- `tablestore_remember`
  Persists a fact or short note to long-term memory.
- `tablestore_forget`
  Deletes a memory by id.
- Automatic `sync_turn()`
  Sends completed user/assistant turns to TableStore memory ingestion.
- Automatic `queue_prefetch()`
  Retrieves likely relevant memories for the next turn.
- Mirrors Hermes built-in memory writes into TableStore.

## Requirements

- Hermes Agent `v0.10.0` or newer (`2026-04-16` or later)
- Python environment used by Hermes can install:
  - `tablestore==6.4.5`
  - `alibabacloud-tablestore20201209`
  - `alibabacloud-credentials`
- A TableStore access key pair with permission to create or access the target instance
- Permission to create the memory store if it does not already exist

`v0.9.0` may install the repository under `~/.hermes/plugins/` but still fail
to detect it as an external memory provider. Upgrade Hermes first if
`hermes memory status` shows `Plugin: NOT installed`.

## Install

### Recommended: install from GitHub

```bash
hermes plugins install yourname/hermes-tablestore-memory
```

Or:

```bash
hermes plugins install https://github.com/yourname/hermes-tablestore-memory.git
```

Hermes installs the plugin into:

```text
~/.hermes/plugins/tablestore-mem/
```

Important: `hermes plugins install ...` installs the plugin files, but does
not reliably install Python runtime dependencies for memory providers. After
installation, either:

- run `hermes memory setup` and select `tablestore-mem` so Hermes can install
  `pip_dependencies` from `plugin.yaml`, or
- install the SDK manually into the exact Python environment used by `hermes`

Manual install example:

```bash
uv pip install --python "$(head -n 1 "$(which hermes)" | sed 's/^#!//')" \
  tablestore==6.4.5 \
  alibabacloud-tablestore20201209 \
  alibabacloud-credentials
```

### Manual install

Copy this repository into:

```text
~/.hermes/plugins/tablestore-mem/
```

Then install the SDK dependency into the Python environment used by Hermes:

```bash
uv pip install --python "$(which python)" \
  tablestore==6.4.5 \
  alibabacloud-tablestore20201209 \
  alibabacloud-credentials
```

If Hermes runs from a venv, use that interpreter explicitly instead.

## Activate

Interactive setup:

```bash
hermes memory setup
```

Select `tablestore-mem` from the provider list.

This step also installs any missing Python dependencies declared by the plugin,
including `tablestore==6.4.5`, `alibabacloud-tablestore20201209`, and
`alibabacloud-credentials`.

Or activate manually:

```bash
hermes config set memory.provider tablestore-mem
```

## Configuration

Secrets should go into:

```text
~/.hermes/.env
```

All non-secret provider settings should go into:

```text
$HERMES_HOME/tablestore_memory.json
```

### Environment variables

```bash
TABLESTORE_MEMORY_AK=your_access_key_id
TABLESTORE_MEMORY_SK=your_access_key_secret
```

Only these two secret fields belong in `.env`.

### Example `tablestore_memory.json`

```json
{
  "memory_store_name": "hermes_mem",
  "description": "",
  "app_id": "hermes",
  "tenant_id": "",
  "enable_rerank": true,
  "auto_create_store": true,
  "timeout": 30.0
}
```

On first initialization, if `instance_name` is missing, the plugin will:

- create a TableStore VCU instance through the Alibaba Cloud control-plane API
- update the new instance network ACL to allow `INTERNET`, `VPC`, and `CLASSIC`
- derive the data-plane endpoint as
  `https://{instance_name}.cn-beijing.ots.aliyuncs.com`
- persist both `instance_name` and `endpoint` back into
  `tablestore_memory.json`

After that, Hermes reuses the same persisted instance for all later runs.

If the user does not specify a memory store name, the plugin defaults to
`hermes_mem` and automatically creates it when missing.

Current built-in defaults:

- `endpoint`: auto-derived after first instance bootstrap if not already saved
- `instance_name`: auto-created after first instance bootstrap if not already saved
- `memory_store_name`: `hermes_mem`
- `app_id`: `hermes`
- `tenant_id`: empty string, then resolved from session or `__default__`
- `description`: empty string
- `enable_rerank`: `true`
- `auto_create_store`: `true`
- `timeout`: `30`

## How scope works

The provider stores and retrieves memories under a TableStore memory scope:

```text
appId / tenantId / agentId / runId
```

Current field resolution:

- `appId`
  Source: `app_id` in `tablestore_memory.json`.
  Default: `hermes`.
- `tenantId`
  Source: Hermes session `user_id` first.
  Fallback: `tenant_id` in `tablestore_memory.json`.
  Default: `__default__`.
- `agentId`
  Source: Hermes session identity, currently `agent_identity`.
  Default: `hermes`.
- `runId`
  Source priority:
  1. `gateway_session_key`
  2. `session_title`
  3. current `session_id`
  Default: `__default__` only if all of the above are empty.

This means only `appId` and `tenantId` are user-facing configuration inputs.
`agentId` and `runId` are intentionally session-derived so users do not need
to manage them manually.

Configuration source summary:

- `.env`: only `TABLESTORE_MEMORY_AK` and `TABLESTORE_MEMORY_SK`
- `tablestore_memory.json`: endpoint, instance, store, scope defaults, rerank,
  auto-create, timeout, and description
- session context: `tenantId` override via `user_id`, plus `agentId` and `runId`

Write scope and search scope are intentionally different:

- writes use the current session scope exactly
- searches use the current `tenantId` with `agentId=*` and `runId=*`

This lets Hermes search across all agents and sessions for the same tenant
while still writing memories with precise session attribution.

## Verify the installation

Check that Hermes sees the provider:

```bash
hermes memory status
```

You should see:

```text
Provider:  tablestore-mem
Plugin:    installed
Status:    available
```

Then start a Hermes session and use the memory tools, or run a quick manual
flow from a prompt:

1. Ask Hermes to remember a fact.
2. Ask Hermes to search for that fact.
3. Optionally delete the stored memory by id.

If the plugin is installed but the required SDKs are not yet available in the
Python environment Hermes is using, install the declared dependencies first:

```bash
uv pip install --python "$(head -n 1 "$(which hermes)" | sed 's/^#!//')" \
  tablestore==6.4.5 \
  alibabacloud-tablestore20201209 \
  alibabacloud-credentials
```

## CLI commands

When `memory.provider` is set to `tablestore-mem`, Hermes exposes:

```bash
hermes tablestore-mem add "User prefers concise answers"
hermes tablestore-mem add "User likes Rust" --metadata source=manual --metadata topic=preferences
hermes tablestore-mem add "Write this synchronously" --sync
hermes tablestore-mem search "concise answers"
hermes tablestore-mem search "Rust" --top-k 10
hermes tablestore-mem doctor
```

Notes:

- `hermes tablestore-mem add` writes one memory payload through the provider.
- `hermes tablestore-mem add` is asynchronous by default; pass `--sync` to wait.
- `hermes tablestore-mem search` returns JSON search results.
- `hermes tablestore-mem doctor` runs read-only diagnostics.
- `--metadata KEY=VALUE` can be repeated.
- These CLI commands are only registered when `tablestore-mem` is the active
  external memory provider.

The `doctor` command performs read-only diagnostics by:

- initializing the provider
- calling `DescribeMemoryStore` through `get_memory_store`
- calling `ListMemories`
- returning structured JSON suitable for debugging support requests

## Operational notes

- The plugin uses `tablestore.OTSClient` memory methods directly.
- The plugin uses Alibaba Cloud control-plane OpenAPI once for first-run
  instance bootstrap when `instance_name` is missing.
- During first-run bootstrap, the plugin also enables public access on the new
  instance by setting `network_type_acl` to `INTERNET`, `VPC`, and `CLASSIC`.
- Request signing and authentication are handled by the OTS SDK.
- `is_available()` only checks local config presence and does not do network
  calls. It now only requires `AK/SK`; missing `instance_name` is handled by
  bootstrap during initialization.
- `sync_turn()` runs asynchronously in a daemon thread to avoid blocking the
  agent loop.
- explicit `tablestore_remember` writes are asynchronous by default unless
  `sync=true` is provided.
- search and prefetch use rerank by default unless disabled in config or at
  call time.
- `tablestore_remember` may create multiple memory units from a single input
  if the backend extracts structured memories.

## Common issues

### Provider shows "not available"

Usually one of these values is missing:

- `TABLESTORE_MEMORY_AK`
- `TABLESTORE_MEMORY_SK`
- or the required Python SDK dependencies are not installed yet

Run:

```bash
hermes memory status
```

### Authentication fails

Check:

- the endpoint is an OTS endpoint, not a separate application gateway
- the persisted instance endpoint matches the auto-derived format
  `https://{instance_name}.cn-beijing.ots.aliyuncs.com`
- the AK/SK pair has permission for the target instance
- the SDK versions are installed:
  - `tablestore==6.4.5`
  - `alibabacloud-tablestore20201209`
  - `alibabacloud-credentials`

### Search does not return the original raw text

This is expected in some deployments. `AddMemories` can extract and normalize
the input into multiple memory units, so search results may contain structured
facts rather than the exact original sentence.

### First write is slow

The first write may take longer than a normal request when Hermes has to do one
or both of the following before writing memory data:

- bootstrap a new TableStore instance and enable `INTERNET`/`VPC`/`CLASSIC`
  network access on that instance
- create the `hermes_mem` memory store when it does not exist yet

The default timeout is `30` seconds.

## Repository layout

This repository is intentionally structured so Hermes can install it directly:

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

The repository root is the plugin root.

## License

This project is released under the MIT License. See [LICENSE](./LICENSE).
