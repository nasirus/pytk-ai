import unittest

from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FiltersInfraTests(unittest.TestCase):
    def test_docker_ps_summarizes_container_table(self):
        stdout = """CONTAINER ID   IMAGE          COMMAND   CREATED        STATUS         PORTS                    NAMES
abc123def456   nginx:latest   "nginx"   2 hours ago    Up 2 hours     0.0.0.0:80->80/tcp       web
987654fedcba   redis:7        "redis"   20 minutes ago  Up 20 minutes                           cache
"""
        result = filter_output(
            "docker ps",
            stdout,
            "",
            0,
            plan=plan_command("docker ps"),
        )
        self.assertEqual(result.filter_name, "docker.ps")
        self.assertIn("docker ps: 2 containers", result.output)
        self.assertIn("abc123def456 web (nginx:latest) Up 2 hours [80]", result.output)
        self.assertIn("987654fedcba cache (redis:7) Up 20 minutes", result.output)

    def test_docker_images_summarizes_images_and_total_size(self):
        stdout = """IMAGE                                              ID             DISK USAGE   CONTENT SIZE   EXTRA
browserless/chrome:latest                         57d19e414d9f       4.51GB         1.25GB   U
diygod/rsshub:latest                              5deed9faf8ee        643MB          119MB   U
docker/desktop-cloud-provider-kind:v0.5.0         4ad59ce20658        595MB          162MB   U
"""
        result = filter_output(
            "docker images",
            stdout,
            "",
            0,
            plan=plan_command("docker images"),
        )
        self.assertEqual(result.filter_name, "docker.images")
        self.assertIn("docker images: 3 images (5.7GB)", result.output)
        self.assertIn("browserless/chrome:latest [4.51GB]", result.output)
        self.assertIn(
            "docker/desktop-cloud-provider-kind:v0.5.0 [595MB]", result.output
        )

    def test_docker_logs_deduplicates_repeated_lines(self):
        stdout = "boot\nsame\nsame\nsame\nready\n"
        result = filter_output(
            "docker logs web",
            stdout,
            "",
            0,
            plan=plan_command("docker logs web"),
        )
        self.assertEqual(result.filter_name, "docker.logs")
        self.assertIn("docker logs web:", result.output)
        self.assertIn("repeated line omitted 2 time(s)", result.output)

    def test_docker_compose_ps_summarizes_services(self):
        stdout = """NAME      IMAGE                COMMAND                   SERVICE   CREATED         STATUS                   PORTS
cache     postgres:16-alpine   \"docker-entrypoint.s…\"    cache     3 seconds ago   Up 2 seconds (healthy)   5432/tcp
web       ubuntu:24.04         \"bash -lc 'printf \\\"b…\"   web       3 seconds ago   Up 2 seconds (healthy)
"""
        result = filter_output(
            "docker compose ps",
            stdout,
            "",
            0,
            plan=plan_command("docker compose ps"),
        )
        self.assertEqual(result.filter_name, "docker.compose.ps")
        self.assertIn("docker compose ps: 2 services", result.output)
        self.assertIn(
            "cache (postgres:16-alpine) Up 2 seconds (healthy) [5432]", result.output
        )
        self.assertIn("web (ubuntu:24.04) Up 2 seconds (healthy)", result.output)

    def test_docker_compose_logs_deduplicates_repeated_lines(self):
        stdout = "web-1  | boot\nweb-1  | same\nweb-1  | same\nweb-1  | ready\n"
        result = filter_output(
            "docker compose logs web",
            stdout,
            "",
            0,
            plan=plan_command("docker compose logs web"),
        )
        self.assertEqual(result.filter_name, "docker.compose.logs")
        self.assertIn("docker compose logs web:", result.output)
        self.assertIn("repeated line omitted 1 time(s)", result.output)

    def test_docker_compose_build_summarizes_build_progress(self):
        stdout = """[+] Building 12.3s (8/8) FINISHED
 => [web internal] load build definition from Dockerfile           0.0s
 => [web internal] load metadata for docker.io/library/node:20     1.2s
 => [web 1/4] FROM docker.io/library/node:20@sha256:abc123         0.0s
 => [web 2/4] WORKDIR /app                                         0.1s
 => [web 3/4] COPY package*.json ./                                0.1s
 => [web 4/4] RUN npm install                                      8.5s
 => [web] exporting to image                                       2.3s
"""
        result = filter_output(
            "docker compose build web",
            stdout,
            "",
            0,
            plan=plan_command("docker compose build web"),
        )
        self.assertEqual(result.filter_name, "docker.compose.build")
        self.assertIn(
            "docker compose build: [+] Building 12.3s (8/8) FINISHED", result.output
        )
        self.assertIn("Services: web", result.output)
        self.assertIn("Steps: 7", result.output)

    def test_kubectl_pods_summarizes_json_issues(self):
        stdout = """{
  "items": [
    {
      "metadata": {"namespace": "default", "name": "api-123"},
      "status": {
        "phase": "Running",
        "containerStatuses": [{"restartCount": 1}]
      }
    },
    {
      "metadata": {"namespace": "jobs", "name": "worker-456"},
      "status": {
        "phase": "Pending",
        "containerStatuses": [{"restartCount": 0}]
      }
    }
  ]
}"""
        result = filter_output(
            "kubectl get pods -A -o json",
            stdout,
            "",
            0,
            plan=plan_command("kubectl get pods -A -o json"),
        )
        self.assertEqual(result.filter_name, "kubectl.pods")
        self.assertIn(
            "kubectl pods: 2 pods (1 running, 1 pending, 1 restarts)", result.output
        )
        self.assertIn("jobs/worker-456 Pending", result.output)

    def test_kubectl_services_summarizes_table_output(self):
        stdout = """NAME         TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)          AGE
kubernetes   ClusterIP   10.96.0.1      <none>        443/TCP          10d
api          ClusterIP   10.96.10.10    <none>        8080/TCP         2d
"""
        result = filter_output(
            "kubectl get services",
            stdout,
            "",
            0,
            plan=plan_command("kubectl get services"),
        )
        self.assertEqual(result.filter_name, "kubectl.services")
        self.assertIn("kubectl services: 2 services", result.output)
        self.assertIn("api ClusterIP [8080/TCP]", result.output)

    def test_kubectl_pods_namespaced_table_uses_status_column(self):
        stdout = """NAMESPACE   NAME         READY   STATUS             RESTARTS   AGE
default     api-123      1/1     Running            1          2d
jobs        worker-456   0/1     Pending            0          10m
ops         cron-789     0/1     CrashLoopBackOff   7          5m
"""
        result = filter_output(
            "kubectl get pods -A",
            stdout,
            "",
            0,
            plan=plan_command("kubectl get pods -A"),
        )
        self.assertEqual(result.filter_name, "kubectl.pods")
        self.assertIn(
            "kubectl pods: 3 pods (1 running, 1 pending, 1 failed, 8 restarts)",
            result.output,
        )
        self.assertIn("jobs/worker-456 Pending", result.output)
        self.assertIn("ops/cron-789 CrashLoopBackOff", result.output)

    def test_kubectl_services_namespaced_table_uses_namespace_prefix(self):
        stdout = """NAMESPACE   NAME         TYPE        CLUSTER-IP    EXTERNAL-IP   PORT(S)    AGE
default     kubernetes   ClusterIP   10.96.0.1     <none>        443/TCP    10d
apps        api          ClusterIP   10.96.10.10   <none>        8080/TCP   2d
"""
        result = filter_output(
            "kubectl get services -A",
            stdout,
            "",
            0,
            plan=plan_command("kubectl get services -A"),
        )
        self.assertEqual(result.filter_name, "kubectl.services")
        self.assertIn("kubectl services: 2 services", result.output)
        self.assertIn("default/kubernetes ClusterIP [443/TCP]", result.output)
        self.assertIn("apps/api ClusterIP [8080/TCP]", result.output)

    def test_kubectl_logs_deduplicates_repeated_lines(self):
        stdout = "line1\nline2\nline2\nline2\n"
        result = filter_output(
            "kubectl logs api-123",
            stdout,
            "",
            0,
            plan=plan_command("kubectl logs api-123"),
        )
        self.assertEqual(result.filter_name, "kubectl.logs")
        self.assertIn("kubectl logs api-123:", result.output)
        self.assertIn("repeated line omitted 2 time(s)", result.output)

    def test_aws_read_summarizes_structured_json(self):
        stdout = """{
  "Reservations": [
    {
      "Instances": [
        {
          "InstanceId": "i-abc123",
          "State": {"Name": "running"},
          "InstanceType": "t3.micro",
          "PrivateIpAddress": "10.0.1.5",
          "Tags": [{"Key": "Name", "Value": "web"}]
        }
      ]
    }
  ]
}"""
        result = filter_output(
            "aws ec2 describe-instances --output json",
            stdout,
            "",
            0,
            plan=plan_command("aws ec2 describe-instances --output json"),
        )
        self.assertEqual(result.filter_name, "aws.read")
        self.assertIn("aws ec2 describe-instances: 1 instances", result.output)
        self.assertIn("i-abc123 running t3.micro 10.0.1.5 (web)", result.output)

    def test_terraform_plan_strips_refresh_noise(self):
        stdout = """Acquiring state lock. This may take a few moments...
Refreshing state... [id=vpc-abc]

Terraform will perform the following actions:

  # aws_instance.web will be created
  + resource \"aws_instance\" \"web\" {}

Plan: 1 to add, 0 to change, 0 to destroy.
"""
        result = filter_output(
            "terraform plan",
            stdout,
            "",
            0,
            plan=plan_command("terraform plan"),
        )
        self.assertEqual(result.filter_name, "terraform.plan")
        self.assertNotIn("Refreshing state", result.output)
        self.assertIn("Plan: 1 to add, 0 to change, 0 to destroy.", result.output)

    def test_terraform_validate_short_circuits_success(self):
        result = filter_output(
            "terraform validate",
            "Success! The configuration is valid.\n",
            "",
            0,
            plan=plan_command("terraform validate"),
        )
        self.assertEqual(result.filter_name, "terraform.validate")
        self.assertEqual(result.output, "terraform validate: ok (valid)")

    def test_infra_failures_keep_raw_output(self):
        stderr = "Error: Unsupported block type\n  on main.tf line 7\n"
        result = filter_output(
            "terraform validate",
            "",
            stderr,
            1,
            plan=plan_command("terraform validate"),
        )
        self.assertEqual(result.filter_name, "terraform.validate")
        self.assertIn("Unsupported block type", result.output)
