You are implementing a **scalable location-based search system** in an existing FastAPI + SQLModel backend.

## 🎯 Goal

Add **location-aware search** to an already working search endpoint, with:

* minimal disruption to existing logic
* strong UX (users search by place name, not coordinates)
* scalable architecture for future millions of users

---

## 🧱 Existing Context

* FastAPI backend
* SQLModel ORM
* Existing many `/query` endpoints with filters (non-geo)
* `CabProviders` and `StayProviders` table already exists
* `Location` table exists and is linked via FK:
* `StayUnits` belongs to `StayProviders`
* Cab and Driver belongs to `CabProviders`

```python
class Location(SQLModel, table=True):
    id: UUID = Field(default=None, primary_key=True)
    latitude: float = Field(nullable=False)
    longitude: float = Field(nullable=False)
```

---

## 🚨 Requirements (MVP but scalable)

### 1. Extend Location Intelligence

Modify or extend the system to support resolving human-readable location queries.

Create a new table (or extend existing one if preferred):

```python
class LocationLookup(SQLModel, table=True):
    id: UUID = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)   # normalized (lowercase)
    latitude: float
    longitude: float
    search_count: int = 0
```

Optional (future-ready):

* aliases (JSON or separate table)

---

### 2. Add Location Resolution Layer

Implement a function:

```python
async def resolve_location(query: str, db: Session) -> tuple[float, float] | None:
```

Behavior:

1. Normalize input (`lower().strip()`)

2. Check `LocationLookup` table:

   * if found:

     * increment `search_count`
     * return lat/lng

3. If NOT found:

   * call external geocoding API (use OpenStreetMap Nominatim)
   * extract first result
   * store in `LocationLookup`
   * return lat/lng

4. If no result:

   * return None

---

### 3. Add Caching Layer

Implement a simple in-memory cache with TTL:

* key: normalized location string
* value: `(lat, lng)`
* TTL: ~24 hours

Cache should be checked BEFORE DB lookup if possible.

Structure example:

```python
class GeoCache:
    def get(key: str) -> Optional[tuple[float, float]]
    def set(key: str, value: tuple[float, float])
```

---

### 4. Extend Search Endpoint

Modify existing `/search` endpoint:

Add query params:

```python
location: Optional[str]
radius_km: float = 10
```

Flow:

1. Run existing filters as-is
2. If `location` provided:

   * call `resolve_location`
   * if coords found:

     * apply geo filtering

---

### 5. Geo Filtering (Haversine)

Implement SQL expression using SQLAlchemy functions:

```python
distance = haversine(lat, lng, Property.location.latitude, Property.location.longitude)
```

Apply:

```python
WHERE distance <= radius_km
ORDER BY distance ASC
```

---

### 6. Database Considerations

Ensure:

* indexes on latitude and longitude
* efficient joins between Property and Location

---

## ⚡ Performance Optimizations (IMPORTANT)

* Use bounding box pre-filter before Haversine (optional but recommended)
* Avoid calling external API repeatedly (cache + DB layer handles this)
* Use async HTTP client for geocoding

---

## 🧠 UX Behavior

* If user searches only location → return nearby properties
* If combined with filters → apply both
* Results should feel proximity-aware (closest first)

---

## 🔮 Future Upgrade Notes (DO NOT IMPLEMENT NOW, JUST DOCUMENT)

Leave clear comments in code for future agents:

1. Replace Haversine with PostGIS (`ST_DWithin`) when scaling
2. Replace in-memory cache with Redis
3. Add autocomplete using `LocationLookup` sorted by `search_count`
4. Support alias mapping (e.g., "cochin" → "kochi")
5. Add bounding box optimization for large datasets
6. Allow direct lat/lng input from frontend
7. Add ranking combining:

   * distance
   * text relevance
   * popularity

---

## 🚫 Constraints

* DO NOT break existing search functionality
* DO NOT introduce heavy dependencies (no Elasticsearch yet)
* KEEP implementation clean and modular
* KEEP functions reusable and testable

---

## ✅ Deliverables

* Updated models (if needed)
* `resolve_location` implementation
* caching layer
* updated `/search` endpoint
* helper function for Haversine
* clear inline comments for future scaling

---

## 🧠 Guiding Principle

Convert user input → geographic coordinates → filter by proximity.

NOT:

* string matching across address fields

---

Implement cleanly, with production awareness, but optimized for fast delivery.
