from abc import ABC, abstractmethod
from typing import Optional

class BaseTester(ABC):
    """
    Abstract base class for all proxy testers.
    Defines the interface for testing a proxy's availability and performance.
    """

    @abstractmethod
    def test_proxy(self, proxy_ip: str, proxy_port: int, proxy_protocol: Optional[str] = None) -> dict:
        """
        Tests the given proxy.

        Args:
            proxy_ip: The IP address of the proxy.
            proxy_port: The port of the proxy.
            proxy_protocol: The protocol of the proxy (e.g., 'http', 'https').

        Returns:
            A dictionary containing test results, e.g.:
            {
                "success": bool,
                "response_time": float,  # in seconds
                "status_code": Optional[int],
                "error_message": Optional[str],
            }
        """
        pass
