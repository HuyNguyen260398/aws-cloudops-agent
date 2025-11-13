# 🔍 AWS CloudOps Agent - Monitoring Setup

## Quick Start

### 1. Deploy Monitoring Infrastructure

```bash
# PowerShell
.\deploy_monitoring.ps1 -NotificationEmail your@email.com

# Or manually
aws cloudformation create-stack \
  --stack-name cloudops-monitoring \
  --template-body file://infrastructure/monitoring_stack.yaml \
  --parameters ParameterKey=NotificationEmail,ParameterValue=your@email.com \
  --capabilities CAPABILITY_NAMED_IAM
```

### 2. Test Locally

```bash
# Run scheduled monitoring
uv run src/workflows/scheduled_monitor.py

# Or test via CLI
uv run src/agent_cli.py
# Then: "Monitor my EC2 instances"
```

### 3. Deploy to Production

```bash
# Package code
cd src
zip -r ../monitoring.zip .

# Update Lambda
aws lambda update-function-code \
  --function-name cloudops-agent-monitor \
  --zip-file fileb://../monitoring.zip
```

## Architecture

**Multi-Agent Workflow:**
```
Event → Monitoring Agent → Alert Agent → Remediation Agent → Action
```

**Monitoring Modes:**
1. **Event-Driven**: Real-time response to AWS events
2. **Scheduled**: Periodic checks every 5 minutes
3. **On-Demand**: Manual CLI/API invocation

## What Gets Monitored

- ✅ EC2 instance health & metrics
- ✅ RDS database performance
- ✅ S3 bucket security
- ✅ Lambda errors & throttling
- ✅ CloudWatch alarms
- ✅ Cost anomalies
- ✅ Security findings
- ✅ Resource configuration

## Alert Levels

- 🔴 **CRITICAL**: Immediate action (outage, breach)
- 🟡 **WARNING**: Needs attention (degradation)
- 🔵 **INFO**: FYI (config changes)
- 🟢 **RESOLVED**: Issue fixed

## Cost Estimate

- Bedrock API: ~$10-30/month
- Lambda: Free tier covers most
- EventBridge: ~$1/month
- **Total: $10-50/month**

## Next Steps

1. ✅ Deploy infrastructure
2. ✅ Confirm SNS email
3. ✅ Test monitoring
4. ✅ Review alerts
5. ✅ Enable auto-remediation

See [MONITORING_GUIDE.md](docs/MONITORING_GUIDE.md) for details.
