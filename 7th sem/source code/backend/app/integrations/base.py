from abc import ABC, abstractmethod
from typing import Any, Dict

class IntegrationBase(ABC):
    """Base class for all integrations (Email, GitHub)."""
    
    @abstractmethod
    async def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an action on the integration.
        
        Args:
            action: The name of the action to perform (e.g. "send_welcome_email")
            params: Parameters required for the action
            
        Returns:
            A dictionary containing the result of the action
        """
        pass

    @abstractmethod
    async def verify(self) -> bool:
        """
        Verify that the integration is configured correctly and the service is reachable.
        
        Returns:
            True if verification succeeded, False otherwise.
        """
        pass
