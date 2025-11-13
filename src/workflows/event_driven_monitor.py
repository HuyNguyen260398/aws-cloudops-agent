import json
from strands.models import BedrockModel
from workflows.monitoring_orchestrator import MonitoringOrchestrator
from utils.config_manager import AgentCoreConfigManager
import utils.mylogger as mylogger

logger = mylogger.get_logger()


class EventDrivenMonitor:
    """Event-driven monitoring triggered by CloudWatch Events/EventBridge"""
    
    def __init__(self):
        config_manager = AgentCoreConfigManager()
        model_settings = config_manager.get_model_settings()
        self.model = BedrockModel(**model_settings)
        self.orchestrator = MonitoringOrchestrator(self.model)
        
    async def handle_cloudwatch_alarm(self, event: dict):
        """Handle CloudWatch alarm state change"""
        logger.info("🚨 CloudWatch alarm triggered")
        
        alarm_name = event.get("detail", {}).get("alarmName")
        state = event.get("detail", {}).get("state", {}).get("value")
        
        if state == "ALARM":
            prompt = f"""CloudWatch alarm '{alarm_name}' is in ALARM state.
            
Investigate:
1. Check affected resources
2. Analyze metrics and logs
3. Determine root cause
4. Suggest remediation"""
            
            response = await self.orchestrator.monitoring_agent.run_async(prompt)
            logger.info(f"📊 Investigation: {response}")
            
            if "CRITICAL" in response:
                remediation = await self.orchestrator.remediation_agent.run_async(
                    f"Create remediation plan for: {response}"
                )
                logger.info(f"🔧 Remediation: {remediation}")
                return {"status": "remediation_required", "plan": remediation}
        
        return {"status": "acknowledged"}
    
    async def handle_health_event(self, event: dict):
        """Handle AWS Health Dashboard event"""
        logger.info("🏥 AWS Health event received")
        
        service = event.get("detail", {}).get("service")
        event_type = event.get("detail", {}).get("eventTypeCode")
        
        prompt = f"""AWS Health event detected:
Service: {service}
Event Type: {event_type}

Assess impact on our resources and recommend actions."""
        
        response = await self.orchestrator.alert_agent.run_async(prompt)
        return {"status": "analyzed", "assessment": response}
    
    async def handle_cost_anomaly(self, event: dict):
        """Handle cost anomaly detection"""
        logger.info("💰 Cost anomaly detected")
        
        anomaly = event.get("detail", {})
        
        prompt = f"""Cost anomaly detected:
{json.dumps(anomaly, indent=2)}

Investigate:
1. Identify resources causing cost spike
2. Determine if legitimate or wasteful
3. Recommend cost optimization actions"""
        
        response = await self.orchestrator.monitoring_agent.run_async(prompt)
        return {"status": "investigated", "findings": response}


def lambda_handler(event, context):
    """AWS Lambda handler for EventBridge events"""
    monitor = EventDrivenMonitor()
    
    event_source = event.get("source")
    
    if event_source == "aws.cloudwatch":
        import asyncio
        result = asyncio.run(monitor.handle_cloudwatch_alarm(event))
        return {"statusCode": 200, "body": json.dumps(result)}
    
    elif event_source == "aws.health":
        import asyncio
        result = asyncio.run(monitor.handle_health_event(event))
        return {"statusCode": 200, "body": json.dumps(result)}
    
    elif event_source == "aws.ce":
        import asyncio
        result = asyncio.run(monitor.handle_cost_anomaly(event))
        return {"statusCode": 200, "body": json.dumps(result)}
    
    return {"statusCode": 400, "body": "Unknown event source"}
