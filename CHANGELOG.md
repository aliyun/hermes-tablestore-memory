# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

- Changed `tenantId` precedence to config-first:
  - `tablestore_memory.json` `tenant_id` now overrides Hermes session `user_id`
  - session `user_id` is only used as a fallback when config `tenant_id` is empty
- Clarified installation and scope documentation:
  - after-install now documents config-first `tenant_id` resolution
  - after-install now documents write scope vs tenant-wide search scope

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
