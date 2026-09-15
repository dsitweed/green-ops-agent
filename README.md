https://github.com/aws-samples/compute-optimizer-automation
https://github.com/aws-samples/sample-cfm-tips-mcp


services/compute_optimizer.py
playbooks/ec2/ec2_optimization.py
mcp_server_with_runbooks.py

Example usage:
ec2_rightsizing(region="us-east-1")

## Run discovery through CFM Tips MCP

Clone the MCP server and install its dependencies with `uv`:

```bash
git clone https://github.com/aws-samples/sample-cfm-tips-mcp.git mcps/sample-cfm-tips-mcp
uv sync
uv run --directory mcps/sample-cfm-tips-mcp --with-requirements requirements.txt python -c "import boto3; print(boto3.Session().region_name)"
```

Adjust the values for your account, and keep
credentials outside source code. The application loads these environment
variables automatically:

```bash
AWS_PROFILE=my-finops-readonly
AWS_DEFAULT_REGION=ap-northeast-1
CFM_MCP_SERVER=mcps/sample-cfm-tips-mcp/mcp_server_with_runbooks.py
CFM_MCP_PYTHON=mcps/sample-cfm-tips-mcp/.venv/bin/python
FINOPS_APPLICATION=Taco House
FINOPS_ENVIRONMENT=staging
FINOPS_PROTECTED=false
FINOPS_EVIDENCE_WINDOW_DAYS=14
PYTHONPATH=src uv run python src/agent_finops.py
```

The adapter starts `mcp_server_with_runbooks.py` over stdio and calls
`ec2_rightsizing`. MCP supplies Compute Optimizer recommendations only; EC2
metadata, CloudWatch evidence, Terraform ownership, and cost data still need
separate read-only providers before this can be considered complete discovery.