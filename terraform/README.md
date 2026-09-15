# Terraform AWS setup

Terraform needs AWS credentials before it can refresh the AMI data source or
create a plan. Credentials must be configured outside this repository.

## Use an AWS CLI profile

Configure a profile once:

```bash
aws configure --profile default
```

Verify it before running Terraform:

```bash
aws sts get-caller-identity --profile default
```

Then run:

```bash
AWS_EC2_METADATA_DISABLED=true terraform plan
```

The profile name is selected in `terraform.tfvars` with `aws_profile`. Change
`default` to the name of an existing profile when needed.

## Use environment credentials instead

Leave `aws_profile` empty and export credentials in the shell:

```bash
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_SESSION_TOKEN="..." # only for temporary credentials
AWS_EC2_METADATA_DISABLED=true terraform plan
```

Never commit access keys or session tokens to `terraform.tfvars`.
# Làm việc với terraform
```bash
terraform init # Khởi tạo terraform
terraform fmt # Định dạng lại các file terraform (format code)
terraform validate # Kiểm tra cấu hình terraform
terraform plan # Xem trước các thay đổi sẽ được áp dụng
terraform apply # Áp dụng các thay đổi
```

# Làm việc với aws cli
```bash
aws s3 ls # Liệt kê các bucket S3
aws ec2 describe-instances # Liệt kê các instance EC2
aws ec2 describe-images \
    --filters "Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*" "Name=state,Values=available" \
    --query "sort_by(Images, &CreationDate)[-1].ImageId" \
    --region ap-northeast-1  \
    --output text
```