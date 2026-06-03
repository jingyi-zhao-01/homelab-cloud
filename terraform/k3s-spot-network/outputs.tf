output "vpc_id" {
  description = "VPC created for the low-cost spot worker network"
  value       = aws_vpc.spot_network.id
}

output "public_subnet_ids" {
  description = "Public subnet IDs that the spot worker Auto Scaling Group can use"
  value       = [for subnet in aws_subnet.public : subnet.id]
}

output "availability_zones" {
  description = "Availability zones used by the public subnets"
  value       = [for subnet in aws_subnet.public : subnet.availability_zone]
}

output "internet_gateway_id" {
  description = "Internet gateway attached to the VPC"
  value       = aws_internet_gateway.spot_network.id
}
