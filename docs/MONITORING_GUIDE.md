# 🔍 AWS CloudOps Agent - Monitoring Guide

## Overview

This guide explains how to set up and use the AWS CloudOps Agent for infrastructure monitoring.

## Architecture

The monitoring system uses a **multi-agent workflow** with three specialized agents:

1. **Monitoring Agent** - Detects issues and anomalies
2. **Alert Agent** - Analyzes and prioritizes findings
3. **Remediation Agent** - Suggests and executes fixes

## Monitoring Approaches

### 1. Event-Driven Monitoring (Recommended)

Real-time monitoring triggered by AWS events:

**Triggers:**

- CloudWatch alarm state changes
- AWS Health Dashboard events
- Cost anomaly detection
- EC2 state changes
- Security findings

**Setup:**

```bash
# Deploy monitoring infrastructure
aws cloudformation create-stack \
  --stack-name cloudops-monitoring \
  --template-body file://infrastructure/monitoring_stack.yaml \
  --parameters ParameterKey=NotificationEmail,ParameterValue=your@email.com \
  --capabilities CAPABILITY_NAMED_IAM

# Deploy EventBridge rules
aws cloudformation create-stack \
  --stack-name cloudops-eventbridge \
  --template-body file://infrastructure/eventbridge_rules.yaml \
  --parameters ParameterKey=MonitoringLambdaArn,ParameterValue=<lambda-arn>
```

### 2. Scheduled Monitoring

Continuous monitoring at regular intervals:

**Run locally:**

```bash
uv run src/workflows/scheduled_monitor.py
```

**Deploy to Lambda:**

```bash
# Package and deploy
zip -r monitoring.zip src/
aws lambda create-function \
  --function-name cloudops-scheduled-monitor \
  --runtime python3.11 \
  --handler workflows.scheduled_monitor.lambda_handler \
  --zip-file fileb://monitoring.zip \
  --role <execution-role-arn>
```

### 3. On-Demand Monitoring

Manual monitoring via CLI or API:

```bash
# Using CLI
uv run src/agent_cli.py

# Then ask:
"Monitor my EC2 instances for issues"
"Check RDS database health"
"Scan for security vulnerabilities"
```

## Monitored Services

### Compute

- **EC2**: Instance health, CPU/memory, stopped instances
- **Lambda**: Error rates, throttling, cold starts
- **ECS/EKS**: Container health, resource utilization

### Storage

- **S3**: Bucket policies, versioning, lifecycle rules
- **EBS**: Volume health, snapshots, encryption

### Database

- **RDS**: Performance metrics, backup status, connections
- **DynamoDB**: Throttling, capacity, GSI health

### Networking

- **VPC**: Security groups, NACLs, flow logs
- **ELB**: Target health, latency, error rates
- **Route53**: Health checks, DNS queries

### Security

- **IAM**: Policy changes, unused credentials
- **GuardDuty**: Security findings
- **Security Hub**: Compliance violations

### Cost

- **Cost Explorer**: Spending trends, anomalies
- **Budgets**: Budget threshold alerts

## Alert Severity Levels

- 🔴 **CRITICAL**: Immediate action required (outage, security breach)
- 🟡 **WARNING**: Attention needed (performance degradation)
- 🔵 **INFO**: Informational (configuration changes)
- 🟢 **RESOLVED**: Previously reported issue fixed

## Remediation Workflow

1. **Detection**: Monitoring agent identifies issue
2. **Analysis**: Alert agent determines severity and impact
3. **Planning**: Remediation agent creates fix plan
4. __Approval__: User confirms via handoff_to_user
5. **Execution**: Agent applies fix using AWS APIs
6. **Verification**: Confirms issue resolved

## Example Workflows

### Scenario 1: High CPU Alert

```ini
Event: CloudWatch alarm "High CPU" → ALARM state
↓
Monitoring Agent: Investigates EC2 instance metrics
↓
Alert Agent: Generates critical alert with impact analysis
↓
Remediation Agent: Suggests scaling or instance optimization
↓
User Approval: Confirms remediation plan
↓
Execution: Applies fix (e.g., add instances to Auto Scaling)
↓
Verification: Confirms CPU normalized
```

### Scenario 2: Cost Anomaly

```ini
Event: Cost Explorer detects spending spike
↓
Monitoring Agent: Identifies resources causing spike
↓
Alert Agent: Analyzes if legitimate or wasteful
↓
Remediation Agent: Recommends cost optimization
↓
User Review: Decides on actions
```

### Scenario 3: Security Finding

```ini
Event: GuardDuty finding detected
↓
Monitoring Agent: Investigates affected resources
↓
Alert Agent: Assesses security impact
↓
Remediation Agent: Creates incident response plan
↓
Immediate Action: Isolates compromised resources
```

## Configuration

### Monitoring Intervals

Edit `src/workflows/scheduled_monitor.py`:

```python
# Check every 5 minutes
monitor = ScheduledMonitor(interval_minutes=5)

# Check every hour
monitor = ScheduledMonitor(interval_minutes=60)
```

### Services to Monitor

```python
# Monitor specific services
await monitor.start(services=["ec2", "rds", "s3"])

# Monitor all services
await monitor.start()  # Uses default list
```

### Alert Thresholds

Customize in agent system prompts:

- `src/agents/monitoring_agent.py`
- `src/agents/alert_agent.py`

## Best Practices

1. **Start Small**: Begin with critical services (EC2, RDS)
2. **Tune Alerts**: Adjust thresholds to reduce noise
3. **Test Remediations**: Validate fixes in non-prod first
4. **Review Regularly**: Check monitoring results weekly
5. **Automate Gradually**: Start manual, automate proven fixes

## Troubleshooting

### No Alerts Received

- Check EventBridge rules are enabled
- Verify Lambda has correct permissions
- Check SNS topic subscription confirmed

### False Positives

- Adjust monitoring thresholds
- Add maintenance window logic
- Correlate multiple signals

### Agent Errors

- Check CloudWatch Logs: `/aws/cloudops-agent/monitoring`
- Verify Bedrock model access
- Ensure IAM permissions correct

## Cost Considerations

- **Bedrock API calls**: ~$0.003 per 1K input tokens
- **Lambda invocations**: Free tier covers most usage
- **CloudWatch metrics**: Standard pricing applies
- **EventBridge events**: $1 per million events

**Estimated monthly cost**: $10-50 for typical workload

## Next Steps

1. Deploy monitoring infrastructure
2. Test with on-demand monitoring
3. Enable event-driven monitoring
4. Configure alert notifications
5. Set up automated remediations

## Support

For issues or questions:

- Check logs in CloudWatch
- Review agent responses
- Adjust system prompts for better results
