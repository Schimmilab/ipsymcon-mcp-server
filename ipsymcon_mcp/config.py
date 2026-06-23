"""Instance configuration: resolve a named IP-Symcon target to an IPSClient.

Two sources, in order:

1. **Multi-instance YAML** at ``IPS_INSTANCES_FILE`` — named connections:

   ```yaml
   default: home
   instances:
     home:
       url: http://192.168.1.10:3777/api/
       user: ""
       password: ""
     linux:
       url: http://192.168.1.20:3777/api/
   ```

2. **Single env** (``IPS_URL`` / ``IPS_USER`` / ``IPS_PASSWORD``) — used as the implicit
   ``default`` instance when no YAML file is configured. Keeps single-instance setups
   working unchanged (backward compatible).
"""

from __future__ import annotations

import os
from pathlib import Path

from .client import IPSClient, IPSConfigError


def _load_instances() -> tuple[dict[str, dict], str | None]:
    """Return (instances map, default name) from the YAML file or the single-env fallback."""
    path = os.environ.get("IPS_INSTANCES_FILE", "").strip()
    if path:
        import yaml  # imported lazily so single-instance setups don't need PyYAML

        raw = Path(path).expanduser().read_text(encoding="utf-8")
        data = yaml.safe_load(raw) or {}
        instances = data.get("instances") or {}
        if not isinstance(instances, dict) or not instances:
            raise IPSConfigError(f"IPS_INSTANCES_FILE '{path}' has no 'instances' map.")
        return instances, data.get("default")

    url = os.environ.get("IPS_URL", "").strip()
    if url:
        return {
            "default": {
                "url": url,
                "user": os.environ.get("IPS_USER", ""),
                "password": os.environ.get("IPS_PASSWORD", ""),
            }
        }, "default"

    return {}, None


def make_client(instance: str | None = None) -> IPSClient:
    """Build an IPSClient for the named instance (or the default)."""
    instances, default = _load_instances()
    if not instances:
        raise IPSConfigError(
            "No IP-Symcon instance configured. Set IPS_URL (single instance) or "
            "IPS_INSTANCES_FILE pointing at an instances YAML (multi-instance)."
        )

    name = instance or default or os.environ.get("IPS_DEFAULT_INSTANCE") or None
    if name is None:
        if len(instances) == 1:
            name = next(iter(instances))
        else:
            raise IPSConfigError(
                f"No instance given and no default set. Available: {', '.join(instances)}."
            )
    if name not in instances:
        raise IPSConfigError(f"Unknown instance '{name}'. Available: {', '.join(instances)}.")

    cfg = instances[name] or {}
    return IPSClient(url=cfg.get("url"), user=cfg.get("user"), password=cfg.get("password"))
