#!/usr/bin/env python3
"""Sanitize diagnostic streams before publication; never print parsing errors."""

import json
import re
import sys

REDACTED = "<redacted>"
SENSITIVE = re.compile(r"password|passwd|token|credential|private.?key|client.?secret|authorization|jdbcurl|connectionstring", re.I)


def text(value):
    value = re.sub(r"-----BEGIN [^-]*(?:PRIVATE KEY|CERTIFICATE)-----.*?-----END [^-]+-----", REDACTED, value, flags=re.S)
    value = re.sub(r"(?i)(bearer\s+)\S+", r"\1<redacted>", value)
    value = re.sub(r"(?i)([a-z][a-z0-9+.-]*://)[^\s/@]+:[^\s/@]+@", r"\1<redacted>@", value)
    value = re.sub(r'''(?i)((?:password|passwd|token|client_secret|authorization|api[_-]?key)\s*[=:]\s*)(?:"[^"]*"|'[^']*'|[^\s,;]+)''', r"\1<redacted>", value)
    value = re.sub(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b", REDACTED, value)
    value = re.sub(r"sha256~[A-Za-z0-9_-]+", REDACTED, value)
    return value


def sanitize(value, in_build=False):
    if isinstance(value, list):
        return [sanitize(item, in_build) for item in value if not isinstance(item, dict) or item.get("kind") != "Secret"]
    if not isinstance(value, dict):
        return text(value) if isinstance(value, str) else value
    if value.get("kind") == "Secret":
        return {"kind": "Secret", "omitted": True}
    in_build = in_build or value.get("kind") in ("Build", "BuildConfig")
    result = {}
    for key, item in value.items():
        if key in ("annotations", "managedFields"):
            continue
        if value.get("kind") == "ConfigMap" and key in ("data", "binaryData"):
            result[key] = {name: REDACTED for name in item} if isinstance(item, dict) else REDACTED
        elif key == "value" and "name" in value:
            # All literal environment values, regardless of variable name.
            result[key] = REDACTED
        elif key in ("secretRef", "secretKeyRef", "imagePullSecrets"):
            # References are useful and contain names/keys, not Secret payloads.
            result[key] = sanitize(item, in_build)
        elif in_build and (key in ("dockerfile", "script", "logSnippet")
                           or (key == "secret" and isinstance(item, str))):
            result[key] = REDACTED
        elif SENSITIVE.search(key) or key in ("stringData", "tls", "command", "args"):
            result[key] = REDACTED
        else:
            result[key] = sanitize(item, in_build)
    return result


def main():
    mode = sys.argv[1]
    source = sys.stdin.read()
    if mode == "text":
        sys.stdout.write(text(source))
    elif mode == "json":
        json.dump(sanitize(json.loads(source)), sys.stdout, indent=2)
        sys.stdout.write("\n")
    elif mode == "yaml":
        import yaml
        yaml.safe_dump_all((sanitize(doc) for doc in yaml.safe_load_all(source)), sys.stdout, sort_keys=False)
    else:
        raise ValueError("unsupported mode")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Do not leak offending source text through exception messages.
        sys.exit(1)
