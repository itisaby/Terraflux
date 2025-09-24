"""
Terraform MCP Server
Handles infrastructure provisioning through Terraform
"""
import json
import subprocess
import tempfile
import os
from typing import Dict, Any, List
from jinja2 import Template, FileSystemLoader, Environment
from security.credentials import get_user_credentials
import uuid
import logging

class TerraformMCPServer:
    def __init__(self):
        self.template_dir = "mcp/server/templates"
        self.workspace_dir = "terraform/workspaces"
        self.jinja_env = Environment(loader=FileSystemLoader(self.template_dir))
        self.active_plans = {}
        
    async def plan_infrastructure(self, resources: List[Dict], region: str, environment: str, user_id: str) -> Dict[str, Any]:
        """Generate Terraform plan for requested resources"""
        try:
            # Create user workspace
            workspace_path = await self._create_workspace(user_id, environment)
            
            # Generate Terraform configuration
            tf_config = await self._generate_terraform_config(resources, region, environment)
            
            # Write configuration to workspace
            config_path = os.path.join(workspace_path, "main.tf")
            with open(config_path, 'w') as f:
                f.write(tf_config)
            
            # Get user credentials and set environment
            credentials = await get_user_credentials(user_id)
            env_vars = os.environ.copy()
            env_vars.update({
                'AWS_ACCESS_KEY_ID': credentials['aws_access_key'],
                'AWS_SECRET_ACCESS_KEY': credentials['aws_secret_key'],
                'AWS_REGION': region
            })
            
            # Initialize Terraform
            await self._run_terraform_command(['init'], workspace_path, env_vars)
            
            # Generate plan
            plan_file = f"plan-{uuid.uuid4().hex}.tfplan"
            plan_path = os.path.join(workspace_path, plan_file)
            
            result = await self._run_terraform_command(
                ['plan', '-out', plan_file, '-detailed-exitcode'],
                workspace_path,
                env_vars
            )
            
            # Parse plan output
            plan_json = await self._get_plan_json(workspace_path, plan_file, env_vars)
            
            plan_id = str(uuid.uuid4())
            self.active_plans[plan_id] = {
                'workspace_path': workspace_path,
                'plan_file': plan_path,
                'user_id': user_id,
                'resources': resources
            }
            
            return {
                'success': True,
                'plan': {
                    'id': plan_id,
                    'resources_to_create': self._count_resources(plan_json, 'create'),
                    'estimated_cost': await self._estimate_cost(plan_json),
                    'summary': self._generate_plan_summary(plan_json)
                }
            }
            
        except Exception as e:
            logging.error(f"Error in plan_infrastructure: {e}")
            return {'success': False, 'error': str(e)}
    
    async def apply_infrastructure(self, plan_id: str, user_id: str) -> Dict[str, Any]:
        """Apply the Terraform plan"""
        try:
            if plan_id not in self.active_plans:
                return {'success': False, 'error': 'Plan not found'}
            
            plan_info = self.active_plans[plan_id]
            
            if plan_info['user_id'] != user_id:
                return {'success': False, 'error': 'Unauthorized'}
            
            # Get credentials
            credentials = await get_user_credentials(user_id)
            env_vars = os.environ.copy()
            env_vars.update({
                'AWS_ACCESS_KEY_ID': credentials['aws_access_key'],
                'AWS_SECRET_ACCESS_KEY': credentials['aws_secret_key']
            })
            
            # Apply the plan
            result = await self._run_terraform_command(
                ['apply', os.path.basename(plan_info['plan_file'])],
                plan_info['workspace_path'],
                env_vars
            )
            
            # Get outputs
            outputs = await self._get_terraform_outputs(plan_info['workspace_path'], env_vars)
            
            # Clean up plan
            del self.active_plans[plan_id]
            
            return {
                'success': True,
                'outputs': outputs,
                'message': 'Infrastructure provisioned successfully'
            }
            
        except Exception as e:
            logging.error(f"Error in apply_infrastructure: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _create_workspace(self, user_id: str, environment: str) -> str:
        """Create or get user workspace directory"""
        workspace_path = os.path.join(self.workspace_dir, f"user-{user_id}", environment)
        os.makedirs(workspace_path, exist_ok=True)
        return workspace_path
    
    async def _generate_terraform_config(self, resources: List[Dict], region: str, environment: str) -> str:
        """Generate Terraform configuration from resource definitions"""
        config_parts = [
            # Provider configuration
            f'''
terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  region = "{region}"
}}
'''
        ]
        
        # Generate resource configurations
        for i, resource in enumerate(resources):
            template_name = self._get_template_name(resource['type'])
            template = self.jinja_env.get_template(template_name)
            
            resource_config = template.render(
                resource_name=f"{resource['type']}_{i}",
                config=resource['config'],
                environment=environment,
                index=i
            )
            config_parts.append(resource_config)
        
        return '\n'.join(config_parts)
    
    def _get_template_name(self, resource_type: str) -> str:
        """Map resource type to template file"""
        template_map = {
            'aws_instance': 'aws/ec2.tf.j2',
            'aws_db_instance': 'aws/rds.tf.j2',
            'aws_s3_bucket': 'aws/s3.tf.j2',
            'aws_lb': 'aws/alb.tf.j2'
        }
        return template_map.get(resource_type, 'aws/ec2.tf.j2')
    
    async def _run_terraform_command(self, cmd: List[str], cwd: str, env: Dict[str, str]) -> str:
        """Run terraform command and return output"""
        full_cmd = ['terraform'] + cmd
        
        process = subprocess.run(
            full_cmd,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if process.returncode != 0:
            raise Exception(f"Terraform command failed: {process.stderr}")
        
        return process.stdout
    
    async def _estimate_cost(self, plan_json: Dict) -> float:
        """Estimate monthly cost of resources (simplified)"""
        # This is a simplified cost estimation
        # In production, you'd integrate with AWS Cost Explorer API
        
        cost_estimates = {
            'aws_instance': {'t3.micro': 10.0, 't3.small': 20.0, 't3.medium': 40.0},
            'aws_db_instance': {'db.t3.micro': 15.0, 'db.t3.small': 30.0},
            'aws_s3_bucket': 5.0,  # Base cost
            'aws_lb': 25.0  # Application Load Balancer
        }
        
        total_cost = 0.0
        
        # This would parse the actual plan JSON in production
        # For now, return a placeholder
        return total_cost or 50.0  # Placeholder cost
    
    def _generate_plan_summary(self, plan_json: Dict) -> str:
        """Generate human-readable plan summary"""
        return "Plan will create infrastructure resources as requested."