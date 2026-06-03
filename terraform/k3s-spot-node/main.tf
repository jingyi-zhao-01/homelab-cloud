terraform {
  required_version = ">= 1.5"

  # Partial configuration — bucket/key/region are passed via -backend-config at init time.
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

data "aws_ssm_parameter" "ubuntu_ami" {
  name = var.ami_ssm_parameter
}

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "asg_tag_access" {
  statement {
    sid = "AllowDescribeOwnTags"

    actions = [
      "ec2:DescribeInstances",
      "ec2:DescribeTags",
    ]

    resources = ["*"]
  }
}

locals {
  name_prefix = "${var.cluster_name}-${var.node_group_name}"
  common_tags = merge(
    {
      Name               = local.name_prefix
      managed_by         = "terraform"
      kubernetes_cluster = var.cluster_name
    },
    {
      ("kubernetes.io/cluster/${var.cluster_name}") = "owned"
    },
    var.tags,
  )

  user_data = templatefile("${path.module}/user-data.sh.tftpl", {
    cluster_name   = var.cluster_name
    k3s_server_url = var.k3s_server_url
    k3s_token      = var.k3s_token
    node_labels    = join(",", var.node_labels)
    node_taints    = join(",", var.node_taints)
    extra_k3s_args = var.extra_k3s_agent_args
  })
}

resource "aws_security_group" "spot_node" {
  name_prefix = "${local.name_prefix}-"
  description = "Security group for ${local.name_prefix} spot k3s node"
  vpc_id      = var.vpc_id

  dynamic "ingress" {
    for_each = var.allowed_ssh_cidrs

    content {
      description = "SSH access"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

resource "aws_iam_role" "spot_node" {
  name_prefix        = "${local.name_prefix}-"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.spot_node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "asg_tag_access" {
  name_prefix = "${local.name_prefix}-"
  role        = aws_iam_role.spot_node.id
  policy      = data.aws_iam_policy_document.asg_tag_access.json
}

resource "aws_iam_instance_profile" "spot_node" {
  name_prefix = "${local.name_prefix}-"
  role        = aws_iam_role.spot_node.name
  tags        = local.common_tags
}

resource "aws_launch_template" "spot_node" {
  name_prefix   = "${local.name_prefix}-"
  image_id      = data.aws_ssm_parameter.ubuntu_ami.value
  instance_type = var.instance_types[0]
  key_name      = var.key_name

  update_default_version = true

  iam_instance_profile {
    arn = aws_iam_instance_profile.spot_node.arn
  }

  instance_market_options {
    market_type = "spot"

    spot_options {
      instance_interruption_behavior = "terminate"
      spot_instance_type             = "one-time"
    }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_put_response_hop_limit = 2
    http_tokens                 = "required"
  }

  monitoring {
    enabled = true
  }

  network_interfaces {
    associate_public_ip_address = var.associate_public_ip_address
    delete_on_termination       = true
    security_groups             = [aws_security_group.spot_node.id]
  }

  user_data = base64encode(local.user_data)

  tag_specifications {
    resource_type = "instance"
    tags = merge(local.common_tags, {
      lifecycle = "spot"
      role      = "k3s-agent"
    })
  }

  tag_specifications {
    resource_type = "volume"
    tags          = local.common_tags
  }

  tags = local.common_tags
}

resource "aws_autoscaling_group" "spot_node" {
  name                      = local.name_prefix
  desired_capacity          = 1
  min_size                  = 1
  max_size                  = 1
  health_check_type         = "EC2"
  health_check_grace_period = 300
  vpc_zone_identifier       = var.subnet_ids
  default_cooldown          = 30
  force_delete              = false
  termination_policies      = ["OldestLaunchTemplate", "ClosestToNextInstanceHour"]

  mixed_instances_policy {
    instances_distribution {
      on_demand_base_capacity                  = 0
      on_demand_percentage_above_base_capacity = 0
      spot_allocation_strategy                 = "price-capacity-optimized"
    }

    launch_template {
      launch_template_specification {
        launch_template_id = aws_launch_template.spot_node.id
        version            = aws_launch_template.spot_node.latest_version
      }

      dynamic "override" {
        for_each = var.instance_types

        content {
          instance_type = override.value
        }
      }
    }
  }

  tag {
    key                 = "Name"
    value               = local.name_prefix
    propagate_at_launch = true
  }

  tag {
    key                 = "k8s.io/cluster-autoscaler/enabled"
    value               = "false"
    propagate_at_launch = true
  }

  dynamic "tag" {
    for_each = local.common_tags

    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }

  instance_refresh {
    strategy = "Rolling"

    preferences {
      min_healthy_percentage = 0
    }
  }
}
