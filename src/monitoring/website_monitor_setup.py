"""
AWS Website Monitoring Setup
Creates CloudWatch alarms and SNS notifications for static website monitoring
"""

import boto3
import json
from typing import Dict


class WebsiteMonitorSetup:
    def __init__(self, region: str = 'us-east-1'):
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        self.sns = boto3.client('sns', region_name=region)
        self.route53 = boto3.client('route53', region_name=region)
        
    def create_sns_topic(self, topic_name: str = 'website-monitoring-alerts') -> str:
        """Create SNS topic for alerts"""
        response = self.sns.create_topic(Name=topic_name)
        return response['TopicArn']
    
    def subscribe_email(self, topic_arn: str, email: str):
        """Subscribe email to SNS topic"""
        self.sns.subscribe(
            TopicArn=topic_arn,
            Protocol='email',
            Endpoint=email
        )
    
    def create_cloudfront_alarms(self, distribution_id: str, topic_arn: str):
        """Create CloudFront monitoring alarms"""
        alarms = [
            {
                'name': f'CloudFront-5xx-Errors-{distribution_id}',
                'metric': '5xxErrorRate',
                'threshold': 5.0,
                'description': 'Alert when 5xx error rate exceeds 5%'
            },
            {
                'name': f'CloudFront-4xx-Errors-{distribution_id}',
                'metric': '4xxErrorRate',
                'threshold': 10.0,
                'description': 'Alert when 4xx error rate exceeds 10%'
            },
            {
                'name': f'CloudFront-Cache-Hit-Rate-{distribution_id}',
                'metric': 'CacheHitRate',
                'threshold': 70.0,
                'comparison': 'LessThanThreshold',
                'description': 'Alert when cache hit rate drops below 70%'
            }
        ]
        
        for alarm in alarms:
            self.cloudwatch.put_metric_alarm(
                AlarmName=alarm['name'],
                ComparisonOperator=alarm.get('comparison', 'GreaterThanThreshold'),
                EvaluationPeriods=2,
                MetricName=alarm['metric'],
                Namespace='AWS/CloudFront',
                Period=300,
                Statistic='Average',
                Threshold=alarm['threshold'],
                ActionsEnabled=True,
                AlarmActions=[topic_arn],
                AlarmDescription=alarm['description'],
                Dimensions=[
                    {'Name': 'DistributionId', 'Value': distribution_id}
                ]
            )
    
    def create_waf_alarms(self, web_acl_name: str, topic_arn: str, region: str = 'us-east-1'):
        """Create WAF monitoring alarms"""
        alarms = [
            {
                'name': f'WAF-Blocked-Requests-Spike-{web_acl_name}',
                'metric': 'BlockedRequests',
                'threshold': 1000,
                'description': 'Alert when blocked requests spike above 1000'
            },
            {
                'name': f'WAF-Allowed-Requests-Drop-{web_acl_name}',
                'metric': 'AllowedRequests',
                'threshold': 10,
                'comparison': 'LessThanThreshold',
                'description': 'Alert when allowed requests drop below 10'
            }
        ]
        
        for alarm in alarms:
            self.cloudwatch.put_metric_alarm(
                AlarmName=alarm['name'],
                ComparisonOperator=alarm.get('comparison', 'GreaterThanThreshold'),
                EvaluationPeriods=2,
                MetricName=alarm['metric'],
                Namespace='AWS/WAFV2',
                Period=300,
                Statistic='Sum',
                Threshold=alarm['threshold'],
                ActionsEnabled=True,
                AlarmActions=[topic_arn],
                AlarmDescription=alarm['description'],
                Dimensions=[
                    {'Name': 'WebACL', 'Value': web_acl_name},
                    {'Name': 'Region', 'Value': region}
                ]
            )
    
    def create_route53_health_check(self, domain: str, topic_arn: str) -> str:
        """Create Route53 health check"""
        response = self.route53.create_health_check(
            HealthCheckConfig={
                'Type': 'HTTPS',
                'ResourcePath': '/',
                'FullyQualifiedDomainName': domain,
                'Port': 443,
                'RequestInterval': 30,
                'FailureThreshold': 3,
                'MeasureLatency': True
            }
        )
        health_check_id = response['HealthCheck']['Id']
        
        self.cloudwatch.put_metric_alarm(
            AlarmName=f'Route53-Health-Check-{domain}',
            ComparisonOperator='LessThanThreshold',
            EvaluationPeriods=1,
            MetricName='HealthCheckStatus',
            Namespace='AWS/Route53',
            Period=60,
            Statistic='Minimum',
            Threshold=1.0,
            ActionsEnabled=True,
            AlarmActions=[topic_arn],
            AlarmDescription=f'Alert when {domain} health check fails',
            Dimensions=[
                {'Name': 'HealthCheckId', 'Value': health_check_id}
            ]
        )
        
        return health_check_id
    
    def setup_complete_monitoring(self, config: Dict) -> Dict:
        """Setup complete monitoring workflow"""
        results = {}
        
        topic_arn = self.create_sns_topic(config.get('topic_name', 'website-monitoring-alerts'))
        results['topic_arn'] = topic_arn
        
        if config.get('email'):
            self.subscribe_email(topic_arn, config['email'])
            results['email_subscribed'] = config['email']
        
        if config.get('cloudfront_distribution_id'):
            self.create_cloudfront_alarms(config['cloudfront_distribution_id'], topic_arn)
            results['cloudfront_alarms'] = 'created'
        
        if config.get('waf_web_acl_name'):
            self.create_waf_alarms(
                config['waf_web_acl_name'], 
                topic_arn,
                config.get('region', 'us-east-1')
            )
            results['waf_alarms'] = 'created'
        
        if config.get('domain'):
            health_check_id = self.create_route53_health_check(config['domain'], topic_arn)
            results['health_check_id'] = health_check_id
        
        return results


if __name__ == '__main__':
    monitor = WebsiteMonitorSetup(region='us-east-1')
    
    config = {
        'topic_name': 'website-monitoring-alerts',
        'email': 'your-email@example.com',
        'cloudfront_distribution_id': 'E1234EXAMPLE',
        'waf_web_acl_name': 'your-web-acl',
        'domain': 'example.com',
        'region': 'us-east-1'
    }
    
    results = monitor.setup_complete_monitoring(config)
    print(json.dumps(results, indent=2))
