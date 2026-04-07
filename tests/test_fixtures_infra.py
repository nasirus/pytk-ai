import unittest

try:
    from tests.helpers import load_fixture
except ImportError:
    from helpers import load_fixture
from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FixturesInfraTests(unittest.TestCase):
    def _run(self, name):
        f = load_fixture("infra", name)
        result = filter_output(
            f["command"],
            f["stdout"],
            f["stderr"],
            f["exit_code"],
            plan=plan_command(f["command"]),
        )
        return f, result

    def test_docker_ps(self):
        f, result = self._run("docker_ps")
        self.assertEqual(result.filter_name, f["filter_name"])
        self.assertIn("docker ps: 6 containers", result.output)
        self.assertIn("web", result.output)
        self.assertIn("cache", result.output)
        self.assertIn("kind-cloud-provider", result.output)

    def test_docker_images(self):
        f, result = self._run("docker_images")
        self.assertEqual(result.filter_name, f["filter_name"])
        self.assertIn("docker images: 33 images (17.0GB)", result.output)
        self.assertIn("browserless/chrome:latest [4.51GB]", result.output)
        self.assertIn("kindest/node:v1.35.1 [1.29GB]", result.output)
        self.assertIn("... +18 more images", result.output)

    def test_docker_logs(self):
        f, result = self._run("docker_logs")
        self.assertEqual(result.filter_name, f["filter_name"])
        self.assertIn("repeated line omitted 2 time(s)", result.output)
        self.assertIn("repeated line omitted 1 time(s)", result.output)

    def test_docker_compose_ps(self):
        f, result = self._run("docker_compose_ps")
        self.assertEqual(result.filter_name, f["filter_name"])
        self.assertIn("docker compose ps: 3 services", result.output)
        self.assertIn("web (ubuntu:24.04) Up 2 seconds (healthy)", result.output)
        self.assertIn(
            "cache (postgres:16-alpine) Up 2 seconds (healthy)", result.output
        )

    def test_kubectl_pods_json(self):
        f, result = self._run("kubectl_pods_json")
        self.assertEqual(result.filter_name, f["filter_name"])
        self.assertIn("kubectl pods: 13 pods", result.output)
        self.assertIn("11 running, 1 pending, 1 failed", result.output)
        self.assertIn("pytk-fixture/failed-shell Failed", result.output)
        self.assertIn("pytk-fixture/pending-worker Pending", result.output)

    def test_kubectl_services(self):
        f, result = self._run("kubectl_services")
        self.assertEqual(result.filter_name, f["filter_name"])
        self.assertIn("kubectl services: 3 services", result.output)
        self.assertIn("pytk-api ClusterIP [8080/TCP]", result.output)
        self.assertIn("pytk-metrics NodePort [9090:30090/TCP]", result.output)

    def test_kubectl_pods_table(self):
        f, result = self._run("kubectl_pods_table")
        self.assertEqual(result.filter_name, f["filter_name"])
        self.assertIn("kubectl pods: 13 pods", result.output)
        self.assertIn("11 running, 1 pending, 1 failed", result.output)
        self.assertIn("pytk-fixture/failed-shell StartError", result.output)
        self.assertIn("pytk-fixture/pending-worker Pending", result.output)

    def test_terraform_plan(self):
        f, result = self._run("terraform_plan")
        self.assertEqual(result.filter_name, f["filter_name"])
        self.assertNotIn("Refreshing state", result.output)
        self.assertIn("Plan: 2 to add, 0 to change, 1 to destroy.", result.output)
        self.assertIn("null_resource.metrics will be created", result.output)
        self.assertIn("null_resource.web must be replaced", result.output)

    def test_terraform_validate_ok(self):
        f, result = self._run("terraform_validate_ok")
        self.assertEqual(result.filter_name, "terraform.validate")
        self.assertEqual(result.output, "terraform validate: ok (valid)")

    def test_terraform_validate_fail(self):
        f, result = self._run("terraform_validate_fail")
        self.assertEqual(result.filter_name, "terraform.validate")
        self.assertIn("Unsupported block type", result.output)
        self.assertIn(
            'Blocks of type "invalid_block" are not expected here.', result.output
        )

    def test_aws_ec2(self):
        f, result = self._run("aws_ec2")
        self.assertEqual(result.filter_name, f["filter_name"])
        self.assertIn("0 instances", result.output)

    def test_success_fixtures_reduce_tokens(self):
        for name in ("docker_ps", "docker_images", "terraform_plan"):
            with self.subTest(name=name):
                f, result = self._run(name)
                self.assertLess(len(result.output), len(f["stdout"]))
