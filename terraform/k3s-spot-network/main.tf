terraform {
  required_version = ">= 1.5"

  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  name_prefix = "${var.cluster_name}-${var.network_name}"
  selected_azs = slice(
    data.aws_availability_zones.available.names,
    0,
    min(var.public_subnet_count, length(data.aws_availability_zones.available.names)),
  )
  public_subnets = {
    for index, az in local.selected_azs : az => {
      cidr_block = cidrsubnet(var.vpc_cidr, 8, index + 1)
      az         = az
    }
  }
  common_tags = merge(
    {
      Name               = local.name_prefix
      managed_by         = "terraform"
      kubernetes_cluster = var.cluster_name
      network_tier       = "public-only"
    },
    var.tags,
  )
}

resource "aws_vpc" "spot_network" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(local.common_tags, {
    Name = local.name_prefix
  })
}

resource "aws_internet_gateway" "spot_network" {
  vpc_id = aws_vpc.spot_network.id

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-igw"
  })
}

resource "aws_subnet" "public" {
  for_each = local.public_subnets

  vpc_id                  = aws_vpc.spot_network.id
  availability_zone       = each.value.az
  cidr_block              = each.value.cidr_block
  map_public_ip_on_launch = true

  tags = merge(local.common_tags, {
    Name                     = "${local.name_prefix}-${replace(each.key, var.aws_region, "")}"
    "kubernetes.io/role/elb" = "1"
  })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.spot_network.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.spot_network.id
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-public-rt"
  })
}

resource "aws_route_table_association" "public" {
  for_each = aws_subnet.public

  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}
