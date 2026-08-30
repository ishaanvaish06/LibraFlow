"""
Library Branch Domain Model
"""
from typing import Dict, Any, Optional


class LibraryBranch:
    """
    Represents a physical campus/city library branch with its own inventory pool.
    """

    def __init__(
        self,
        branch_id: str,
        name: str,
        city: str,
        address: str = "",
        phone: str = "",
        latitude: float = 0.0,
        longitude: float = 0.0,
    ):
        self.branch_id = branch_id
        self.name = name
        self.city = city
        self.address = address
        self.phone = phone
        self.latitude = latitude
        self.longitude = longitude

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "name": self.name,
            "city": self.city,
            "address": self.address,
            "phone": self.phone,
            "coordinates": {
                "latitude": self.latitude,
                "longitude": self.longitude,
            },
        }
