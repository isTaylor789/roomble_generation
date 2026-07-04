from typing import Dict, List, Protocol
from uuid import UUID

from src.entities.manager import Manager


class IManagerRepository(Protocol):

    async def find_by_key(self, key: str) -> Manager | None:
        ...
