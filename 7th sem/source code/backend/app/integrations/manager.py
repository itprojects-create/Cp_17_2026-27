import logging
from typing import Any, Dict

from app.integrations.email import EmailIntegration
from app.integrations.github import GitHubIntegration

logger = logging.getLogger(__name__)

class IntegrationManager:
    """
    Central manager for executing actions across all integrations.
    """
    
    def __init__(self):
        self.integrations = {
            "email": EmailIntegration(),
            "github": GitHubIntegration(),
        }

    async def execute_action(self, integration_name: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an action on a specific integration.
        
        Args:
            integration_name: The name of the integration (e.g., 'email', 'github')
            action: The specific action to execute
            params: Parameters for the action
            
        Returns:
            The result of the action execution
        """
        integration_name = integration_name.lower()
        if integration_name not in self.integrations:
            msg = f"Unknown integration: {integration_name}"
            logger.error(msg)
            raise ValueError(msg)
            
        integration = self.integrations[integration_name]
        
        try:
            logger.info(f"Executing '{action}' on integration '{integration_name}'")
            return await integration.execute(action, params)
        except Exception as e:
            logger.error(f"Error executing '{action}' on '{integration_name}': {e}")
            return {"status": "error", "message": str(e), "error": str(e)}


    async def verify_integration(self, integration_name: str) -> bool:
        """
        Verify that a specific integration is configured and working.
        """
        integration_name = integration_name.lower()
        if integration_name not in self.integrations:
            return False
            
        try:
            return await self.integrations[integration_name].verify()
        except Exception as e:
            logger.error(f"Error verifying '{integration_name}': {e}")
            return False

# Create a singleton instance
integration_manager = IntegrationManager()
