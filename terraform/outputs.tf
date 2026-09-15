output "ec2_instance_id" {
  value = aws_instance.ec2.id
}

output "aws_region" {
  value = var.aws_region
}

output "aws_account_id" {
  value = data.aws_caller_identity.current.account_id
}

output "vpc_id" {
  value = data.aws_vpc.current.id
}

output "subnet_id" {
  value = aws_instance.ec2.subnet_id
}

output "security_group_id" {
  value = aws_security_group.ec2.id
}
