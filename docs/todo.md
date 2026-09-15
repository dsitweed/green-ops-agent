# Todo: Discovery v0.1 - EC2 rightsizing

## Mục tiêu và giới hạn

- [ ] Xác nhận phạm vi v0.1: chỉ discovery cho một workload EC2 nhỏ, chưa sửa Terraform, chưa tạo PR và chưa apply production.
- [ ] Chọn một AWS region và một account thử nghiệm riêng hoặc resource có thể hủy an toàn.
- [ ] Định nghĩa output chuẩn của Discovery: `resource`, `current_configuration`, `ownership`, `runtime_metrics`, `cost`, `recommendations`, `evidence`, `collected_at`, `errors`.
- [ ] Định nghĩa tiêu chí: agent chỉ thu thập và báo cáo dữ liệu; không tự kết luận "safe to change" nếu thiếu bằng chứng.

## 1. Chuẩn bị hệ thống AWS bằng Terraform

- [x] Tạo thư mục Terraform ở root, ví dụ `terraform/`, có provider AWS và biến `region`.
- [x] Tạo một EC2 instance nhỏ, dùng AMI hợp lệ theo region, gắn security group tối thiểu và SSM access method.
- [x] Gắn các tag nền tảng: `Name`, `Environment`, `Project`, `ManagedBy=terraform`.
- [x] Tạo IAM instance profile tối thiểu cho Systems Manager access.
- [x] Tạo metric alarm status-check tối thiểu cho EC2, không gắn notification destination.
- [x] Tách state/backend thử nghiệm khỏi production; không commit secret, state nhạy cảm hoặc key pair.
- [x] Chạy `terraform fmt`, `terraform validate`, `terraform plan` và ghi lại output baseline.
- [ ] Apply resource thử nghiệm, xác nhận instance đang chạy và lưu `instance_id`, `region`, `account_id`.
- [ ] Xác nhận Terraform state đọc được ownership và cấu hình hiện tại của EC2.

## 2. Tạo dữ liệu quan sát cho Discovery

- [ ] Bật hoặc xác nhận EC2 detailed monitoring và xác định cửa sổ quan sát, ví dụ 7 hoặc 14 ngày cho v0.1.
- [ ] Tạo dữ liệu CloudWatch tối thiểu: CPU utilization, network in/out, status check và metric liên quan workload.
- [ ] Gửi một log ứng dụng hoặc system log mẫu vào CloudWatch Logs nếu agent cần đọc log.
- [ ] Viết collector gọi AWS APIs ở chế độ read-only để lấy: EC2 metadata, tags, trạng thái, instance type, EBS attachment và networking cơ bản.
- [ ] Viết collector gọi CloudWatch APIs để lấy metric statistics theo cùng một time window; trả về dữ liệu có timestamp và đơn vị.
- [ ] Gọi Cost Explorer nếu account có dữ liệu chi phí đủ dùng; nếu chưa có, ghi rõ `cost_unavailable` thay vì tự bịa dữ liệu.
- [ ] Dùng LocalStack cho contract test hoặc fixture của EC2/CloudWatch collector khi phù hợp; không coi LocalStack là bằng chứng về chi phí AWS thật.
- [ ] Tạo fixture JSON cho trường hợp không có AWS thật, nhưng đánh dấu rõ `source=fixture`.

## 3. Xác định cách lấy Compute Optimizer

- [ ] Kiểm tra account/region có bật Compute Optimizer và identity có quyền read-only cần thiết hay chưa.
- [ ] Kiểm tra EC2 đã có đủ thời gian chạy và CloudWatch utilization history để Compute Optimizer có thể tạo recommendation.
- [ ] Thử gọi API recommendation cho EC2 và lưu raw response chỉ trong artifact thử nghiệm phù hợp.
- [ ] Nếu chưa có recommendation thật, tạo adapter interface và fixture recommendation có schema tương đương; đánh dấu `source=fixture`.
- [ ] Không dùng recommendation fixture để khẳng định mức tiết kiệm hoặc performance risk ngoài môi trường thử nghiệm.

## 4. Xây Discovery agent v0.1

- [ ] Chọn một entrypoint chạy một lần, ví dụ `discover`, nhận `region`, `instance_id` và time window.
- [ ] Implement các adapter riêng: Terraform state, EC2 APIs, CloudWatch metrics/logs, Cost Explorer và Compute Optimizer.
- [ ] Chuẩn hóa response của mọi adapter về schema chung; lỗi một nguồn phải xuất hiện trong `errors`, không bị nuốt.
- [ ] Ghép dữ liệu theo `account_id`, `region`, `resource_id` và thời điểm thu thập.
- [ ] Kiểm tra deterministic: cùng input và cùng snapshot dữ liệu phải tạo cùng output, không cần LLM để tính toán số liệu.
- [ ] Xuất một discovery report JSON và một report dễ đọc cho người review.
- [ ] Gắn provenance cho từng trường: API/fixture, query, time window và collected timestamp.
- [ ] Báo rõ dữ liệu thiếu, metric không có, resource drift hoặc recommendation chưa sẵn sàng.

## 5. Kiểm thử và tiêu chí hoàn thành Discovery

- [ ] Unit test parser/normalizer cho EC2, CloudWatch và Compute Optimizer response.
- [ ] Contract test với LocalStack hoặc fixture cho luồng collector không cần AWS thật.
- [ ] Integration test read-only với AWS thử nghiệm nếu có account phù hợp.
- [ ] Test trường hợp thiếu tag, không có metric, không có cost data và không có Compute Optimizer recommendation.
- [ ] Xác nhận agent không gọi API mutation như `modify-instance-attribute`, không chạy `terraform apply` và không thay đổi production.
- [ ] Chạy một lần end-to-end và lưu report mẫu có đủ resource, config, metrics, cost/reason, recommendation/reason và provenance.
- [ ] Discovery v0.1 hoàn thành khi report có thể trả lời: EC2 nào đang chạy, được Terraform quản lý không, cấu hình hiện tại là gì, runtime metrics ra sao, chi phí có lấy được không và recommendation đến từ nguồn nào.

## Quyết định kiến trúc cần giữ

- [ ] ECS chưa nằm trong v0.1 trừ khi cần để kiểm thử một dependency cụ thể; bắt đầu bằng EC2 rightsizing để giảm phạm vi.
- [ ] LocalStack là môi trường mô phỏng/contract test, không thay thế AWS thật cho Compute Optimizer và chi phí thực tế.
- [ ] AWS APIs ở bước Discovery chỉ dùng read-only; mọi thay đổi Terraform, plan, sandbox và PR để sau Discovery.
