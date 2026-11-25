import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SANITIZER = ROOT / "collection-scripts/osl-sanitize.py"
spec = importlib.util.spec_from_file_location("sanitizer", SANITIZER)
sanitizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sanitizer)


class RedactionTests(unittest.TestCase):
    def test_structured_and_nested_payloads(self):
        source = {"items": [{"kind": "Secret", "data": {"key": "secret-data"}},
                            {"kind": "ConfigMap", "data": {"ordinary": "private"}},
                            {"spec": {"env": [{"name": "ORDINARY", "value": "sensitive"}],
                                      "password": "password-data", "args": ["--key=hidden"]},
                             "metadata": {"annotations": {"last-applied": "sensitive"}}}]}
        result = json.dumps(sanitizer.sanitize(source))
        for value in ("secret-data", "private", "sensitive", "password-data", "--key=hidden"):
            self.assertNotIn(value, result)
        self.assertEqual(len(sanitizer.sanitize(source)["items"]), 2)

    def test_text_and_reference_policy(self):
        self.assertEqual(sanitizer.sanitize({"secretRef": {"name": "db-secret"}}), {"secretRef": {"name": "db-secret"}})
        result = sanitizer.text('password="two words" Bearer abc sha256~example https://u:p@host')
        for value in ('two words', 'Bearer abc', 'sha256~example', 'u:p@'):
            self.assertNotIn(value, result)

    def test_invalid_input_does_not_echo_payload(self):
        result = subprocess.run(["python3", str(SANITIZER), "json"], input="INVALID_PRIVATE_PAYLOAD", text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout + result.stderr, "")


class CollectorTests(unittest.TestCase):
    def run_collection(self, scenario):
        temporary = tempfile.TemporaryDirectory(prefix="osl-test-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        bindir = root / "bin"
        bindir.mkdir()
        shutil.copyfile(ROOT / "tests/fake_oc.py", bindir / "oc")
        (bindir / "oc").chmod(0o700)
        trace = root / "trace.jsonl"
        output = root / "output"
        env = dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ["PATH"],
                   OSL_SANITIZER=str(SANITIZER), OSL_OUTPUT_DIR=str(output),
                   FAKE_OC_TRACE=str(trace), FAKE_OC_SCENARIO=scenario, TMPDIR=str(root))
        result = subprocess.run(["bash", str(ROOT / "collection-scripts/gather")], env=env, text=True, capture_output=True, timeout=90)
        return result, output, trace, root

    def test_discovery_logs_and_secret_exclusion(self):
        result, output, trace, root = self.run_collection("installed")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        for ns in ("openshift-serverless-logic", "custom-operator", "workflow-team", "database-team", "broker-team"):
            self.assertTrue((output / "namespaces" / ns / "pods.json").is_file(), ns)
        self.assertTrue((output / "namespaces/workflow-team/logs/controller/migration.previous.log").is_file())
        workflow = output / "namespaces/workflow-team"
        build = json.loads((workflow / "builds.build.openshift.io.json").read_text())["items"][0]
        self.assertEqual(build["status"], {"phase": "Complete", "logSnippet": "<redacted>"})
        config = json.loads((workflow / "buildconfigs.build.openshift.io.json").read_text())["items"][0]
        self.assertEqual(config["spec"]["source"], {"dockerfile": "<redacted>", "sourceSecret": {"name": "git-creds"}})
        self.assertEqual(config["spec"]["postCommit"]["script"], "<redacted>")
        self.assertEqual(config["spec"]["triggers"][0]["github"]["secret"], "<redacted>")
        stream = json.loads((workflow / "imagestreams.image.openshift.io.json").read_text())["items"][0]
        self.assertEqual(stream["status"]["tags"][0]["items"][0]["image"], "sha256:fixture")
        artifacts = "\n".join(p.read_text() for p in output.rglob("*") if p.is_file())
        for secret in ("ENV_SECRET", "CONFIG_SECRET", "SECRET_PAYLOAD", "ANNOTATION_SECRET", "LOG_SECRET", "BEARER_SECRET", "URL_SECRET", "EVENT_SECRET"):
            self.assertNotIn(secret, artifacts)
        calls = [json.loads(line) for line in trace.read_text().splitlines()]
        for call in calls:
            if call[0] == "get":
                self.assertNotIn(call[1], ("secret", "secrets", "all"))
            if call[:2] == ["adm", "inspect"]:
                self.assertEqual(call[2], "events")
        events = json.loads((output / "namespaces/workflow-team/warning-error-events.json").read_text())
        self.assertEqual([e["type"] for e in events["items"]], ["Warning"])
        self.assertIn("finished status=0", (output / "summary.log").read_text())
        self.assertEqual(list(root.glob("osl-gather.*")), [])

    def test_all_forbidden_still_completes_and_omits_stderr(self):
        result, output, _, _ = self.run_collection("forbidden")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        summary = (output / "summary.log").read_text()
        self.assertIn("WARNING", summary)
        self.assertIn("finished status=0", summary)
        self.assertNotIn("SHOULD_NOT_LEAK", summary)

    def test_crd_list_denied_uses_fallback(self):
        result, output, _, _ = self.run_collection("fallback")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue((output / "namespaces/workflow-team/pods.json").exists())

    def test_malformed_optional_resource_is_not_published(self):
        result, output, _, _ = self.run_collection("malformed")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertFalse((output / "namespaces/workflow-team/jobs.batch.json").exists())
        self.assertFalse((output / "namespaces/workflow-team/buildconfigs.build.openshift.io.json").exists())
        self.assertIn("collection failed: namespaces/workflow-team/buildconfigs.build.openshift.io.json",
                      (output / "summary.log").read_text())
        self.assertTrue((output / "namespaces/workflow-team/builds.build.openshift.io.json").exists())
        self.assertTrue((output / "namespaces/workflow-team/imagestreams.image.openshift.io.json").exists())
        self.assertTrue((output / "namespaces/workflow-team/pods.json").exists())

    def test_malformed_discovery_continues_with_fallback(self):
        result, output, _, _ = self.run_collection("malformed-discovery")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue((output / "namespaces/workflow-team/pods.json").exists())


if __name__ == "__main__":
    unittest.main()
