"""TableStore memory plugin backed by the official OTS Python SDK."""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider
from tools.registry import tool_error

try:
    from tablestore import OTSClient as OTSClient
except Exception:
    OTSClient = None

try:
    from alibabacloud_credentials.client import Client as CredentialClient
    from alibabacloud_tea_openapi import models as open_api_models
    from alibabacloud_tablestore20201209.client import Client as Tablestore20201209Client
    from alibabacloud_tablestore20201209 import models as tablestore_20201209_models
    from alibabacloud_tea_util import models as util_models
except Exception:
    CredentialClient = None
    open_api_models = None
    Tablestore20201209Client = None
    tablestore_20201209_models = None
    util_models = None

logger = logging.getLogger(__name__)

_DEFAULT_ENDPOINT = "https://127.0.0.1"
_DEFAULT_TIMEOUT = 30.0
_DEFAULT_MEMORY_STORE = "hermes_mem"
_DEFAULT_REGION = "cn-beijing"
_DEFAULT_CONTROL_ENDPOINT = f"tablestore.{_DEFAULT_REGION}.aliyuncs.com"


def _is_not_found_error(exc: Exception) -> bool:
    text = str(exc)
    markers = (
        "NOT_FOUND",
        "404",
        "OTSObjectNotExist",
        "resource not found",
    )
    return any(marker in text for marker in markers)


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _clean_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _scope_piece(value: Any, default: str = "__default__") -> str:
    text = _clean_str(value, "")
    return text if text else default


def _build_instance_endpoint(instance_name: str, region: str = _DEFAULT_REGION) -> str:
    return f"https://{instance_name}.{region}.ots.aliyuncs.com"


def _load_config() -> dict:
    """Load non-secret config from JSON and secrets from env."""
    from hermes_constants import get_hermes_home

    config = {
        "endpoint": _DEFAULT_ENDPOINT,
        "instance_name": "",
        "memory_store_name": _DEFAULT_MEMORY_STORE,
        "description": "",
        "app_id": "hermes",
        "tenant_id": "",
        "access_key_id": "",
        "access_key_secret": "",
        "enable_rerank": True,
        "auto_create_store": True,
        "timeout": _DEFAULT_TIMEOUT,
    }

    config_path = get_hermes_home() / "tablestore_memory.json"
    if config_path.exists():
        try:
            file_cfg = json.loads(config_path.read_text(encoding="utf-8"))
            for key, value in file_cfg.items():
                if value in (None, ""):
                    continue
                config[key] = value
        except Exception as exc:
            logger.debug("Failed to load tablestore_memory.json: %s", exc)

    config["access_key_id"] = os.environ.get("TABLESTORE_MEMORY_AK", "")
    config["access_key_secret"] = os.environ.get("TABLESTORE_MEMORY_SK", "")
    config["endpoint"] = _clean_str(config.get("endpoint"), _DEFAULT_ENDPOINT)
    config["instance_name"] = _clean_str(config.get("instance_name"))
    config["memory_store_name"] = _clean_str(config.get("memory_store_name"), _DEFAULT_MEMORY_STORE)
    config["description"] = _clean_str(config.get("description"))
    config["app_id"] = _clean_str(config.get("app_id"), "hermes")
    config["tenant_id"] = _clean_str(config.get("tenant_id"))
    config["access_key_id"] = _clean_str(config.get("access_key_id"))
    config["access_key_secret"] = _clean_str(config.get("access_key_secret"))
    config["enable_rerank"] = _as_bool(config.get("enable_rerank"), True)
    config["auto_create_store"] = _as_bool(config.get("auto_create_store"), True)
    try:
        config["timeout"] = float(config.get("timeout", _DEFAULT_TIMEOUT))
    except Exception:
        config["timeout"] = _DEFAULT_TIMEOUT

    return config


