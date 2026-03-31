from abc import ABC, abstractmethod
from triggers.router import ApiRouter


class AbstractAdapter(ABC):
    @abstractmethod
    def register(self, sdk, routers: list[ApiRouter]) -> None:
        """Register all routes from all routers with the underlying framework/SDK."""
        ...
