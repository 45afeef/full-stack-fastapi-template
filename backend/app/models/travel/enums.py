from enum import Enum


class ServiceProviderType(str, Enum):
    CAB = "CAB"
    STAY = "STAY"
    EXPERIENCE = "EXPERIENCE"
    ACTIVITY = "ACTIVITY"
    DESTINATION = "DESTINATION"


class VehicleType(str, Enum):
    SEDAN = "SEDAN"
    SUV = "SUV"
    HATCHBACK = "HATCHBACK"
    VAN = "VAN"


class BookingStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class RoomType(str, Enum):
    SINGLE = "SINGLE"
    DOUBLE = "DOUBLE"
    SUITE = "SUITE"
    DORM = "DORM"


class AmenityScope(str, Enum):
    ROOM = "ROOM"
    COMMON = "COMMON"
    PRIVATE = "PRIVATE"


class StaffRole(str, Enum):
    AGENT = "AGENT"
    MANAGER = "MANAGER"
    SUPPORT = "SUPPORT"


__all__ = [
    "ServiceProviderType",
    "VehicleType",
    "BookingStatus",
    "RoomType",
    "AmenityScope",
    "StaffRole",
]
