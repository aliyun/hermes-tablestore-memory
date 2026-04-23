# Changelog

All notable changes to this project will be documented in this file.

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
