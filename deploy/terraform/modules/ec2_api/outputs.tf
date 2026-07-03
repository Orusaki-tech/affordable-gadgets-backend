output "instance_id" {
  value = aws_instance.api.id
}

output "private_ip" {
  value = aws_instance.api.private_ip
}

output "public_ip" {
  value = aws_instance.api.public_ip
}
