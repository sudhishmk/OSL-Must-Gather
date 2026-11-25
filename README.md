# OSL must-gather

Diagnostic collection image targeting Red Hat OpenShift Serverless Logic 1.39.
This repository is an independent implementation, not an official Red Hat image.

## Run the published image

The image is published on [Quay.io](https://quay.io/repository/rhn-support-sudnair/osl-must-gather):

```text
quay.io/rhn-support-sudnair/osl-must-gather:1.39
```

Log in to your OpenShift cluster with `oc`, then run:

```bash
oc adm must-gather --timeout=20m \
  --image=quay.io/rhn-support-sudnair/osl-must-gather:1.39
```

`oc adm must-gather` creates temporary cluster resources and downloads output to
your workstation; run it with appropriate administrative access. The collector's
own API operations only read. Never place tokens in source files or image layers.

## Build a custom image

Build and publish to a registry you control (Podman is the default runtime):

```bash
make lint
make test
make build IMAGE=quay.io/YOUR_ORG/osl-must-gather:1.39
make push IMAGE=quay.io/YOUR_ORG/osl-must-gather:1.39
oc adm must-gather --timeout=20m --image=quay.io/YOUR_ORG/osl-must-gather:1.39
```

Replace `YOUR_ORG` with your own registry namespace when building a custom image.

The Dockerfile pins the default `quay.io/openshift/origin-must-gather` base by
digest. To select another base, set `OPENSHIFT_VERSION` to a tag or `tag@sha256:…`
and verify it against your target cluster. Set `CONTAINER_ENGINE=docker` to use
Docker. Builds install Python 3 and PyYAML using the base image's configured RPM
repositories.
`make clean IMAGE=...` removes only that local image and does not prune storage.

## Artifacts and limits

The `/must-gather` directory contains:

- `version` and `summary.log`, including timestamps, warning counts and completion.
- `cluster/`: version, matching OLM subscriptions, SonataFlow CRs/CRDs, filtered
  operator RBAC and webhook configurations.
- `namespaces/NAME/`: workload, OLM, networking, storage and Knative JSON;
  events, warning/error events, sanitized event-inspect artifacts, and container
  logs organized by pod and container (current and previous).

Namespaces are discovered from the Operator, SonataFlow resources and explicit
namespace references, plus installed standard Knative control-plane namespaces.
This includes shared namespaces and their unrelated workloads. See
[COLLECTION_SPEC.md](COLLECTION_SPEC.md) for the precise API allowlist and gaps.
Run the standard OpenShift must-gather separately for broader cluster diagnosis.

Secret objects are never requested. ConfigMap values, literal env values,
annotations, command arguments, TLS and recognized credential fields are redacted.
Secret references remain useful where possible. Logs and free text receive
best-effort redaction; arbitrary application secrets may still occur. Review the
bundle before sharing. There are no database dumps or application API calls.

Optional API/RBAC/log failures produce warnings and allow completion with exit
code zero. Missing prerequisites, invalid settings, local I/O failures and signals
are failures. A zero status does not mean every resource was collected.

Defaults: 100 namespaces, 200 pods per namespace, 24 hours of logs, 2,000 lines and
1 MiB per container/log stream; 30-second API request and 60-second command bounds.
Previous logs may be absent when a container has not restarted. There is no hard
aggregate disk limit. The outer `--timeout=20m` bounds pod execution and may leave
an incomplete collection; check summary.log.

Pass overrides through an explicit gather command, for example:

```bash
oc adm must-gather --timeout=20m --image=quay.io/rhn-support-sudnair/osl-must-gather:1.39 -- \
  /usr/bin/env OSL_MAX_NAMESPACES=50 OSL_MAX_PODS=100 OSL_LOG_SINCE=6h /usr/bin/gather
```

Other settings: `OSL_LOG_BYTES`, `OSL_REQUEST_TIMEOUT`, `OSL_COMMAND_TIMEOUT`.
Durations accept a positive integer followed by `s`, `m`, or `h`. Numeric limits
must be positive integers. `OSL_OUTPUT_DIR` must be a fresh, empty, private output
directory. `TMPDIR` should be private; raw non-Secret discovery/inspect responses
briefly exist there before sanitization. Scratch is removed on normal/caught exit.

## Development and verification

Requirements: Bash, ShellCheck, Python 3, PyYAML, and Podman or Docker. Local
collection additionally needs oc, GNU timeout, and existing cluster authentication.
Do not run against a live cluster to execute the offline tests.

```bash
make lint
make test
make build IMAGE=localhost/osl-must-gather:1.39-dev
```

Offline tests use a fake oc and temporary directories; they verify requested API
scope, namespace discovery, redaction, optional failures and completion summaries.
They do not validate a real cluster, image availability or OpenShift packaging.
For a controlled local collection (writes only output, scratch and oc caches):

```bash
OSL_OUTPUT_DIR=/tmp/osl-diagnostics-new \
OSL_SANITIZER="$PWD/collection-scripts/osl-sanitize.py" \
bash collection-scripts/gather
```

This command uses your current kubeconfig; it does not log in or change contexts.
Avoid running it with an output path containing existing files. Inspect the output
before uploading. Obtain your organization's approval before cluster collection.
