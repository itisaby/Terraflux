# EC2 Instance
data "aws_ami" "{{ resource_name }}_ami" {
  most_recent = true
  owners      = ["099720109477"] # Canonical (Ubuntu)

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-20.04-amd64-server-*"]
  }
}

resource "aws_instance" "{{ resource_name }}" {
  ami           = data.aws_ami.{{ resource_name }}_ami.id
  instance_type = "{{ config.instance_type }}"

  vpc_security_group_ids = [aws_security_group.{{ resource_name }}_sg.id]

  tags = {
    Name        = "{{ resource_name }}-{{ environment }}"
    Environment = "{{ environment }}"
    ManagedBy   = "InfraAgent"
  }

  user_data = <<-EOF
    #!/bin/bash
    apt update
    apt install -y nginx
    systemctl start nginx
    systemctl enable nginx
  EOF
}

resource "aws_security_group" "{{ resource_name }}_sg" {
  name = "{{ resource_name }}-sg-{{ environment }}"

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

output "{{ resource_name }}_public_ip" {
  value = aws_instance.{{ resource_name }}.public_ip
}

output "{{ resource_name }}_instance_id" {
  value = aws_instance.{{ resource_name }}.id
}