# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

- Added an optional `host_label` config field that attributes memories to a
  specific machine:
  - accepts a literal label, or `auto` to resolve the OS hostname
  - when set, the write scope becomes
    `agentId = <agent_identity>@<host_label>`, and every memory written by this
    installation carries a `host` metadata key
  - when unset (the default) the resolved scope and metadata are unchanged, so
    existing installations keep their current behavior
  - retrieval keeps using `agentId=*` / `runId=*`, so memories written by
    different machines under the same tenant stay mutually visible
- `tablestore_search` results now include the `metadata` field, matching what
  `tablestore_profile` already returned for the same memory units

## 1.0.2 - 2026-04-29

- Fixed clean-environment automatic bootstrap:
  - control-plane instance creation now explicitly reuses
    `TABLESTORE_MEMORY_AK` and `TABLESTORE_MEMORY_SK`
  - first-run initialization now waits for the new public endpoint DNS to
    become resolvable before using the data-plane SDK
  - first-run initialization now retries transient data-plane endpoint errors
    while the new instance becomes reachable
- Verified first-run bootstrap in a fresh Hermes home:
  - a clean environment with only `TABLESTORE_MEMORY_AK` and
    `TABLESTORE_MEMORY_SK` now completes
    `hermes tablestore-mem doctor` successfully on first initialization
- Updated docs to match actual behavior:
  - removed the practical requirement for separate `ALIBABA_CLOUD_*`
    credentials in the default AK/SK bootstrap path
  - clarified that the first initialization may wait noticeably longer while
    the new endpoint becomes reachable
  - documented semantic search visibility and eventual consistency after writes

## 1.0.1 - 2026-04-29

- Changed `tenantId` precedence to config-first:
  - `tablestore_memory.json` `tenant_id` now overrides Hermes session `user_id`
  - session `user_id` is only used as a fallback when config `tenant_id` is empty
- Added `hermes tablestore-mem doctor` for read-only provider diagnostics.
- Improved first-run automatic instance bootstrap:
  - create a VCU instance when `instance_name` is missing
  - derive and persist the data-plane endpoint automatically
  - update network ACL to allow `INTERNET`, `VPC`, and `CLASSIC`
  - set `NetworkSourceACL` to `TRUST_PROXY`
  - retry control-plane follow-up steps during initial instance visibility delays
- Kept the default bootstrap region at `cn-beijing`.
- Clarified installation and runtime requirements:
  - minimum supported Hermes version is `v0.10.0` (`2026-04-16`)
  - `hermes memory setup` is the recommended activation path
- Clarified scope and defaults documentation:
  - after-install now documents config-first `tenant_id` resolution
  - README now documents exact scope resolution for `appId`, `tenantId`, `agentId`, and `runId`
  - write scope remains session-precise, while search uses tenant-wide `agentId=*` and `runId=*`

## 1.0.0 - 2026-04-19

- Initial public release of the Hermes TableStore memory provider.
- Added Hermes memory provider integration backed by the official OTS SDK.
- Added automatic memory store creation with default store name `hermes_mem`.
- Added CLI commands:
  - `hermes tablestore-mem add`
  - `hermes tablestore-mem search`
- Added English and Simplified Chinese documentation.
- Added MIT license.
- Added tenant-wide search scope design:
  - writes use precise session scope
  - searches use `agentId=*` and `runId=*` within the same tenant
