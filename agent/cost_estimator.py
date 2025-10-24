"""
AWS Cost Estimation
Estimate monthly costs for AWS resources based on current pricing
"""
from typing import Dict, Any, List
from datetime import datetime
import logging

class AWSCostEstimator:
    """
    Estimate AWS resource costs

    Note: These are approximations based on standard pricing.
    Actual costs may vary based on:
    - Region
    - Reserved instances / Savings Plans
    - Data transfer costs
    - Additional services

    For production, integrate with AWS Pricing API or Cost Explorer
    """

    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self.pricing_data = self._load_pricing_data()

    def _load_pricing_data(self) -> Dict[str, Any]:
        """
        Load pricing data for AWS resources
        Prices are in USD per month (assuming 730 hours/month)
        Based on us-east-1 pricing as of 2024
        """
        return {
            # EC2 Instance pricing (per month, 730 hours)
            'ec2': {
                # General Purpose (T3)
                't3.nano': 3.80,
                't3.micro': 7.66,
                't3.small': 15.33,
                't3.medium': 30.66,
                't3.large': 61.32,
                't3.xlarge': 122.63,
                't3.2xlarge': 245.27,

                # General Purpose (T2)
                't2.micro': 8.47,
                't2.small': 16.94,
                't2.medium': 33.87,
                't2.large': 67.74,

                # Compute Optimized (C5)
                'c5.large': 62.78,
                'c5.xlarge': 125.55,
                'c5.2xlarge': 251.10,
                'c5.4xlarge': 502.20,

                # Memory Optimized (R5)
                'r5.large': 91.98,
                'r5.xlarge': 183.96,
                'r5.2xlarge': 367.92,

                # Compute Optimized (M5)
                'm5.large': 70.08,
                'm5.xlarge': 140.16,
                'm5.2xlarge': 280.32,
            },

            # RDS Database pricing (per month)
            'rds': {
                # MySQL/PostgreSQL - db.t3
                'db.t3.micro': 11.68,
                'db.t3.small': 23.36,
                'db.t3.medium': 46.72,
                'db.t3.large': 93.44,
                'db.t3.xlarge': 186.88,
                'db.t3.2xlarge': 373.76,

                # MySQL/PostgreSQL - db.t2
                'db.t2.micro': 13.14,
                'db.t2.small': 26.28,
                'db.t2.medium': 52.56,

                # MySQL/PostgreSQL - db.m5
                'db.m5.large': 131.40,
                'db.m5.xlarge': 262.80,
                'db.m5.2xlarge': 525.60,

                # MySQL/PostgreSQL - db.r5
                'db.r5.large': 175.20,
                'db.r5.xlarge': 350.40,
                'db.r5.2xlarge': 700.80,
            },

            # RDS Storage (per GB per month)
            'rds_storage': {
                'gp2': 0.115,  # General Purpose SSD
                'gp3': 0.092,  # General Purpose SSD (newer)
                'io1': 0.125,  # Provisioned IOPS
                'magnetic': 0.10,  # Magnetic (deprecated)
            },

            # S3 Pricing (per GB per month)
            's3': {
                'standard': 0.023,  # First 50 TB
                'standard_ia': 0.0125,  # Infrequent Access
                'glacier': 0.004,  # Glacier
                'glacier_deep': 0.00099,  # Glacier Deep Archive
            },

            # EBS Volume pricing (per GB per month)
            'ebs': {
                'gp3': 0.08,  # General Purpose SSD
                'gp2': 0.10,  # General Purpose SSD (older)
                'io2': 0.125,  # Provisioned IOPS SSD
                'st1': 0.045,  # Throughput Optimized HDD
                'sc1': 0.015,  # Cold HDD
                'standard': 0.05,  # Magnetic
            },

            # Load Balancer pricing (per month)
            'lb': {
                'application': 18.40,  # ALB - per load balancer
                'network': 18.40,  # NLB - per load balancer
                'classic': 18.40,  # CLB - per load balancer (deprecated)
                'lcu_hour': 0.008,  # Load Balancer Capacity Units (additional)
            },

            # NAT Gateway (per month, 730 hours)
            'nat_gateway': {
                'base': 32.85,  # Per NAT Gateway
                'data_processing': 0.045,  # Per GB processed
            },

            # Elastic IP (per month)
            'elastic_ip': {
                'attached': 0.0,  # Free when attached to running instance
                'unattached': 3.65,  # Per month when not attached
            },

            # VPC Endpoints (per month)
            'vpc_endpoint': {
                'interface': 7.30,  # Interface endpoint
                'gateway': 0.0,  # Gateway endpoint (free for S3 and DynamoDB)
            },

            # Data Transfer (per GB)
            'data_transfer': {
                'out_internet': 0.09,  # First 10 TB
                'between_regions': 0.02,  # Between regions
                'between_azs': 0.01,  # Between AZs
            },

            # CloudWatch (per month)
            'cloudwatch': {
                'metrics': 0.30,  # Per custom metric
                'alarms': 0.10,  # Per alarm
                'logs_ingestion': 0.50,  # Per GB ingested
                'logs_storage': 0.03,  # Per GB per month
            }
        }

    def estimate_ec2_cost(self, instance_type: str, count: int = 1,
                          storage_gb: int = 30, storage_type: str = 'gp3') -> Dict[str, float]:
        """
        Estimate EC2 instance cost

        Args:
            instance_type: EC2 instance type (e.g., 't3.micro')
            count: Number of instances
            storage_gb: Root volume size in GB
            storage_type: EBS volume type

        Returns:
            Dict with cost breakdown
        """
        instance_cost = self.pricing_data['ec2'].get(instance_type, 10.0) * count
        storage_cost = self.pricing_data['ebs'].get(storage_type, 0.10) * storage_gb * count

        return {
            'compute': instance_cost,
            'storage': storage_cost,
            'total': instance_cost + storage_cost
        }

    def estimate_rds_cost(self, instance_class: str, engine: str = 'mysql',
                          storage_gb: int = 20, storage_type: str = 'gp3',
                          multi_az: bool = False) -> Dict[str, float]:
        """
        Estimate RDS database cost

        Args:
            instance_class: RDS instance class (e.g., 'db.t3.micro')
            engine: Database engine (mysql, postgres, etc.)
            storage_gb: Storage size in GB
            storage_type: Storage type (gp2, gp3, io1)
            multi_az: Whether Multi-AZ deployment is enabled

        Returns:
            Dict with cost breakdown
        """
        instance_cost = self.pricing_data['rds'].get(instance_class, 15.0)

        # Multi-AZ doubles the instance cost
        if multi_az:
            instance_cost *= 2

        storage_cost_per_gb = self.pricing_data['rds_storage'].get(storage_type, 0.115)
        storage_cost = storage_cost_per_gb * storage_gb

        # Storage is also doubled for Multi-AZ
        if multi_az:
            storage_cost *= 2

        # Backup storage (approximation - first GB free, then $0.095/GB)
        backup_cost = max(0, (storage_gb - 1) * 0.095) if storage_gb > 1 else 0

        return {
            'compute': instance_cost,
            'storage': storage_cost,
            'backup': backup_cost,
            'total': instance_cost + storage_cost + backup_cost
        }

    def estimate_s3_cost(self, storage_gb: int = 10, storage_class: str = 'standard',
                         requests_per_month: int = 10000) -> Dict[str, float]:
        """
        Estimate S3 bucket cost

        Args:
            storage_gb: Storage size in GB
            storage_class: Storage class (standard, standard_ia, glacier)
            requests_per_month: Approximate number of requests per month

        Returns:
            Dict with cost breakdown
        """
        storage_cost_per_gb = self.pricing_data['s3'].get(storage_class, 0.023)
        storage_cost = storage_cost_per_gb * storage_gb

        # Request costs (simplified)
        # PUT/POST: $0.005 per 1,000 requests
        # GET: $0.0004 per 1,000 requests
        request_cost = (requests_per_month / 1000) * 0.005

        return {
            'storage': storage_cost,
            'requests': request_cost,
            'total': storage_cost + request_cost
        }

    def estimate_load_balancer_cost(self, lb_type: str = 'application',
                                    lcu_hours: int = 730) -> Dict[str, float]:
        """
        Estimate Load Balancer cost

        Args:
            lb_type: Type of load balancer (application, network, classic)
            lcu_hours: Load Balancer Capacity Unit hours per month

        Returns:
            Dict with cost breakdown
        """
        base_cost = self.pricing_data['lb'].get(lb_type, 18.40)
        lcu_cost = lcu_hours * self.pricing_data['lb']['lcu_hour']

        return {
            'base': base_cost,
            'capacity_units': lcu_cost,
            'total': base_cost + lcu_cost
        }

    def estimate_resources(self, resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Estimate total cost for multiple resources

        Args:
            resources: List of resource configurations

        Returns:
            Dict with detailed cost breakdown
        """
        total_cost = 0.0
        resource_costs = []

        for resource in resources:
            resource_type = resource.get('type')
            config = resource.get('config', {})
            cost_estimate = None

            try:
                if resource_type == 'aws_instance':
                    instance_type = config.get('instance_type', 't3.micro')
                    storage_gb = config.get('root_volume_size', 30)
                    cost_estimate = self.estimate_ec2_cost(instance_type, storage_gb=storage_gb)

                elif resource_type == 'aws_db_instance':
                    instance_class = config.get('instance_class', 'db.t3.micro')
                    engine = config.get('engine', 'mysql')
                    storage_gb = config.get('allocated_storage', 20)
                    multi_az = config.get('multi_az', False)
                    cost_estimate = self.estimate_rds_cost(
                        instance_class, engine, storage_gb, multi_az=multi_az
                    )

                elif resource_type == 'aws_s3_bucket':
                    storage_gb = config.get('estimated_size_gb', 10)
                    storage_class = config.get('storage_class', 'standard')
                    cost_estimate = self.estimate_s3_cost(storage_gb, storage_class)

                elif resource_type == 'aws_lb':
                    lb_type = config.get('load_balancer_type', 'application')
                    cost_estimate = self.estimate_load_balancer_cost(lb_type)

                if cost_estimate:
                    resource_costs.append({
                        'type': resource_type,
                        'cost': cost_estimate,
                        'monthly_total': cost_estimate['total']
                    })
                    total_cost += cost_estimate['total']
                else:
                    # Default estimate for unknown resources
                    resource_costs.append({
                        'type': resource_type,
                        'cost': {'total': 5.0},
                        'monthly_total': 5.0
                    })
                    total_cost += 5.0

            except Exception as e:
                logging.error(f"Error estimating cost for {resource_type}: {e}")
                # Add a default estimate
                resource_costs.append({
                    'type': resource_type,
                    'cost': {'total': 5.0},
                    'monthly_total': 5.0,
                    'error': str(e)
                })
                total_cost += 5.0

        return {
            'total_monthly': round(total_cost, 2),
            'total_annual': round(total_cost * 12, 2),
            'resource_breakdown': resource_costs,
            'region': self.region,
            'estimated_at': datetime.utcnow().isoformat(),
            'note': 'Costs are estimates and may vary based on actual usage, region, and AWS pricing changes.'
        }

    def get_regional_multiplier(self, region: str) -> float:
        """
        Get pricing multiplier for different regions
        Some regions cost more than us-east-1

        Args:
            region: AWS region code

        Returns:
            Multiplier for the region (1.0 = same as us-east-1)
        """
        multipliers = {
            'us-east-1': 1.0,
            'us-east-2': 1.0,
            'us-west-1': 1.0,
            'us-west-2': 1.0,
            'eu-west-1': 1.0,
            'eu-west-2': 1.02,
            'eu-central-1': 1.05,
            'ap-southeast-1': 1.10,
            'ap-southeast-2': 1.12,
            'ap-northeast-1': 1.15,
            'ap-northeast-2': 1.10,
            'sa-east-1': 1.25,  # São Paulo is more expensive
            'ca-central-1': 1.02,
        }

        return multipliers.get(region, 1.05)  # Default 5% more for unknown regions
