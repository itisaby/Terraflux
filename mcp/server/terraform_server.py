"""
Terraform MCP Server
Handles infrastructure provisioning through Terraform
"""
import json
import subprocess
import tempfile
import os
import re
from pathlib import Path
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
            
            # Get user credentials and set environment securely
            credentials = await get_user_credentials(user_id)

            # Create temporary credentials file instead of using environment variables
            creds_file_path = await self._create_secure_credentials_file(workspace_path, credentials, region)

            try:
                # Set environment to use credentials file
                env_vars = os.environ.copy()
                env_vars['AWS_SHARED_CREDENTIALS_FILE'] = creds_file_path
                env_vars['AWS_REGION'] = region

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
                    'resources': resources,
                    'credentials_file': creds_file_path
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

            finally:
                # Always clean up credentials file after planning
                await self._cleanup_credentials_file(creds_file_path)

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
            
            # Get credentials and create secure file
            credentials = await get_user_credentials(user_id)
            creds_file_path = await self._create_secure_credentials_file(
                plan_info['workspace_path'],
                credentials,
                credentials.get('region', 'us-east-1')
            )

            try:
                env_vars = os.environ.copy()
                env_vars['AWS_SHARED_CREDENTIALS_FILE'] = creds_file_path

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

            finally:
                # Always clean up credentials file
                await self._cleanup_credentials_file(creds_file_path)
            
        except Exception as e:
            logging.error(f"Error in apply_infrastructure: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _create_workspace(self, user_id: str, environment: str) -> str:
        """
        Create or get user workspace directory with proper security validation

        Args:
            user_id: User ID (must be valid UUID format)
            environment: Environment name (must be dev, staging, or prod)

        Returns:
            Validated workspace path

        Raises:
            ValueError: If inputs are invalid or path traversal is detected
        """
        # Validate user_id format (UUID)
        if not re.match(r'^[a-f0-9\-]{36}$', user_id):
            raise ValueError(f"Invalid user_id format: {user_id}")

        # Validate environment
        if environment not in ['dev', 'staging', 'prod']:
            raise ValueError(f"Invalid environment: {environment}. Must be dev, staging, or prod")

        # Create workspace path
        workspace_base = Path(self.workspace_dir).resolve()
        workspace_path = workspace_base / f"user-{user_id}" / environment

        # Ensure the path is within the expected workspace directory
        if not str(workspace_path.resolve()).startswith(str(workspace_base)):
            raise ValueError("Invalid workspace path - potential path traversal attack detected")

        # Create directory with restricted permissions
        workspace_path.mkdir(parents=True, exist_ok=True, mode=0o750)

        # Ensure correct permissions
        os.chmod(workspace_path, 0o750)  # rwxr-x---

        logging.info(f"Created/verified workspace: {workspace_path}")
        return str(workspace_path)
    
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
        """
        Run terraform command with security validation

        Args:
            cmd: Terraform command arguments (validated)
            cwd: Working directory (must be validated workspace path)
            env: Environment variables

        Returns:
            Command output

        Raises:
            ValueError: If path validation fails
            Exception: If terraform command fails
        """
        # Validate workspace path
        workspace_path = Path(cwd).resolve()
        expected_base = Path(self.workspace_dir).resolve()

        # Ensure path is within workspace directory
        try:
            workspace_path.relative_to(expected_base)
        except ValueError:
            raise ValueError(f"Invalid workspace path - potential path traversal attack: {cwd}")

        if not workspace_path.exists():
            raise ValueError(f"Workspace path does not exist: {cwd}")

        # Validate command arguments to prevent injection
        allowed_commands = ['init', 'plan', 'apply', 'destroy', 'output', 'show', 'validate']
        if cmd and cmd[0] not in allowed_commands:
            raise ValueError(f"Terraform command not allowed: {cmd[0]}")

        full_cmd = ['terraform'] + cmd

        logging.info(f"Executing terraform command: {' '.join(full_cmd)} in {cwd}")

        try:
            process = subprocess.run(
                full_cmd,
                cwd=str(workspace_path),
                env=env,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if process.returncode != 0:
                logging.error(f"Terraform command failed: {process.stderr}")
                raise Exception(f"Terraform command failed: {process.stderr}")

            return process.stdout

        except subprocess.TimeoutExpired:
            logging.error(f"Terraform command timed out after 300 seconds")
            raise Exception("Terraform command timed out after 5 minutes")
    
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

    async def _create_secure_credentials_file(self, workspace_path: str, credentials: Dict[str, Any], region: str) -> str:
        """
        Create a secure temporary credentials file with restricted permissions

        Args:
            workspace_path: Workspace directory path
            credentials: AWS credentials dictionary
            region: AWS region

        Returns:
            Path to the created credentials file
        """
        import configparser

        # Create credentials file in workspace
        creds_file_path = os.path.join(workspace_path, f".aws_credentials_{uuid.uuid4().hex}")

        # Write credentials in AWS credentials file format
        config = configparser.ConfigParser()
        config['default'] = {
            'aws_access_key_id': credentials.get('aws_access_key', ''),
            'aws_secret_access_key': credentials.get('aws_secret_key', ''),
            'region': region
        }

        # Create file with restrictive permissions (owner read/write only)
        os.umask(0o077)
        with open(creds_file_path, 'w') as f:
            config.write(f)

        # Ensure restrictive permissions
        os.chmod(creds_file_path, 0o600)

        logging.info(f"Created secure credentials file: {creds_file_path}")
        return creds_file_path

    async def _cleanup_credentials_file(self, creds_file_path: str):
        """
        Securely delete credentials file

        Args:
            creds_file_path: Path to credentials file to delete
        """
        try:
            if os.path.exists(creds_file_path):
                # Overwrite file with random data before deletion (extra security)
                with open(creds_file_path, 'wb') as f:
                    f.write(os.urandom(1024))

                # Delete the file
                os.unlink(creds_file_path)
                logging.info(f"Cleaned up credentials file: {creds_file_path}")
        except Exception as e:
            logging.error(f"Error cleaning up credentials file: {e}")

    async def _get_plan_json(self, workspace_path: str, plan_file: str, env: Dict[str, str]) -> Dict[str, Any]:
        """
        Get Terraform plan as JSON

        Args:
            workspace_path: Workspace directory
            plan_file: Plan file name
            env: Environment variables

        Returns:
            Plan JSON dictionary
        """
        try:
            # Run terraform show to get JSON
            result = await self._run_terraform_command(
                ['show', '-json', plan_file],
                workspace_path,
                env
            )
            return json.loads(result) if result else {}
        except Exception as e:
            logging.warning(f"Could not parse plan JSON: {e}")
            return {}

    async def _get_terraform_outputs(self, workspace_path: str, env: Dict[str, str]) -> Dict[str, Any]:
        """
        Get Terraform outputs

        Args:
            workspace_path: Workspace directory
            env: Environment variables

        Returns:
            Outputs dictionary
        """
        try:
            result = await self._run_terraform_command(
                ['output', '-json'],
                workspace_path,
                env
            )
            return json.loads(result) if result else {}
        except Exception as e:
            logging.warning(f"Could not get terraform outputs: {e}")
            return {}

    def _count_resources(self, plan_json: Dict, action: str) -> int:
        """
        Count resources in plan by action type

        Args:
            plan_json: Terraform plan JSON
            action: Action type ('create', 'update', 'delete')

        Returns:
            Count of resources
        """
        try:
            if not plan_json or 'resource_changes' not in plan_json:
                return 0

            count = 0
            for resource in plan_json.get('resource_changes', []):
                actions = resource.get('change', {}).get('actions', [])
                if action in actions:
                    count += 1

            return count
        except Exception as e:
            logging.warning(f"Error counting resources: {e}")
            return 0