class _TableStoreClient:
    """Thin wrapper around tablestore.OTSClient memory APIs."""

    def __init__(
        self,
        endpoint: str,
        instance_name: str,
        *,
        access_key_id: str,
        access_key_secret: str,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        client_cls = OTSClient
        if client_cls is None:
            from tablestore import OTSClient as client_cls

        self.endpoint = endpoint.rstrip("/")
        self.instance_name = instance_name
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.timeout = timeout
        self._client = client_cls(
            self.endpoint,
            access_key_id,
            access_key_secret,
            instance_name,
            socket_timeout=timeout,
        )

    def list_tables(self) -> Any:
        return self._client.list_table()

    def list_memory_stores(self) -> dict:
        return self._client.list_memory_stores({})

    def get_memory_store(self, memory_store_name: str) -> dict:
        return self._client.get_memory_store({"memoryStoreName": memory_store_name})

    def create_memory_store(self, memory_store_name: str, description: str = "") -> dict:
        payload = {"memoryStoreName": memory_store_name}
        if description:
            payload["description"] = description
        return self._client.create_memory_store(payload)

    def add_memories(
        self,
        memory_store_name: str,
        scope: dict,
        *,
        messages: Optional[List[dict]] = None,
        text: str = "",
        metadata: Optional[Dict[str, str]] = None,
        sync: bool = False,
    ) -> dict:
        payload = {
            "memoryStoreName": memory_store_name,
            "scope": scope,
            "sync": sync,
        }
        if messages:
            payload["messages"] = messages
        if text:
            payload["text"] = text
        if metadata:
            payload["metadata"] = metadata
        return self._client.add_memories(payload)

    def search_memories(
        self,
        memory_store_name: str,
        query: str,
        scope: dict,
        *,
        top_k: int = 10,
        enable_rerank: bool = False,
        metadata: Optional[Dict[str, str]] = None,
    ) -> dict:
        payload = {
            "memoryStoreName": memory_store_name,
            "query": query,
            "scope": scope,
            "topK": top_k,
            "enableRerank": enable_rerank,
        }
        if metadata:
            payload["metadata"] = metadata
        return self._client.search_memories(payload)

    def list_memories(
        self,
        memory_store_name: str,
        scope: dict,
        *,
        limit: int = 20,
        next_token: str = "",
    ) -> dict:
        payload = {
            "memoryStoreName": memory_store_name,
            "scope": scope,
            "limit": limit,
        }
        if next_token:
            payload["nextToken"] = next_token
        return self._client.list_memories(payload)

    def get_memory(self, memory_store_name: str, memory_id: str, scope: dict) -> dict:
        return self._client.get_memory(
            {
                "memoryStoreName": memory_store_name,
                "memoryId": memory_id,
                "scope": scope,
            }
        )

    def update_memory(
        self,
        memory_store_name: str,
        memory_id: str,
        scope: dict,
        *,
        text: str = "",
        metadata: Optional[Dict[str, str]] = None,
    ) -> dict:
        payload = {
            "memoryStoreName": memory_store_name,
            "memoryId": memory_id,
            "scope": scope,
        }
        if text:
            payload["text"] = text
        if metadata:
            payload["metadata"] = metadata
        return self._client.update_memory(payload)

    def delete_memory(self, memory_store_name: str, memory_id: str, scope: dict) -> dict:
        return self._client.delete_memory(
            {
                "memoryStoreName": memory_store_name,
                "memoryId": memory_id,
                "scope": scope,
            }
        )


class _TableStoreControlClient:
    """Control-plane helper for creating a TableStore VCU instance."""

    def __init__(self, endpoint: str = _DEFAULT_CONTROL_ENDPOINT) -> None:
        client_cls = Tablestore20201209Client
        credential_cls = CredentialClient
        config_cls = open_api_models.Config if open_api_models else None
        if client_cls is None or credential_cls is None or config_cls is None:
            from alibabacloud_credentials.client import Client as credential_cls
            from alibabacloud_tea_openapi import models as open_api_models_local
            from alibabacloud_tablestore20201209.client import Client as client_cls

            config_cls = open_api_models_local.Config

        credential = credential_cls()
        config = config_cls(credential=credential)
        config.endpoint = endpoint
        self._client = client_cls(config)

    def create_vcu_instance(self) -> dict:
        request_cls = tablestore_20201209_models.CreateVCUInstanceRequest if tablestore_20201209_models else None
        runtime_cls = util_models.RuntimeOptions if util_models else None
        if request_cls is None or runtime_cls is None:
            from alibabacloud_tablestore20201209 import models as tablestore_20201209_models_local
            from alibabacloud_tea_util import models as util_models_local

            request_cls = tablestore_20201209_models_local.CreateVCUInstanceRequest
            runtime_cls = util_models_local.RuntimeOptions

        request = request_cls(
            cluster_type="SSD",
            vcu=0,
            period_in_month=1,
            enable_elastic_vcu=True,
            enable_auto_renew=True,
            auto_renew_period_in_month=1,
        )
        response = self._client.create_vcuinstance_with_options(request, {}, runtime_cls())
        if isinstance(response, dict):
            return response
        body = getattr(response, "body", None)
        if body is not None:
            if hasattr(body, "to_map"):
                return body.to_map()
            if isinstance(body, dict):
                return body
        if hasattr(response, "to_map"):
            return response.to_map()
        raise RuntimeError("CreateVCUInstance returned an unexpected response payload.")

    def update_instance_network_acl(self, instance_name: str, acl: List[str]) -> dict:
        request_cls = tablestore_20201209_models.UpdateInstanceRequest if tablestore_20201209_models else None
        runtime_cls = util_models.RuntimeOptions if util_models else None
        if request_cls is None or runtime_cls is None:
            from alibabacloud_tablestore20201209 import models as tablestore_20201209_models_local
            from alibabacloud_tea_util import models as util_models_local

            request_cls = tablestore_20201209_models_local.UpdateInstanceRequest
            runtime_cls = util_models_local.RuntimeOptions

        request = request_cls(
            instance_name=instance_name,
            network_type_acl=acl,
        )
        response = self._client.update_instance_with_options(request, {}, runtime_cls())
        if isinstance(response, dict):
            return response
        body = getattr(response, "body", None)
        if body is not None:
            if hasattr(body, "to_map"):
                return body.to_map()
            if isinstance(body, dict):
                return body
        if hasattr(response, "to_map"):
            return response.to_map()
        return {}


PROFILE_SCHEMA = {
    "name": "tablestore_profile",
    "description": (
        "List durable memories already stored in the current TableStore memory scope. "
        "Use at conversation start when you want a direct snapshot of known facts."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum memories to return (default: 10, max: 100).",
            },
        },
        "required": [],
    },
}

