
# Các định nghĩa giúp hệ thống quản lý chi phí tích hợp AI
1. Deterministic rule: là thuật ngữ này gắn liền với kỷ nguyên FinOps Agent (AI đại lý). Khi các hệ thống quản lý chi phí tích hợp AI (như AWS FinOps Agent dựa trên Amazon Bedrock), người ta dùng Deterministic Rules để làm "hàng rào bảo vệ" (guardrails) hoặc làm công cụ tính toán toán học chính xác nhằm kiểm soát tính ngẫu nhiên (probabilistic) của AI.
- Tính toán chi phí tài nguyên (Pricing Math): Khi quét qua hệ thống, công cụ FinOps lấy dữ liệu từ AWS Price List Bulk API để nhân số giờ chạy với đơn giá. Phép toán này tuân theo deterministic rule (Luôn ra số tiền chính xác, không đoán mò). 
- Hệ thống phân bổ chi phí (Cost Allocation): Sử dụng các tính năng như AWS Cost Categories để gom nhóm chi phí dựa trên luật cố định: Nếu Resource Tag Env = Prod THÌ phân bổ chi phí về cho Bộ phận Vận hành. 
- Xác thực dữ liệu đầu vào (Input Validation): Trước khi đưa dữ liệu cho các AI Agent xử lý (để tránh AI tính toán sai), hệ thống sử dụng code để check nhanh xem tài nguyên có bị thiếu Tag hay không (sử dụng AWS Config Rules). 
- Tự động hóa hành động (Rule-based Automation): Thiết lập các hành động tự động bật/tắt tài nguyên theo lịch cố định hoặc cấu hình AWS Budgets để tự động gửi thông báo hoặc chặn quyền truy cập khi mức chi tiêu vượt quá 80%
2. AI Hallucination
- AI Hallucination là hiện tượng khi các AI Agent tạo ra thông tin không chính xác hoặc không tồn tại trong thực tế. Điều này có thể dẫn đến các quyết định quản lý chi phí sai lầm nếu không có các cơ chế kiểm tra và xác thực dữ liệu đầu vào.

# Các tool có thể tận dụng
1. AWS Compute Optimizer (Dùng để phân tích hiệu suất và chi phí của các tài nguyên AWS, từ đó đưa ra các đề xuất tối ưu hóa): Recommendation engine
2. Infracost (Dùng để ước tính chi phí hạ tầng từ các file Terraform trước khi triển khai): Terraform cost analysis / cost guardrail
3. Cloud Custodian (Dùng để quản lý và tự động hóa các chính sách trên AWS, giúp đảm bảo tuân thủ các quy tắc xác định trước): Rule/policy engine + governance
4. AWS FinOps Agent dựa trên Amazon Bedrock (Dùng để quản lý chi phí AWS tích hợp AI, thực hiện các hành động dựa trên các quy tắc xác định trước)
5. AWS Price List Bulk API (Dùng để lấy dữ liệu giá của các dịch vụ AWS nhằm thực hiện các phép tính chi phí chính xác)

# Tóm tắt output của hệ thống 
```
detect bằng deterministic rule → Agent → sandbox → PR → human review, và không cho Agent tự sửa production

AWS infrastructure
      │
      │ Terraform
      ▼
┌───────────────────────┐
│ Hệ thống đang chạy ổn │
└───────────────────────┘
      │
      │ metrics / cost / config
      ▼
┌───────────────────────┐
│     FinOps Agent      │
└───────────────────────┘
      │
      ├── phát hiện lãng phí
      ├── tìm phương án tối ưu
      ├── đánh giá performance risk
      ├── đánh giá architecture dependency
      ├── sửa Terraform
      ├── terraform plan
      └── tạo Pull Request
                    │
                    ▼
              Human review
```
- Ưu tiên tuyệt đối:
  - Không được tiết kiệm tiền bằng cách làm hệ thống kém ổn định.
Tức là objective không phải:
- minimize(cost)
Mà gần hơn với:
```
minimize(cost)
subject to:
    availability >= required
    performance >= required
    reliability >= required
    architecture constraints satisfied
```

