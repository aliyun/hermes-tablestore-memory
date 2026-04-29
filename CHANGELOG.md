# Changelog

All notable changes to this project will be documented in this file.

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
  - control-plane credentials may also be required for automatic instance bootstrap
  - the first request after bootstrap can briefly fail during endpoint DNS propagation
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