SEARCH_SCHEMA = {
    "name": "tablestore_search",
    "description": (
        "Semantic search over TableStore long-term memory. Returns ranked memory hits "
        "with ids and exact scope so you can inspect or delete them later."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search for."},
            "top_k": {"type": "integer", "description": "Max results (default: 8, max: 50)."},
            "enable_rerank": {
                "type": "boolean",
                "description": "Enable server-side rerank (default: provider config, true).",
            },
            "metadata": {
                "type": "object",
                "description": "Optional exact-match metadata filters.",
                "additionalProperties": {"type": "string"},
            },
        },
        "required": ["query"],
    },
}

REMEMBER_SCHEMA = {
    "name": "tablestore_remember",
    "description": (
        "Persist a durable fact or short passage to TableStore memory. "
        "Use for preferences, decisions, stable project facts, or explicit corrections."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "The durable fact or note to store."},
            "metadata": {
                "type": "object",
                "description": "Optional custom metadata for filtering later.",
                "additionalProperties": {"type": "string"},
            },
            "sync": {
                "type": "boolean",
                "description": "Wait for ingest to complete before returning (default: false).",
            },
        },
        "required": ["content"],
    },
}

FORGET_SCHEMA = {
    "name": "tablestore_forget",
    "description": (
        "Delete a specific TableStore memory by id. If the memory was found via "
        "tablestore_search, reuse the returned scope fields for an exact delete."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "memory_id": {"type": "string", "description": "Memory id to delete."},
            "app_id": {"type": "string", "description": "Override appId for the target memory."},
            "tenant_id": {"type": "string", "description": "Override tenantId for the target memory."},
            "agent_id": {"type": "string", "description": "Override agentId for the target memory."},
            "run_id": {"type": "string", "description": "Override runId for the target memory."},
        },
        "required": ["memory_id"],
    },
}


