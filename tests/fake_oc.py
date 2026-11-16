#!/usr/bin/env python3
"""Deterministic CLI boundary fixture; never contacts a cluster."""
import json
import os
from pathlib import Path
import sys

args = [a for a in sys.argv[1:] if not a.startswith("--request-timeout=")]
with open(os.environ["FAKE_OC_TRACE"], "a") as trace:
    trace.write(json.dumps(args) + "\n")
scenario = os.environ.get("FAKE_OC_SCENARIO", "installed")
if scenario == "forbidden":
    print("Forbidden password=SHOULD_NOT_LEAK", file=sys.stderr)
    sys.exit(1)
if args[:2] == ["version", "--client"]:
    print('{"clientVersion":{"gitVersion":"fixture"}}')
    sys.exit(0)
if args[:2] == ["adm", "inspect"]:
    assert args[2] == "events"
    ns = args[args.index("-n") + 1]
    dest = Path(next(a.split("=", 1)[1] for a in args if a.startswith("--dest-dir=")))
    dest.mkdir(parents=True)
    (dest / "events.json").write_text(json.dumps({"items": [{"message": "password=EVENT_SECRET", "namespace": ns}]}))
    sys.exit(0)
if args[0] == "logs":
    print("password=LOG_SECRET Bearer BEARER_SECRET https://user:URL_SECRET@db.example/path")
    sys.exit(0)
assert args[0] == "get", args
resource = args[1]
if resource == "namespace":
    if args[2] != "openshift-serverless-logic":
        sys.exit(1)
    print('namespace/openshift-serverless-logic' if "name" in args else '{"kind":"Namespace","metadata":{"name":"openshift-serverless-logic"}}')
    sys.exit(0)
if resource == "customresourcedefinitions.apiextensions.k8s.io":
    if scenario == "malformed-discovery":
        print("not-json")
        sys.exit(0)
    if scenario == "fallback":
        sys.exit(1)
    items = [{"metadata": {"name": name + ".sonataflow.org"}, "spec": {"group": "sonataflow.org", "scope": scope}}
             for name, scope in [("sonataflows", "Namespaced"), ("sonataflowplatforms", "Namespaced"), ("sonataflowclusterplatforms", "Cluster")]]
elif resource == "subscriptions.operators.coreos.com":
    if scenario == "malformed-discovery":
        print("not-json")
        sys.exit(0)
    items = [{"metadata": {"name": "logic-operator", "namespace": "custom-operator"}, "spec": {"name": "logic-operator"}}]
elif resource.endswith(".sonataflow.org"):
    items = [{"kind": "SonataFlow", "metadata": {"name": "hello", "namespace": "workflow-team", "annotations": {"last-applied": "ANNOTATION_SECRET"}},
              "spec": {"persistence": {"postgresql": {"serviceRef": {"name": "postgres", "namespace": "database-team"}, "secretRef": {"name": "db-creds"}}}, "eventing": {"broker": {"ref": {"namespace": "broker-team"}}}}}]
elif resource == "pods":
    items = [{"kind": "Pod", "metadata": {"name": "controller"}, "spec": {"containers": [{"name": "manager", "env": [{"name": "ORDINARY_NAME", "value": "ENV_SECRET"}]}], "initContainers": [{"name": "migration"}]}}]
elif resource == "configmaps":
    items = [{"kind": "ConfigMap", "metadata": {"name": "config"}, "data": {"ordinary": "CONFIG_SECRET"}}, {"kind": "Secret", "data": {"payload": "SECRET_PAYLOAD"}}]
elif resource == "events":
    items = [{"type": "Warning", "message": "password=EVENT_SECRET"}, {"type": "Normal", "message": "Ready"}]
elif resource == "jobs.batch":
    if scenario == "malformed":
        print("invalid-json PASSWORD_RAW")
        sys.exit(0)
    sys.exit(1)  # A missing optional API must not stop subsequent collection.
else:
    items = []
print(json.dumps({"apiVersion": "v1", "kind": "List", "items": items}))
