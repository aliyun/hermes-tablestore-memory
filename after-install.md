# TableStore plugin installed

Next steps:

Minimum supported Hermes version: `v0.10.0` (`2026-04-16`) or newer.

1. Run Hermes memory setup and select `tablestore-mem`:

```bash
hermes memory setup
```

This is the recommended activation path. It sets `memory.provider` and lets
Hermes install missing `pip_dependencies` declared by this plugin, including
`tablestore==6.4.5`, `alibabacloud-tablestore20201209`, and
`alibabacloud-credentials`.

2. If setup reports that dependency installation failed, install the SDK into
   the same interpreter used by `hermes`:

```bash
uv pip install --python "$(head -n 1 "$(which hermes)" | sed 's/^#!//')" \
  tablestore==6.4.5 \
  alibabacloud-tablestore20201209 \
  alibabacloud-credentials
```

3. Add credentials to `~/.hermes/.env`:

```bash
TABLESTORE_MEMORY_AK=your_access_key_id
TABLESTORE_MEMORY_SK=your_access_key_secret
```

4. Create `~/.hermes/tablestore_memory.json` for all non-secret config:

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

`tenant_id` is configuration-first. If it is set in
`tablestore_memory.json`, the plugin uses that value as the active
`tenantId`. Hermes session `user_id` is only used as a fallback when
`tenant_id` is empty. If both are empty, the provider falls back to
`__default__`.

If `instance_name` is missing, the plugin automatically creates a VCU instance
on first initialization, enables `INTERNET`/`VPC`/`CLASSIC` network access on
that new instance, sets `NetworkSourceACL=TRUST_PROXY`, derives the endpoint as
`https://{instance_name}.cn-beijing.ots.aliyuncs.com`, and persists both
fields for reuse.

For automatic instance bootstrap, `TABLESTORE_MEMORY_AK` and
`TABLESTORE_MEMORY_SK` are not always sufficient by themselves. The bootstrap
path uses the Alibaba Cloud control-plane SDK, so the Hermes process should
also have usable Alibaba Cloud account credentials in its environment. In
practice, setting `ALIBABA_CLOUD_ACCESS_KEY_ID` and
`ALIBABA_CLOUD_ACCESS_KEY_SECRET` to the same account credentials is the
safest setup.

A newly created instance may also need a short propagation window before the
public endpoint is reachable. If the first `doctor`, `status`, or CLI memory
command fails immediately after bootstrap with DNS or connection errors, wait a
few seconds and retry.

If `memory_store_name` is omitted, the plugin uses `hermes_mem` and creates it
automatically when missing.

5. Verify:

```bash
hermes memory status
```

Expected:

```text
Plugin:    installed ✓
Status:    available ✓
```

If the plugin is available, Hermes will use it for:

- memory prefetch before turns
- turn sync after completed turns
- explicit tools:
  - `tablestore_profile`
  - `tablestore_search`
  - `tablestore_remember`
  - `tablestore_forget`

Scope behavior:

- writes use the current session scope exactly
- searches use the current `tenantId` with `agentId=*` and `runId=*`

CLI commands are also available when `tablestore-mem` is the active provider:

```bash
hermes tablestore-mem add "Remember this fact"
hermes tablestore-mem search "this fact"
hermes tablestore-mem doctor
```

`doctor` performs read-only diagnostics for provider initialization,
`DescribeMemoryStore`, and `ListMemories`.
