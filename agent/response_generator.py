"""
Response Generator
Converts technical infrastructure plans and results into human-readable responses
"""
from typing import Dict, Any, List
import json

class ResponseGenerator:
    """Generate user-friendly responses for infrastructure operations"""

    def generate_plan_response(self, plan: Dict[str, Any], resources: List[Dict]) -> str:
        """
        Generate human-readable response for infrastructure plan

        Args:
            plan: Terraform plan summary
            resources: List of requested resources

        Returns:
            Human-readable response string
        """
        response_parts = []

        # Header
        response_parts.append("I'll provision the following infrastructure:\n")

        # List resources
        for i, resource in enumerate(resources, 1):
            resource_desc = self._describe_resource(resource)
            response_parts.append(f"{i}. {resource_desc}")

        # Add plan summary
        if plan.get('resources_to_create', 0) > 0:
            response_parts.append(
                f"\nThis will create {plan['resources_to_create']} resource(s)."
            )

        # Add cost estimate
        estimated_cost = plan.get('estimated_cost', 0)
        if estimated_cost:
            response_parts.append(
                f"Estimated monthly cost: ${estimated_cost:.2f}"
            )

        # Confirmation prompt
        response_parts.append("\nShould I proceed with provisioning?")

        return "\n".join(response_parts)

    def generate_success_response(self, outputs: Dict[str, Any], resources: List[Dict]) -> str:
        """
        Generate success response after infrastructure is provisioned

        Args:
            outputs: Terraform outputs
            resources: Resources that were created

        Returns:
            Success message with resource details
        """
        response_parts = ["✅ Infrastructure provisioned successfully!\n"]

        # Group outputs by resource
        for resource in resources:
            resource_type = resource['type']
            resource_outputs = self._extract_resource_outputs(outputs, resource_type)

            if resource_outputs:
                response_parts.append(self._format_resource_outputs(resource_type, resource_outputs))

        return "\n".join(response_parts)

    def generate_error_response(self, error: str) -> str:
        """
        Generate user-friendly error response

        Args:
            error: Technical error message

        Returns:
            User-friendly error message
        """
        # Map common errors to user-friendly messages
        error_mappings = {
            "InvalidAccessKeyId": "❌ Invalid AWS credentials. Please check your access key.",
            "UnauthorizedOperation": "❌ Insufficient permissions. Please check your AWS IAM permissions.",
            "ResourceNotFound": "❌ Resource not found. It may have been deleted.",
            "QuotaExceeded": "❌ AWS quota exceeded. Please request a quota increase.",
            "ValidationError": "❌ Invalid configuration. Please check your request.",
            "terraform": "❌ Infrastructure deployment failed.",
        }

        # Check for known error patterns
        for pattern, friendly_msg in error_mappings.items():
            if pattern.lower() in error.lower():
                return f"{friendly_msg}\n\nTechnical details: {error}"

        # Generic error message
        return f"❌ An error occurred: {error}"

    def generate_list_response(self, resources: List[Dict]) -> str:
        """
        Generate response listing current infrastructure

        Args:
            resources: List of resource dictionaries

        Returns:
            Formatted list of resources
        """
        if not resources:
            return "You don't have any active infrastructure resources."

        response_parts = ["📋 Your active infrastructure:\n"]

        # Group by type
        by_type = {}
        for resource in resources:
            resource_type = resource.get('resource_type', 'unknown')
            if resource_type not in by_type:
                by_type[resource_type] = []
            by_type[resource_type].append(resource)

        # Format by type
        for resource_type, items in by_type.items():
            friendly_type = self._get_friendly_resource_type(resource_type)
            response_parts.append(f"\n**{friendly_type}** ({len(items)})")

            for item in items:
                details = self._format_resource_details(item)
                response_parts.append(f"  • {details}")

        # Add total cost if available
        total_cost = sum(r.get('estimated_monthly_cost', 0) for r in resources)
        if total_cost > 0:
            response_parts.append(f"\n💰 Total estimated monthly cost: ${total_cost:.2f}")

        return "\n".join(response_parts)

    def generate_destroy_confirmation(self, resources: List[Dict]) -> str:
        """
        Generate confirmation message for destroy operation

        Args:
            resources: Resources to be destroyed

        Returns:
            Confirmation message
        """
        response_parts = ["⚠️  You are about to destroy the following resources:\n"]

        for i, resource in enumerate(resources, 1):
            resource_type = self._get_friendly_resource_type(resource.get('type', 'unknown'))
            resource_id = resource.get('id', 'unknown')
            response_parts.append(f"{i}. {resource_type}: {resource_id}")

        response_parts.append("\n⚠️  This action cannot be undone!")
        response_parts.append("\nType 'yes' to confirm destruction.")

        return "\n".join(response_parts)

    def generate_cost_breakdown(self, resources: List[Dict]) -> str:
        """
        Generate detailed cost breakdown

        Args:
            resources: List of resources with cost info

        Returns:
            Formatted cost breakdown
        """
        if not resources:
            return "No resources to calculate costs for."

        response_parts = ["💰 Cost Breakdown:\n"]

        total_cost = 0
        for resource in resources:
            resource_type = self._get_friendly_resource_type(resource.get('type', 'unknown'))
            cost = resource.get('estimated_monthly_cost', 0)
            config = resource.get('config', {})

            # Add resource-specific details
            if resource.get('type') == 'aws_instance':
                instance_type = config.get('instance_type', 'unknown')
                response_parts.append(f"  • {resource_type} ({instance_type}): ${cost:.2f}/month")
            elif resource.get('type') == 'aws_db_instance':
                engine = config.get('engine', 'unknown')
                instance_class = config.get('instance_class', 'unknown')
                response_parts.append(
                    f"  • {resource_type} ({engine}, {instance_class}): ${cost:.2f}/month"
                )
            else:
                response_parts.append(f"  • {resource_type}: ${cost:.2f}/month")

            total_cost += cost

        response_parts.append(f"\n**Total: ${total_cost:.2f}/month**")
        response_parts.append(f"Annual estimate: ${total_cost * 12:.2f}/year")

        return "\n".join(response_parts)

    def _describe_resource(self, resource: Dict) -> str:
        """Generate human-readable description of a resource"""
        resource_type = resource['type']
        config = resource.get('config', {})

        descriptions = {
            'aws_instance': lambda c: f"EC2 Instance ({c.get('instance_type', 't3.micro')})",
            'aws_db_instance': lambda c: f"{c.get('engine', 'MySQL').upper()} Database ({c.get('instance_class', 'db.t3.micro')})",
            'aws_s3_bucket': lambda c: f"S3 Bucket (versioning: {c.get('versioning', True)})",
            'aws_lb': lambda c: f"{c.get('load_balancer_type', 'application').title()} Load Balancer",
        }

        desc_func = descriptions.get(resource_type, lambda c: resource_type)
        return desc_func(config)

    def _get_friendly_resource_type(self, resource_type: str) -> str:
        """Convert technical resource type to friendly name"""
        friendly_names = {
            'aws_instance': 'EC2 Instance',
            'aws_db_instance': 'RDS Database',
            'aws_s3_bucket': 'S3 Bucket',
            'aws_lb': 'Load Balancer',
            'aws_security_group': 'Security Group',
            'aws_vpc': 'Virtual Private Cloud',
            'aws_subnet': 'Subnet',
            'aws_ebs_volume': 'EBS Volume',
            'aws_iam_role': 'IAM Role',
        }

        return friendly_names.get(resource_type, resource_type.replace('_', ' ').title())

    def _extract_resource_outputs(self, outputs: Dict[str, Any], resource_type: str) -> Dict[str, Any]:
        """Extract relevant outputs for a specific resource type"""
        if not outputs:
            return {}

        relevant_outputs = {}

        # Match outputs to resource type
        for key, value in outputs.items():
            if resource_type in key:
                # Clean up key name
                clean_key = key.replace(f"{resource_type}_", "").replace("_", " ").title()
                relevant_outputs[clean_key] = value

        return relevant_outputs

    def _format_resource_outputs(self, resource_type: str, outputs: Dict[str, Any]) -> str:
        """Format resource outputs for display"""
        friendly_type = self._get_friendly_resource_type(resource_type)
        parts = [f"\n**{friendly_type}**"]

        for key, value in outputs.items():
            parts.append(f"  • {key}: {value}")

        return "\n".join(parts)

    def _format_resource_details(self, resource: Dict) -> str:
        """Format resource details for list view"""
        name = resource.get('resource_name', resource.get('resource_id', 'unknown'))
        resource_id = resource.get('resource_id', '')
        region = resource.get('region', '')
        environment = resource.get('environment', '')

        details = [name]

        if resource_id and resource_id != name:
            details.append(f"ID: {resource_id}")

        if region:
            details.append(f"Region: {region}")

        if environment:
            details.append(f"Env: {environment}")

        # Add cost if available
        cost = resource.get('estimated_monthly_cost', 0)
        if cost > 0:
            details.append(f"${cost:.2f}/mo")

        return " | ".join(details)

    def generate_help_response(self) -> str:
        """Generate help message with usage examples"""
        return """
🤖 **Infrastructure Provisioning Agent Help**

I can help you manage cloud infrastructure using natural language. Here are some things you can ask me:

**Creating Resources:**
  • "Create a VM in AWS"
  • "Deploy a database in us-west-2"
  • "Set up a t3.medium instance in Oregon"
  • "Create an S3 bucket for production"

**Managing Resources:**
  • "Show me my infrastructure"
  • "List all my resources"
  • "What's running in us-east-1?"
  • "Destroy the database in staging"

**Cost Information:**
  • "How much is my infrastructure costing?"
  • "Show me a cost breakdown"
  • "What's the estimated cost?"

**Supported Resources:**
  • EC2 Instances (Virtual Machines)
  • RDS Databases (MySQL, PostgreSQL)
  • S3 Buckets (Storage)
  • Load Balancers (ALB, NLB)

**Supported Regions:**
  • us-east-1 (N. Virginia) - default
  • us-west-2 (Oregon)
  • eu-west-1 (Ireland)
  • ap-southeast-1 (Singapore)

**Environments:**
  • dev (development) - default
  • staging
  • prod (production)

For any questions or issues, just ask!
        """.strip()

    def generate_status_response(self, request_status: str, details: Dict[str, Any]) -> str:
        """
        Generate status update response

        Args:
            request_status: Current status of the request
            details: Additional status details

        Returns:
            Status message
        """
        status_messages = {
            'pending': '⏳ Request pending approval...',
            'approved': '✅ Request approved, preparing to execute...',
            'executing': '🔄 Provisioning infrastructure...',
            'completed': '✅ Infrastructure provisioning completed!',
            'failed': '❌ Infrastructure provisioning failed.',
            'cancelled': '🚫 Request cancelled.',
        }

        message = status_messages.get(request_status, f"Status: {request_status}")

        if details:
            message += f"\n\n{json.dumps(details, indent=2)}"

        return message