class TableStoreMemoryProvider(MemoryProvider):
    """Hermes memory provider backed by TableStore memory APIs through OTS SDK."""

    def __init__(self) -> None:
        self._config: Dict[str, Any] = {}
        self._client: Optional[_TableStoreClient] = None
        self._session_id = ""
        self._platform = "cli"
        self._app_id = "hermes"
        self._tenant_id = "__default__"
        self._agent_id = "hermes"
        self._run_id = "__default__"
        self._memory_store_name = ""
        self._enable_rerank = True
        self._prefetch_result = ""
        self._prefetch_lock = threading.Lock()
        self._prefetch_thread: Optional[threading.Thread] = None
        self._sync_thread: Optional[threading.Thread] = None

    @property
    def name(self) -> str:
        return "tablestore-mem"

    def is_available(self) -> bool:
        cfg = _load_config()
        return bool(cfg.get("access_key_id") and cfg.get("access_key_secret"))

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        config_path = Path(hermes_home) / "tablestore_memory.json"
        existing = {}
        if config_path.exists():
            try:
                existing = json.loads(config_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        existing.update(values)
        config_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False))

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {"key": "endpoint", "description": "TableStore OTS endpoint", "default": _DEFAULT_ENDPOINT},
            {"key": "instance_name", "description": "OTS instance name (optional; auto-created when missing)"},
            {"key": "memory_store_name", "description": "Memory store name", "default": _DEFAULT_MEMORY_STORE},
            {"key": "app_id", "description": "Scope appId", "default": "hermes"},
            {"key": "tenant_id", "description": "Default tenantId (gateway user_id overrides this)"},
            {"key": "description", "description": "Store description used when auto-create is enabled"},
            {"key": "enable_rerank", "description": "Enable rerank for prefetch/search by default", "default": "true", "choices": ["true", "false"]},
            {"key": "auto_create_store", "description": "Auto-create memory store if missing", "default": "true", "choices": ["true", "false"]},
            {"key": "timeout", "description": "OTS socket timeout in seconds", "default": str(_DEFAULT_TIMEOUT)},
            {"key": "access_key_id", "description": "TableStore access key id", "secret": True, "env_var": "TABLESTORE_MEMORY_AK"},
            {"key": "access_key_secret", "description": "TableStore access key secret", "secret": True, "env_var": "TABLESTORE_MEMORY_SK"},
        ]

    def _bootstrap_instance(self) -> Dict[str, str]:
        try:
            control_client = _TableStoreControlClient()
            response = control_client.create_vcu_instance()
        except Exception as exc:
            message = getattr(exc, "message", str(exc))
            recommend = ""
            data = getattr(exc, "data", None)
            if isinstance(data, dict):
                recommend = _clean_str(data.get("Recommend"))
            detail = f"Failed to create TableStore instance: {message}"
            if recommend:
                detail += f" ({recommend})"
            raise RuntimeError(detail) from exc

        instance_name = _clean_str(response.get("InstanceName"))
        if not instance_name:
            raise RuntimeError("CreateVCUInstance succeeded but did not return InstanceName.")
        try:
            control_client.update_instance_network_acl(
                instance_name,
                ["INTERNET", "VPC", "CLASSIC"],
            )
        except Exception as exc:
            message = getattr(exc, "message", str(exc))
            recommend = ""
            data = getattr(exc, "data", None)
            if isinstance(data, dict):
                recommend = _clean_str(data.get("Recommend"))
            detail = f"Failed to enable public network access for TableStore instance {instance_name}: {message}"
            if recommend:
                detail += f" ({recommend})"
            raise RuntimeError(detail) from exc
        return {
            "instance_name": instance_name,
            "endpoint": _build_instance_endpoint(instance_name),
        }

    def initialize(self, session_id: str, **kwargs) -> None:
        self._config = _load_config()
        if not self._config.get("instance_name"):
            from hermes_constants import get_hermes_home

            bootstrap_config = self._bootstrap_instance()
            self.save_config(bootstrap_config, str(get_hermes_home()))
            self._config = _load_config()
        self._session_id = session_id
        self._platform = _clean_str(kwargs.get("platform"), "cli")
        self._app_id = _scope_piece(self._config.get("app_id"), "hermes")
        self._tenant_id = _scope_piece(kwargs.get("user_id") or self._config.get("tenant_id"))
        self._agent_id = _scope_piece(kwargs.get("agent_identity"), "hermes")
        self._run_id = _scope_piece(
            kwargs.get("gateway_session_key")
            or kwargs.get("session_title")
            or session_id,
            "__default__",
        )
        self._memory_store_name = self._config.get("memory_store_name", "")
        self._enable_rerank = _as_bool(self._config.get("enable_rerank"), True)

        self._client = _TableStoreClient(
            endpoint=self._config.get("endpoint", _DEFAULT_ENDPOINT),
            instance_name=self._config.get("instance_name", ""),
            access_key_id=self._config.get("access_key_id", ""),
            access_key_secret=self._config.get("access_key_secret", ""),
            timeout=float(self._config.get("timeout", _DEFAULT_TIMEOUT)),
        )

        try:
            self._client.get_memory_store(self._memory_store_name)
        except Exception as exc:
            if self._config.get("auto_create_store", True) and _is_not_found_error(exc):
                self._client.create_memory_store(
                    self._memory_store_name,
                    self._config.get("description", ""),
                )
            else:
                raise

    def system_prompt_block(self) -> str:
        return (
            "# TableStore Memory\n"
            f"Active. Store: {self._memory_store_name}. Scope: "
            f"{self._app_id}/{self._tenant_id}/{self._agent_id}/{self._run_id}.\n"
            "Use tablestore_search for semantic recall, tablestore_profile for a "
            "direct snapshot, tablestore_remember to persist facts, and "
            "tablestore_forget to delete by id."
        )

    def run_doctor(self) -> Dict[str, Any]:
        checks: Dict[str, Any] = {
            "initialize": {"ok": bool(self._client)},
        }
        result: Dict[str, Any] = {
            "ok": True,
            "provider": self.name,
            "instance_name": self._config.get("instance_name", ""),
            "endpoint": self._config.get("endpoint", ""),
            "memory_store_name": self._memory_store_name,
            "scope": self._search_scope(),
            "checks": checks,
        }

        if not self._client:
            checks["initialize"]["error"] = "TableStore client is not initialized."
            result["ok"] = False
            return result

        try:
            payload = self._client.get_memory_store(self._memory_store_name)
            checks["describe_memory_store"] = {
                "ok": True,
                "memory_store_name": payload.get("memoryStoreName", self._memory_store_name),
            }
        except Exception as exc:
            checks["describe_memory_store"] = {
                "ok": False,
                "error": str(exc),
            }
            result["ok"] = False

        try:
            payload = self._client.list_memories(
                self._memory_store_name,
                self._search_scope(),
                limit=5,
            )
            memories = payload.get("memories", []) or []
            checks["list_memories"] = {
                "ok": True,
                "memory_count": len(memories),
                "has_next_token": bool(payload.get("nextToken")),
            }
        except Exception as exc:
            checks["list_memories"] = {
                "ok": False,
                "error": str(exc),
            }
            result["ok"] = False

        return result

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            self._prefetch_thread.join(timeout=3.0)
        with self._prefetch_lock:
            result = self._prefetch_result
            self._prefetch_result = ""
        if not result:
            return ""
        return f"## TableStore Memory\n{result}"

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        if not self._client or not query.strip():
            return

        def _run() -> None:
            try:
                payload = self._client.search_memories(
                    self._memory_store_name,
                    query,
                    self._search_scope(),
                    top_k=5,
                    enable_rerank=self._enable_rerank,
                )
                lines = []
                for hit in payload.get("results", [])[:5]:
                    unit = hit.get("unit", {}) or {}
                    text = unit.get("text", "")
                    if text:
                        lines.append(f"- {text}")
                with self._prefetch_lock:
                    self._prefetch_result = "\n".join(lines)
            except Exception as exc:
                logger.debug("TableStore prefetch failed: %s", exc)

        self._prefetch_thread = threading.Thread(
            target=_run,
            daemon=True,
            name="tablestore-prefetch",
        )
        self._prefetch_thread.start()

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        if not self._client:
            return

        def _sync() -> None:
            try:
                self._client.add_memories(
                    self._memory_store_name,
                    self._default_scope(),
                    messages=[
                        {"role": "user", "content": user_content},
                        {"role": "assistant", "content": assistant_content},
                    ],
                    metadata=self._default_metadata(source="sync_turn"),
                    sync=False,
                )
            except Exception as exc:
                logger.warning("TableStore sync failed: %s", exc)

        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_thread.join(timeout=5.0)

        self._sync_thread = threading.Thread(
            target=_sync,
            daemon=True,
            name="tablestore-sync",
        )
        self._sync_thread.start()

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [PROFILE_SCHEMA, SEARCH_SCHEMA, REMEMBER_SCHEMA, FORGET_SCHEMA]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        if not self._client:
            return tool_error("TableStore client is not initialized.")

        if tool_name == "tablestore_profile":
            limit = min(max(int(args.get("limit", 10) or 10), 1), 100)
            try:
                result = self._client.list_memories(
                    self._memory_store_name,
                    self._search_scope(),
                    limit=limit,
                )
                memories = [self._format_memory(m) for m in result.get("memories", [])]
                return json.dumps({"memories": memories, "count": len(memories)}, ensure_ascii=False)
            except Exception as exc:
                return tool_error(f"Failed to list memories: {exc}")

        if tool_name == "tablestore_search":
            query = _clean_str(args.get("query"))
            if not query:
                return tool_error("Missing required parameter: query")
            top_k = min(max(int(args.get("top_k", 8) or 8), 0), 50)
            enable_rerank = args.get("enable_rerank")
            metadata = args.get("metadata")
            try:
                result = self._client.search_memories(
                    self._memory_store_name,
                    query,
                    self._search_scope(),
                    top_k=top_k,
                    enable_rerank=self._enable_rerank if enable_rerank is None else bool(enable_rerank),
                    metadata=metadata if isinstance(metadata, dict) else None,
                )
                hits = [self._format_hit(hit) for hit in result.get("results", [])]
                return json.dumps({"results": hits, "count": len(hits)}, ensure_ascii=False)
            except Exception as exc:
                return tool_error(f"Search failed: {exc}")

        if tool_name == "tablestore_remember":
            content = _clean_str(args.get("content"))
            if not content:
                return tool_error("Missing required parameter: content")
            metadata = args.get("metadata")
            sync = False if args.get("sync") is None else bool(args.get("sync"))
            try:
                result = self._client.add_memories(
                    self._memory_store_name,
                    self._default_scope(),
                    text=content,
                    metadata=self._merge_metadata(metadata, source="tool_remember"),
                    sync=sync,
                )
                return json.dumps(result, ensure_ascii=False)
            except Exception as exc:
                return tool_error(f"Failed to store memory: {exc}")

        if tool_name == "tablestore_forget":
            memory_id = _clean_str(args.get("memory_id"))
            if not memory_id:
                return tool_error("Missing required parameter: memory_id")
            try:
                result = self._client.delete_memory(
                    self._memory_store_name,
                    memory_id,
                    self._scope_from_tool_args(args),
                )
                return json.dumps(result, ensure_ascii=False)
            except Exception as exc:
                return tool_error(f"Failed to delete memory: {exc}")

        return tool_error(f"Unknown tool: {tool_name}")

    def on_memory_write(self, action: str, target: str, content: str) -> None:
        if not self._client or action not in {"add", "replace"} or not content.strip():
            return
        try:
            self._client.add_memories(
                self._memory_store_name,
                self._default_scope(),
                text=content.strip(),
                metadata=self._default_metadata(
                    source="builtin_memory",
                    target=target,
                    action=action,
                ),
                sync=False,
            )
        except Exception as exc:
            logger.debug("TableStore memory_write mirror failed: %s", exc)

    def shutdown(self) -> None:
        for thread in (self._prefetch_thread, self._sync_thread):
            if thread and thread.is_alive():
                thread.join(timeout=5.0)
        self._client = None

    def _default_scope(self) -> dict:
        return {
            "appId": self._app_id,
            "tenantId": self._tenant_id,
            "agentId": self._agent_id,
            "runId": self._run_id,
        }

    def _search_scope(self) -> dict:
        return {
            "appId": self._app_id,
            "tenantId": self._tenant_id,
            "agentId": "*",
            "runId": "*",
        }

    def _scope_from_tool_args(self, args: Dict[str, Any]) -> dict:
        return {
            "appId": _scope_piece(args.get("app_id"), self._app_id),
            "tenantId": _scope_piece(args.get("tenant_id"), self._tenant_id),
            "agentId": _scope_piece(args.get("agent_id"), self._agent_id),
            "runId": _scope_piece(args.get("run_id"), self._run_id),
        }

    def _default_metadata(self, **extra: str) -> Dict[str, str]:
        metadata = {
            "platform": self._platform,
            "session_id": self._session_id,
        }
        for key, value in extra.items():
            text = _clean_str(value)
            if text:
                metadata[key] = text
        return metadata

    def _merge_metadata(self, metadata: Any, **extra: str) -> Dict[str, str]:
        merged = self._default_metadata(**extra)
        if isinstance(metadata, dict):
            for key, value in metadata.items():
                key_text = _clean_str(key)
                value_text = _clean_str(value)
                if key_text and value_text:
                    merged[key_text] = value_text
        return merged

    @staticmethod
    def _format_memory(memory: Dict[str, Any]) -> Dict[str, Any]:
        scope = memory.get("scope", {}) or {}
        return {
            "id": memory.get("id", ""),
            "text": memory.get("text", ""),
            "unit_type": memory.get("unit_type", ""),
            "salience": memory.get("salience"),
            "created_at": memory.get("created_at") or memory.get("createdAt"),
            "deleted": memory.get("deleted", False),
            "scope": {
                "appId": scope.get("appId", ""),
                "tenantId": scope.get("tenantId", ""),
                "agentId": scope.get("agentId", ""),
                "runId": scope.get("runId", ""),
            },
            "metadata": memory.get("metadata", {}) or {},
        }

    def _format_hit(self, hit: Dict[str, Any]) -> Dict[str, Any]:
        unit = hit.get("unit", {}) or {}
        return {
            "id": unit.get("id", ""),
            "text": unit.get("text", ""),
            "unit_type": unit.get("unit_type", ""),
            "score": hit.get("score"),
            "source": hit.get("source", ""),
            "scope": self._format_memory(unit).get("scope", {}),
        }


def register(ctx) -> None:
    """Register TableStore as a memory provider plugin."""
    ctx.register_memory_provider(TableStoreMemoryProvider())
