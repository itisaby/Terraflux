"""
Natural Language Intent Parser
Converts user messages into structured infrastructure requests
"""
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

class Action(Enum):
    PROVISION = "provision"
    LIST = "list"
    DESTROY = "destroy"
    MODIFY = "modify"
    STATUS = "status"

@dataclass
class ParsedIntent:
    action: Action
    resources: List[Dict[str, Any]]
    region: Optional[str] = None
    environment: Optional[str] = None
    filters: Optional[Dict[str, str]] = None

class IntentParser:
    def __init__(self):
        self.resource_patterns = {
            r'(?i)(vm|virtual machine|ec2|instance)': {
                'type': 'aws_instance',
                'default_config': {
                    'instance_type': 't3.micro',
                    'ami': 'ubuntu-20.04'
                }
            },
            r'(?i)(database|db|rds|mysql|postgres)': {
                'type': 'aws_db_instance',
                'default_config': {
                    'engine': 'mysql',
                    'instance_class': 'db.t3.micro'
                }
            },
            r'(?i)(bucket|s3|storage)': {
                'type': 'aws_s3_bucket',
                'default_config': {
                    'versioning': True
                }
            },
            r'(?i)(load balancer|lb|alb)': {
                'type': 'aws_lb',
                'default_config': {
                    'load_balancer_type': 'application'
                }
            }
        }
        
        self.action_patterns = {
            r'(?i)(create|provision|deploy|setup|spin up|launch)': Action.PROVISION,
            r'(?i)(list|show|display|what do i have)': Action.LIST,
            r'(?i)(destroy|delete|remove|terminate|tear down)': Action.DESTROY,
            r'(?i)(modify|update|change|scale)': Action.MODIFY,
            r'(?i)(status|health|check)': Action.STATUS
        }
        
        self.region_patterns = {
            r'(?i)us-east-1|virginia|n\.?virginia': 'us-east-1',
            r'(?i)us-west-2|oregon': 'us-west-2',
            r'(?i)eu-west-1|ireland': 'eu-west-1',
            r'(?i)ap-southeast-1|singapore': 'ap-southeast-1'
        }
    
    async def parse(self, message: str) -> ParsedIntent:
        """Parse user message into structured intent"""
        
        # Detect action
        action = self._extract_action(message)
        
        # Extract resources
        resources = self._extract_resources(message)
        
        # Extract region
        region = self._extract_region(message)
        
        # Extract environment hints
        environment = self._extract_environment(message)
        
        return ParsedIntent(
            action=action,
            resources=resources,
            region=region,
            environment=environment
        )
    
    def _extract_action(self, message: str) -> Action:
        """Extract the intended action from the message"""
        for pattern, action in self.action_patterns.items():
            if re.search(pattern, message):
                return action
        
        # Default to provision if resources are mentioned
        if self._extract_resources(message):
            return Action.PROVISION
        
        return Action.STATUS  # Default fallback
    
    def _extract_resources(self, message: str) -> List[Dict[str, Any]]:
        """Extract infrastructure resources from the message"""
        resources = []
        
        for pattern, resource_info in self.resource_patterns.items():
            if re.search(pattern, message):
                resource = {
                    'type': resource_info['type'],
                    'config': resource_info['default_config'].copy()
                }
                
                # Extract specific configurations
                resource['config'].update(self._extract_resource_config(message, resource_info['type']))
                resources.append(resource)
        
        return resources
    
    def _extract_resource_config(self, message: str, resource_type: str) -> Dict[str, Any]:
        """Extract specific configuration for a resource type"""
        config = {}
        
        if resource_type == 'aws_instance':
            # Extract instance type
            instance_match = re.search(r'(?i)(t3\.|t2\.|m5\.|c5\.)\w+', message)
            if instance_match:
                config['instance_type'] = instance_match.group()
        
        elif resource_type == 'aws_db_instance':
            # Extract database engine
            if re.search(r'(?i)postgres', message):
                config['engine'] = 'postgres'
            elif re.search(r'(?i)mysql', message):
                config['engine'] = 'mysql'
        
        return config
    
    def _extract_region(self, message: str) -> Optional[str]:
        """Extract AWS region from message"""
        for pattern, region in self.region_patterns.items():
            if re.search(pattern, message):
                return region
        return None
    
    def _extract_environment(self, message: str) -> Optional[str]:
        """Extract environment (dev/staging/prod) from message"""
        if re.search(r'(?i)(prod|production)', message):
            return 'prod'
        elif re.search(r'(?i)(staging|stage)', message):
            return 'staging'
        elif re.search(r'(?i)(dev|development)', message):
            return 'dev'
        return 'dev'  # Default