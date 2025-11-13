import asyncio
from datetime import datetime
from typing import Dict, List
from strands.models import BedrockModel
from agents.monitoring_agent import MonitoringAgent
from agents.alert_agent import AlertAgent
from agents.remediation_agent import RemediationAgent
import utils.mylogger as mylogger

logger = mylogger.get_logger()


class MonitoringOrchestrator:
    """Orchestrates multi-agent monitoring workflow"""
    
    def __init__(self, model: BedrockModel):
        self.model = model
        self.monitoring_agent = MonitoringAgent(model=model)
        self.alert_agent = AlertAgent(model=model)
        self.remediation_agent = RemediationAgent(model=model)
        
    async def run_monitoring_cycle(self, services: List[str] = None) -> Dict:
        """Execute complete monitoring cycle"""
        logger.info("🔄 Starting monitoring cycle")
        
        if not services:
            services = ["ec2", "rds", "s3", "lambda", "cloudwatch"]
        
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "services_checked": services,
            "findings": [],
            "alerts": [],
            "remediations": []
        }
        
        # Step 1: Monitor resources
        for service in services:
            logger.info(f"🔍 Monitoring {service.upper()}")
            findings = await self._monitor_service(service)
            results["findings"].extend(findings)
        
        # Step 2: Analyze and generate alerts
        if results["findings"]:
            logger.info("📢 Analyzing findings and generating alerts")
            alerts = await self._generate_alerts(results["findings"])
            results["alerts"] = alerts
            
            # Step 3: Suggest remediations for critical issues
            critical_alerts = [a for a in alerts if a.get("severity") == "CRITICAL"]
            if critical_alerts:
                logger.info("🔧 Generating remediation plans")
                remediations = await self._generate_remediations(critical_alerts)
                results["remediations"] = remediations
        
        logger.info(f"✅ Monitoring cycle complete: {len(results['findings'])} findings, {len(results['alerts'])} alerts")
        return results
    
    async def _monitor_service(self, service: str) -> List[Dict]:
        """Monitor specific AWS service"""
        prompt = f"""Monitor {service.upper()} service and check for:
- Resource health and status
- Performance metrics and anomalies
- Security configuration issues
- Cost anomalies
- Best practice violations

Return findings in structured format with severity levels."""
        
        response = await self.monitoring_agent.run_async(prompt)
        return self._parse_findings(response, service)
    
    async def _generate_alerts(self, findings: List[Dict]) -> List[Dict]:
        """Generate alerts from findings"""
        prompt = f"""Analyze these monitoring findings and generate actionable alerts:

{findings}

For each issue, provide:
- Alert title and severity
- Affected resources
- Business impact
- Recommended actions"""
        
        response = await self.alert_agent.run_async(prompt)
        return self._parse_alerts(response)
    
    async def _generate_remediations(self, alerts: List[Dict]) -> List[Dict]:
        """Generate remediation plans for critical alerts"""
        prompt = f"""Create remediation plans for these critical alerts:

{alerts}

For each alert, provide:
- Root cause analysis
- Step-by-step remediation plan
- Risks and rollback procedures
- Verification steps"""
        
        response = await self.remediation_agent.run_async(prompt)
        return self._parse_remediations(response)
    
    def _parse_findings(self, response: str, service: str) -> List[Dict]:
        """Parse agent response into structured findings"""
        findings = []
        if "CRITICAL" in response or "WARNING" in response:
            findings.append({
                "service": service,
                "severity": "CRITICAL" if "CRITICAL" in response else "WARNING",
                "details": response,
                "timestamp": datetime.utcnow().isoformat()
            })
        return findings
    
    def _parse_alerts(self, response: str) -> List[Dict]:
        """Parse alert response"""
        return [{"alert": response, "timestamp": datetime.utcnow().isoformat()}]
    
    def _parse_remediations(self, response: str) -> List[Dict]:
        """Parse remediation response"""
        return [{"remediation": response, "timestamp": datetime.utcnow().isoformat()}]
