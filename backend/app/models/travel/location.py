from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Column, DateTime, func


class Location(SQLModel, table=True):
    """Represents a geographic location with latitude and longitude coordinates."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    latitude: float = Field(nullable=False)
    longitude: float = Field(nullable=False)
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )


class LocationLookup(SQLModel, table=True):
    """
    Lookup table for caching place name → (latitude, longitude) mappings.
    
    This table enables efficient resolution of human-readable location names to geographic coordinates.
    - Stores normalized place names (lowercase) for case-insensitive lookups
    - Tracks search frequency to enable future autocomplete and popularity ranking
    - Populated on-demand from external geocoding APIs (OpenStreetMap Nominatim)
    
    **Future optimizations**:
    - Add `aliases` field (JSON) to support alternate names (e.g., "Cochin" → "Kochi")
    - Add composite index on (name, latitude, longitude) for faster lookups
    - Add expiration logic for stale entries (cached geocoding results age)
    - Migrate to Redis for distributed caching at scale
    
    **Performance**:
    - Indexed on `name` for O(1) lookup
    - Handles 1000s of locations efficiently with in-memory TTL cache
    """
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True, unique=True, nullable=False)  # normalized (lowercase)
    latitude: float = Field(nullable=False)
    longitude: float = Field(nullable=False)
    search_count: int = Field(default=0, nullable=False)  # Track popularity
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )


__all__ = ["Location", "LocationLookup"]