# Phân tích kĩ hơn các tool sẽ sử dụng
1. [AWS Compute Optimizer: Recommendation engine](https://aws.amazon.com/compute-optimizer/)
- [What is AWS Compute Optimizer?](https://docs.aws.amazon.com/compute-optimizer/latest/ug/what-is-compute-optimizer)
2. [Infracost: Terraform cost analysis / cost guardrail](https://www.infracost.io/)
- [What is Infracost?](https://www.infracost.io/docs/)
3. [Cloud Custodian: Rule/policy engine + governance](https://cloudcustodian.io/)
- [What is Cloud Custodian?](https://cloudcustodian.io/docs/)
4. [AWS FinOps Agent dựa trên Amazon Bedrock: AI-driven cost management and automation](https://aws.amazon.com/finops-agent/)
- [What is AWS FinOps Agent?](https://aws.amazon.com/finops-agent/)
5. [AWS Price List Bulk API: Accurate cost calculation](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-changes.html)
- [What is AWS Price List Bulk API?](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-changes.html)


# Ý tưởng kết tận dụng đã có để đảm bảo Output của hệ thống

```
                         AWS
                          │
          ┌───────────────┼────────────────┐
          │               │                │
       Metrics           Cost          Resources
          │               │                │
          ▼               ▼                ▼
   CloudWatch /      Cost Explorer      AWS APIs
   Compute Optimizer
          │
          ▼
┌──────────────────────────────┐
│       FINOPS AGENT           │
│                              │
│  Orchestrator / LLM          │
└──────────────┬───────────────┘
               │
      ┌────────┼──────────┐
      │        │          │
      ▼        ▼          ▼
 Compute    Custodian   Terraform
Optimizer    Policy       Repo
      │        │          │
      └────────┼──────────┘
               ▼
         Candidate change
               │
               ▼
        terraform plan
               │
               ▼
          Infracost
               │
       ┌───────┴────────┐
       ▼                ▼
 Cost reduction    Risk validation
       │                │
       └───────┬────────┘
               ▼
            Sandbox
               │
               ▼
        GitHub Pull Request
               │
               ▼
          Human Review
```

# Giải thích kiến trúc

## Vai trò của từng nguồn dữ liệu

Terraform mô tả **kiến trúc mong muốn**. Các dịch vụ AWS cung cấp bằng chứng về **hệ thống đang chạy thực tế**. Agent cần kết hợp các nguồn sau:

| Nguồn | Cung cấp | Giới hạn |
|---|---|---|
| Terraform code và state | Module, cấu hình mong muốn, ownership và dependency được khai báo | Có thể bị drift hoặc không bao gồm resource tạo ngoài Terraform |
| AWS Resource Inventory / Config | Resource đang tồn tại, tags, trạng thái, quan hệ và metadata | Không thay thế metrics, cost hoặc recommendation |
| CloudWatch | CPU, network, latency, error rate và các runtime metrics | Chỉ có dữ liệu cho metric đã được thu thập |
| Compute Optimizer | Recommendation về sizing và performance risk | Không hiểu đầy đủ business context và architecture dependency |
| Cost Explorer | Chi phí thực tế theo account, service, tag hoặc dimension | Không dự báo chính xác chi phí của Terraform change như Infracost |
| Cloud Custodian | Policy, guardrail và điều kiện được phép thay đổi | Không phải công cụ phân tích performance |
| Infracost | Cost estimate trước và sau thay đổi Terraform | Không phản ánh usage runtime thực tế |

Vì vậy, Agent không nhất thiết phải tự gọi trực tiếp mọi AWS Resource API. Tuy nhiên, hệ thống vẫn cần một nguồn **resource inventory** như AWS Config, Terraform refresh/plan hoặc inventory được đồng bộ trước đó để kiểm tra ownership, drift và dependency.

## Orchestration Decision Pipeline

Mục tiêu là xây dựng một **Orchestration decision pipeline có kiểm soát**, không phải một chatbot tự ý thay đổi production.

### Bước 1: Discovery

Agent thu thập:

- Terraform code và state
- Resource inventory
- CloudWatch metrics
- Compute Optimizer recommendations
- Cost Explorer data
- Các policy và guardrail

Ví dụ candidate được chuẩn hóa thành dữ liệu có cấu trúc:

```json
{
  "resource": "ec2-abc",
  "current_type": "m6i.2xlarge",
  "recommended_type": "m6i.xlarge",
  "monthly_saving": 390,
  "performance_risk": "low",
  "evidence": {
    "cloudwatch_window_days": 30,
    "terraform_managed": true,
    "recommendation_source": "compute_optimizer"
  }
}
```

### Bước 2: Context analysis

Agent đối chiếu candidate với kiến trúc và vận hành thực tế:

- Resource thuộc service và Terraform module nào?
- Có dependency với load balancer, database, queue hoặc service khác không?
- Resource có thuộc production hoặc workload critical không?
- Có Auto Scaling hoặc deployment constraint không?
- Có SLA, availability requirement hoặc performance baseline đặc biệt không?
- Cấu hình thực tế có drift so với Terraform state không?

Đây là phần Compute Optimizer không thể hiểu đầy đủ vì recommendation của nó chủ yếu dựa trên resource configuration và usage metrics.

### Bước 3: Policy check

Cloud Custodian hoặc policy engine quyết định candidate có được phép tiếp tục hay không:

```text
if environment == "production" and protected == true:
    REJECT
elif has_unresolved_drift or missing_required_tags:
    BLOCK_FOR_REVIEW
else:
    CONTINUE
```

Agent không được vượt qua policy bằng suy luận của LLM.

### Bước 4: Generate Terraform patch

Agent không gọi lệnh thay đổi trực tiếp vào production:

```bash
aws ec2 modify-instance-attribute ...
```

Thay vào đó, Agent tạo patch trong repository Terraform:

```hcl
# terraform/modules/api/main.tf
instance_type = "m6i.xlarge"
```

### Bước 5: Validate

CI hoặc sandbox chạy các kiểm tra bắt buộc:

```bash
terraform fmt -check
terraform validate
terraform plan
infracost breakdown
infracost diff
```

Nếu `terraform plan`, policy check hoặc validation thất bại, pipeline dừng và không tạo PR tự động.

### Bước 6: Safety decision

Agent chỉ được đề xuất PR khi có đủ bằng chứng:

```text
Cost:
    expected saving: -$390/month

Performance:
    risk: low
    evidence window: 30 days

Availability:
    no expected change

Terraform:
    plan: passed
    unexpected resource replacement: none

Policy:
    passed

Dependencies:
    no unresolved dependency detected
```

`low risk` từ Compute Optimizer chỉ là một input. Nó không tự động đồng nghĩa với `safe to change`.

### Bước 7: Create Pull Request

PR phải chứa đủ thông tin để human review:

```text
Title: FinOps Optimization #42

Change:
    m6i.2xlarge -> m6i.xlarge

Expected saving:
    $390/month

Performance risk:
    LOW

Terraform plan:
    PASSED

Policy:
    PASSED

Rollback:
    restore m6i.2xlarge

Status:
    WAITING FOR HUMAN APPROVAL
```

Agent chỉ tạo candidate change và Pull Request. Việc apply production vẫn cần quy trình phê duyệt của con người.


# Q&A
1. Tại sao lại cần AWS APIs khi đã có kiến trúc Terraform
- Phát hiện drift: cấu hình trên AWS có thể đã bị sửa ngoài Terraform.
- Tìm resource không do Terraform quản lý: tài nguyên tạo thủ công, module khác hoặc tài khoản khác.
- Lấy trạng thái runtime: CPU, network, instance health, autoscaling activity, attached resources. (sử dụng AWS CloudWatch và các API liên quan hỗ trợ bổ sung thêm thông tin chi tiết về trạng thái runtime)
- Đọc metadata AWS mà Terraform không phản ánh đầy đủ: tags thực tế, dependency, trạng thái service, region/account.
- Đối chiếu chi phí và sử dụng thực tế: Terraform biết instance type, nhưng không biết tài nguyên có đang nhàn rỗi hay traffic thấp.
- Kiểm tra resource đã bị xóa hoặc thay đổi nhưng state chưa cập nhật.