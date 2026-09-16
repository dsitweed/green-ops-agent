https://github.com/aws-samples/compute-optimizer-automation
https://github.com/aws-samples/sample-cfm-tips-mcp


services/compute_optimizer.py
playbooks/ec2/ec2_optimization.py
mcp_server_with_runbooks.py

PYTHONPATH=src uv run python src/greenops_agent.py

## Cloud Custodian governance

The pipeline runs deterministic Cloud Custodian guardrails before generating
any Terraform patch. The actionless policy bundle is in
[`policies/governance.yml`](policies/governance.yml); it enforces required
ownership tags and excludes opted-out or protected resources. The Python
preflight also enforces production immutability, account and region
allowlists, supported resource types, action allowlists, minimum resource age,
mandatory backups for high-risk actions, and execution limits.

Configure the account and region boundaries with `CUSTODIAN_ALLOWED_ACCOUNTS`,
`CUSTODIAN_BLOCKED_ACCOUNTS`, and `CUSTODIAN_ALLOWED_REGIONS` in `.env`.
High-risk actions (`terminate`, `delete`, and `destroy`) never auto-approve and
require `approval_granted=True`.