output "autoscaling_group_name" {
  description = "Name of the Auto Scaling Group maintaining the single spot worker"
  value       = aws_autoscaling_group.spot_node.name
}

output "launch_template_id" {
  description = "Launch template used by the spot worker Auto Scaling Group"
  value       = aws_launch_template.spot_node.id
}

output "security_group_id" {
  description = "Security group attached to the spot worker"
  value       = aws_security_group.spot_node.id
}

output "instance_profile_name" {
  description = "IAM instance profile attached to the spot worker"
  value       = aws_iam_instance_profile.spot_node.name
}
