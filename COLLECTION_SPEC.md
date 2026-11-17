# OSL 1.39 collection specification

Status: implementation candidate; see verification results in the delivery report.
This is an independent diagnostic image, not an official Red Hat product image.

## Outcome and boundaries

Collect the state required to diagnose Operator installation, workflow builds and
deployments, supporting services, persistence connectivity, and Knative routing
and event delivery. Cluster API operations are read-only. No exec into application
containers, database queries/dumps, workflow invocation, or Secret requests.

The repository root corresponds to the requested `must-gather/OSL` directory.
Files: Dockerfile, Makefile, README.md, this specification, .dockerignore,
collection-scripts/gather, collection-scripts/osl-sanitize.py, and tests/.

## Discovery and exact scope

- Match OLM Subscription package/name `logic-operator` and legacy
  `logic-operator-rhel8` across namespaces. Include the matching namespace and
  `openshift-serverless-logic` if it exists. Collect namespace-local Subscriptions,
  InstallPlans, ClusterServiceVersions, and OperatorGroups.
- Discover every CRD whose group is exactly `sonataflow.org`; use its declared
  scope rather than a hard-coded version. Collect each definition and its CRs.
  If CRD listing is denied, try `sonataflows`, `sonataflowbuilds`,
  `sonataflowplatforms`, and `sonataflowclusterplatforms` in that group; the first
  three are namespaced candidates and the last is a cluster-scoped candidate.
  These fallback requests may fail harmlessly. No assumption that a candidate is
  installed. Namespaced CRs are listed cluster-wide and retain namespace metadata.
- Include all namespaces found in SonataFlow objects, including metadata and
  explicit platform, PostgreSQL service, and broker namespace references.
- Include `openshift-serverless`, `knative-serving`, `knative-eventing` if present.
  These are diagnostic candidates, not a claim that every workflow needs Knative.
- ClusterVersion and client version; cluster roles, cluster role bindings, and
  mutating/validating webhook configurations with names or role references
  containing `sonataflow` or `logic-operator`. Custom naming can evade this filter.
- Per selected namespace: Deployments, ReplicaSets, StatefulSets, DaemonSets,
  Jobs/CronJobs, Pods, Services, Endpoints/EndpointSlices, Routes, ConfigMaps, PVCs,
  NetworkPolicies, PDBs, HPAs, and the OLM resources above.
- Knative APIs per selected namespace: services, configurations, revisions, routes
  (`serving.knative.dev`); brokers and triggers (`eventing.knative.dev`);
  channels/subscriptions (`messaging.knative.dev`); PingSources, ContainerSources,
  ApiServerSources, SinkBindings (`sources.knative.dev`); KnativeServing and
  KnativeEventing (`operator.knative.dev`). Fully qualified resources avoid the
  OLM/Knative Subscription collision. Optional API failures are recorded.
- All events plus a Warning/Error subset. `oc adm inspect events -n NAMESPACE`
  runs in private scratch space; only sanitized JSON/YAML artifacts are published.
  HTML and other files from inspect are discarded. Namespace-wide inspection is
  deliberately replaced with event-only inspection and the explicit resource
  allowlist because `oc adm inspect ns/NAME` includes Secret collection.
- Current and previous logs from every regular/init/ephemeral container in the
  selected namespaces: includes controller managers, workflows, Data Index,
  Jobs Service, migration/build Jobs, and in-cluster PostgreSQL. Shared namespaces
  can include unrelated workloads; review the namespace list before sharing.
  There are no remote database connections or filesystem copies.

## Secret and artifact policy

Never request Secret objects. JSON/YAML sanitization drops Secret list entries,
annotations (including last-applied configurations), managedFields, ConfigMap
values, literal environment values, command/args, TLS material, JDBC URLs, and
credential-like fields. Keep resource names and Secret references where possible.
No raw stderr, kubeconfig, token, or authentication output goes into the bundle.
Scratch files use a private random directory and restrictive umask and are removed
on normal exit and caught signals. An uncatchable SIGKILL can leave scratch data;
use an ephemeral must-gather pod or a private TMPDIR for local collection.

Logs/events/free text receive best-effort masking of common credential assignments,
Bearer tokens, JWTs, OpenShift token format, URL userinfo, and PEM material. It is
not possible to recognize arbitrary application secrets in free text. Review
bundles before sharing. ConfigMap payloads are omitted rather than relying on
key names; diagnosis may require separately supplied, manually sanitized config.

## Failure and acceptance scenarios

1. Given an installed Operator and workflows outside its namespace, collection
   includes both namespaces and the discovered CRs.
2. Given cluster-platform, database, or broker references to a different namespace,
   that namespace is added within the configured namespace limit.
3. Given no optional CRDs, missing namespace, forbidden resource, or log timeout,
   other collections continue, warnings are counted, and exit status is zero.
4. Given Secret objects embedded in fixtures, credential fields, annotations,
   ConfigMap values, or literal env values, their payloads do not reach artifacts.
5. Given malformed JSON or failed sanitization for a collected resource, its raw
   bytes are not published. Discovery failures must not prevent other discovery.
6. Given a missing required tool, invalid configuration, unsafe/reused output, or
   local filesystem failure, exit nonzero. Successful completion does not imply
   complete access: read summary.log for warnings.
7. Every API command has request and wall-clock bounds. Log volume and namespace/
   pod counts are capped. There is no guaranteed aggregate size/time bound; use
   `oc adm must-gather --timeout=20m` to bound pod execution externally.
