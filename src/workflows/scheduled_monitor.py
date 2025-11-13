import asyncio
import json
from datetime import datetime
from strands.models import BedrockModel
from workflows.monitoring_orchestrator import MonitoringOrchestrator
from utils.config_manager import AgentCoreConfigManager
import utils.mylogger as mylogger

logger = mylogger.get_logger()


class ScheduledMonitor:
    """Scheduled monitoring service for continuous AWS monitoring"""
    
    def __init__(self, interval_minutes: int = 5):
        self.interval_minutes = interval_minutes
        config_manager = AgentCoreConfigManager()
        model_settings = config_manager.get_model_settings()
        self.model = BedrockModel(**model_settings)
        self.orchestrator = MonitoringOrchestrator(self.model)
        
    async def start(self, services: list = None):
        """Start continuous monitoring"""
        logger.info(f"🚀 Starting scheduled monitoring (interval: {self.interval_minutes} min)")
        
        while True:
            try:
                logger.info(f"⏰ Running monitoring cycle at {datetime.utcnow().isoformat()}")
                results = await self.orchestrator.run_monitoring_cycle(services)
                
                self._log_results(results)
                
                if results.get("alerts"):
                    await self._send_notifications(results)
                
                await asyncio.sleep(self.interval_minutes * 60)
                
            except Exception as e:
                logger.error(f"❌ Monitoring cycle failed: {e}")
                await asyncio.sleep(60)
    
    def _log_results(self, results: dict):
        """Log monitoring results"""
        logger.info(f"""
📊 Monitoring Results:
- Services Checked: {len(results['services_checked'])}
- Findings: {len(results['findings'])}
- Alerts: {len(results['alerts'])}
- Remediations: {len(results['remediations'])}
        """)
    
    async def _send_notifications(self, results: dict):
        """Send notifications for alerts"""
        logger.info("📧 Sending alert notifications")


async def main():
    """Run scheduled monitoring"""
    monitor = ScheduledMonitor(interval_minutes=5)
    await monitor.start(services=["ec2", "rds", "s3", "lambda", "cloudwatch"])


if __name__ == "__main__":
    asyncio.run(main())
