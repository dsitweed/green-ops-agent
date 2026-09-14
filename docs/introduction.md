Đúng lúc này bạn chưa cần xây một “AI agent phức tạp”. Với bài toán của bạn, **agent là một chương trình có khả năng gọi các tool, tổng hợp dữ liệu và đưa ra kết quả có cấu trúc**.

## Repo nên xem đầu tiên

### 1. AWS CFM Tips MCP

Repo này gần nhất với bài toán FinOps của bạn:

[aws-samples/sample-cfm-tips-mcp](https://github.com/aws-samples/sample-cfm-tips-mcp)

Đọc theo thứ tự:

- [README.md](https://github.com/aws-samples/sample-cfm-tips-mcp/blob/main/README.md)
- [services/compute_optimizer.py](https://github.com/aws-samples/sample-cfm-tips-mcp/blob/main/services/compute_optimizer.py)
- [playbooks/ec2/ec2_optimization.py](https://github.com/aws-samples/sample-cfm-tips-mcp/blob/main/playbooks/ec2/ec2_optimization.py)
- [mcp_server_with_runbooks.py](https://github.com/aws-samples/sample-cfm-tips-mcp/blob/main/mcp_server_with_runbooks.py)
- services/cost_explorer.py và playbooks/ec2/ec2_optimization.py (đọc theo thứ tự)

Cấu trúc chính của nó:

```text
User
 │
 ▼
MCP tool: ec2_rightsizing
 │
 ▼
EC2 optimization playbook
 │
 ├── Compute Optimizer API
 ├── CloudWatch API
 ├── Trusted Advisor API
 └── EC2 API
 │
 ▼
JSON report
```

Ví dụ tool:

```text
ec2_rightsizing(region="us-east-1")
```

Agent nhận yêu cầu, gọi tool `ec2_rightsizing`, tool lấy dữ liệu từ AWS rồi trả report. Đây là phần quan trọng cần hiểu: **LLM không tự biết EC2 đang chạy thế nào; nó phải gọi tool để lấy dữ liệu thật**.

## Repo thứ hai để hiểu policy và approval

[aws-samples/compute-optimizer-automation](https://github.com/aws-samples/compute-optimizer-automation)

Repo này không tập trung nhiều vào LLM mà tập trung vào automation:

```text
Get recommendation
        │
        ▼
Check resource eligibility
        │
        ▼
Check risk profile
        │
        ▼
Check approval
        │
        ▼
Maintenance window
        │
        ▼
Apply change
```

Bạn nên đọc:

- `src/lambda/get-recommendations.py`
- `src/lambda/EC2-validate-recommendation.py`
- phần Architecture trong `README.md`

Nó minh họa rất rõ việc recommendation của Compute Optimizer **không được áp dụng ngay**, mà phải qua các kiểm tra deterministic.

## Agent v0.1 của bạn nên trông như thế này

```text
CLI/API
  │
  ▼
Discovery Orchestrator
  │
  ├── TerraformProvider
  ├── EC2Provider
  ├── CloudWatchProvider
  ├── ComputeOptimizerProvider
  │     └── AWS hoặc Fixture
  └── CostProvider
  │
  ▼
Normalizer
  │
  ▼
Discovery Report JSON
```

Ví dụ pseudo-code:

```python
def discover(instance_id, region):
    ec2 = ec2_provider.get_instance(instance_id, region)
    metrics = cloudwatch_provider.get_metrics(instance_id, region)
    terraform = terraform_provider.find_resource(instance_id)
    recommendation = compute_optimizer_provider.get_recommendation(
        instance_id, region
    )

    return {
        "resource": ec2,
        "metrics": metrics,
        "terraform": terraform,
        "recommendation": recommendation,
        "source": {
            "ec2": "aws",
            "metrics": "fixture",
            "recommendation": "fixture",
        },
    }
```

Ở giai đoạn đầu, chương trình này **đã là agent Discovery**, dù chưa dùng LLM.

LLM chỉ nên được thêm sau để làm việc như:

```text
Input: Discovery Report JSON
Output: giải thích bằng ngôn ngữ tự nhiên
```

Không nên để LLM tự tính CPU trung bình, tự gọi `modify-instance-attribute`, hoặc tự quyết định apply Terraform.

## Thứ tự học và triển khai

1. Chạy `sample-cfm-tips-mcp` và đọc cách tool gọi `boto3`.
2. Viết `EC2Provider` của riêng bạn.
3. Viết `CloudWatchProvider`.
4. Viết `ComputeOptimizerProvider` với fixture.
5. Ghép thành lệnh:

```bash
python -m agent discover \
  --instance-id i-123456 \
  --region us-east-1
```

6. Xuất `discovery-report.json`.
7. Sau khi pipeline chạy ổn, thay fixture bằng AWS Compute Optimizer thật.
8. Cuối cùng mới thêm Bedrock/LLM để tóm tắt report.

Với repo hiện tại, bạn có thể hiểu ngắn gọn: **bước tiếp theo không phải “xây AI” mà là xây các provider và Discovery Orchestrator**. LLM chỉ là lớp diễn giải và điều phối phía trên các tool đó.


# Read
https://chatgpt.com/s/t_6aa68cab52248191a045d433763036b1


# key word
- RAGAS/LLM-as-judge.
- AspectCritic
- AgentGoalAccuracy
- F1
- ground truth