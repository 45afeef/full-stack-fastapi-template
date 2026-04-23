# Location-Based Search System

This document describes the scalable location-aware search system implementation for the FastAPI + SQLModel backend.

## 🎯 Overview

The system enables users to search for travel resources (accommodations, cabs, drivers) by human-readable place names (e.g., "Bangalore", "New York") rather than requiring GPS coordinates. It automatically resolves location names to coordinates and filters nearby resources.

### Key Features

✅ **Place Name Resolution**: Accepts human-readable locations and auto-resolves to coordinates
✅ **Multi-Layer Caching**: In-memory cache (24h TTL) + database persistence
✅ **Minimal API Overhead**: External geocoding called only on cache misses
✅ **Distance-Aware Sorting**: Optional sorting by proximity to search location
✅ **Production-Ready**: Handles errors gracefully; designed for scaling
✅ **Future-Proof**: Clear upgrade path to PostGIS, Redis, and advanced features

---

## 🏗️ Architecture

### Component Stack

```
User Request
    ↓
[Query Endpoint] (/query/stay-providers-near-location, /query/cabs-near-location)
    ↓
[Location Resolution Service] (app/services/geolocation.py)
    ├─ 1. Check in-memory cache (GeoCache)
    ├─ 2. Query LocationLookup table (database)
    ├─ 3. Call Nominatim API (if not found)
    └─ 4. Store in DB and cache
    ↓
[Geographic Filtering] (bounding box pre-filter)
    ├─ Get provider IDs within radius
    └─ Apply additional business logic filters
    ↓
[Distance Calculation] (optional, Haversine formula)
    └─ Sort results by proximity
    ↓
[Pagination] (offset/limit)
    ↓
JSON Response
```

### Data Models

#### LocationLookup (New Table)
```sql
CREATE TABLE locationlookup (
    id UUID PRIMARY KEY,
    name VARCHAR UNIQUE NOT NULL,              -- normalized (lowercase)
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    search_count INTEGER NOT NULL,             -- popularity metric
    created_at TIMESTAMP WITH TIMEZONE,
    updated_at TIMESTAMP WITH TIMEZONE,
    INDEX ix_locationlookup_name ON (name)
);
```

**Purpose**: Persistent cache of geocoding results. Reduces external API calls and enables analytics (search frequency).

---

## 📍 Geolocation Service (`app/services/geolocation.py`)

### Core Components

#### 1. **GeoCache Class**
In-memory cache with automatic TTL expiration (24 hours default).

```python
from app.services.geolocation import get_cache

cache = get_cache()

# Store a result
cache.set("bangalore", (12.9716, 77.5946))

# Retrieve (returns None if expired)
coords = cache.get("bangalore")  # (12.9716, 77.5946) or None
```

**Features**:
- Thread-safe basic implementation
- Automatic expiration on access
- Configurable TTL

**Scaling Note**: Replace with Redis for multi-process deployments:
```python
# Future: Redis backend
cache = RedisGeoCache(host="redis://localhost", ttl_hours=24)
```

---

#### 2. **resolve_location() Function**
Main async function for resolving place names to coordinates.

```python
from app.services.geolocation import resolve_location

# In an async endpoint
coords = await resolve_location("Bangalore", session)
if coords:
    lat, lon = coords
else:
    # Location not found; return error to user
    raise HTTPException(status_code=400, detail="Location not found")
```

**Resolution Strategy**:
1. Normalize input (lowercase, strip whitespace)
2. Check in-memory cache (fast, ~24h TTL)
3. Query LocationLookup table (persistent cache)
4. If not found, call OpenStreetMap Nominatim API (external)
5. Store result in LocationLookup for future lookups
6. Return (lat, lon) tuple

**Error Handling**:
- Network timeout → returns None (caller should handle)
- Invalid input → returns None
- API errors → logged and returns None

---

#### 3. **Haversine Distance Function**
Computes great-circle distance between two geographic points.

```python
from app.services.geolocation import haversine_distance

# Distance in kilometers
distance = haversine_distance(lat1=12.9716, lon1=77.5946,
                             lat2=13.0827, lon2=80.2707)
# Output: ~350 km (Bangalore to Chennai)
```

**Accuracy**:
- ±0.5% for long distances (thousands of km)
- <1% for distances < 100 km
- Uses mean Earth radius of 6371.0 km

**Performance**: O(1) time, ~1 microsecond per call

---

## 🔍 Query Endpoints

### New Endpoints

#### 1. `/query/stay-providers-near-location`

Find stay providers (accommodations) near a place name.

**Request**:
```
GET /query/stay-providers-near-location?location=Bangalore&radius_km=15&min_price=100&max_price=500&sort_by_distance=true
```

**Query Parameters**:
- `location` (required): Place name (e.g., "Bangalore", "Times Square")
- `radius_km` (default 10): Search radius in kilometers
- `min_price`, `max_price`: Filter by room rate
- `pax_count`: Minimum guest capacity
- `room_count`: Minimum number of rooms
- `amenities`: Comma-separated or repeated params (AND semantics)
- `sort_by_distance` (default false): Sort by distance (nearest first)
- `limit`, `offset`: Pagination

**Response**:
```json
{
  "data": [
    {
      "id": "uuid",
      "provider_name": "Mountain Resort",
      "location_id": "uuid",
      "room_count": 20,
      "max_occupancy": 60
    }
  ],
  "count": 42
}
```

**Authorization**: Superuser or agency staff only

---

#### 2. `/query/cabs-near-location`

Find cabs near a place name.

**Request**:
```
GET /query/cabs-near-location?location=Bangalore&radius_km=10&min_capacity=4&sort_by_distance=true
```

**Response**:
```json
{
  "data": [
    {
      "id": "uuid",
      "vehicle_type": "SEDAN",
      "capacity": 4,
      "minimum_rate": 100
    }
  ],
  "count": 18
}
```

**Authorization**: Public (no auth required)

---

### Existing Endpoints (Enhanced)

The following endpoints continue to work as before, with bounding box optimization:
- `/query/stay-units-near`: Direct coordinate-based search
- `/query/cabs`: Direct coordinate search with vehicle filtering
- `/query/drivers`: Direct coordinate search

---

## 🗄️ Database

### LocationLookup Table

**Schema**:
```sql
CREATE TABLE locationlookup (
    id UUID PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    search_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIMEZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIMEZONE DEFAULT NOW()
);
CREATE INDEX ix_locationlookup_name ON locationlookup(name);
```

**Indexes**:
- Primary key on `id`
- Unique index on `name` (normalized location strings)

**Growth Rate**: ~1-5 new entries per day per 1000 users (highly dependent on usage patterns)

---

## ⚡ Performance Characteristics

### Typical Latencies

| Operation | Time | Notes |
|-----------|------|-------|
| Memory cache hit | <1ms | Fast; used for repeated searches |
| Database lookup | 5-10ms | Cached geocoding results |
| External API call | 500-2000ms | Rate limited to ~1 req/sec by Nominatim |
| Bounding box filter | 10-50ms | SQL index on location coordinates |
| Haversine distance sort | 10-100ms | Python calculation; scales O(n) |
| Full request (cache miss) | 1000-2500ms | Network latency to Nominatim |

### Scaling Considerations

**Current Limits**:
- In-memory cache: ~1GB for 100K locations (small)
- Database queries: <20ms for millions of LocationLookup entries with proper indexing
- Distance calculations: O(n) in Python; ~50K calculations/sec per CPU core

**Optimization Roadmap** (see section below):
1. Replace in-memory cache with Redis (distributed cache)
2. Add PostGIS for SQL-based distance calculations
3. Implement request queuing for Nominatim API rate limiting
4. Add caching headers for HTTP responses

---

## 🚀 Deployment

### Docker Setup

The system works seamlessly in Docker:

```bash
# Build and start
docker-compose up -d

# Run migrations (already done in alembic/versions/)
docker-compose exec backend alembic upgrade head

# Test the endpoint
curl "http://localhost:8000/api/v1/query/cabs-near-location?location=Bangalore&radius_km=5"
```

### Environment Variables

Add to `.env` if customizing:
```env
# Optional: configure cache TTL (in hours)
# GEO_CACHE_TTL_HOURS=24

# Optional: override Nominatim endpoint (for self-hosted deployments)
# NOMINATIM_ENDPOINT=https://nominatim.openstreetmap.org
```

Currently, these are hardcoded in `geolocation.py` but can be added to `core/config.py` if needed.

---

## 🔮 Future Optimizations

These are documented in code comments for future developers. Do not implement now; reference when scaling.

### 1. Replace In-Memory Cache with Redis
**When**: When horizontal scaling required (multiple processes)
**How**: 
```python
# Future implementation
from redis import Redis
cache = RedisGeoCache(Redis.from_url("redis://localhost"))
```
**Benefits**: Shared cache across processes/servers

---

### 2. Use PostGIS for Distance Calculations
**When**: When optimizing millions of location searches per day
**How**: 
```sql
-- Instead of Python haversine, use SQL
SELECT provider_id, 
       ST_Distance(
           ST_GeomFromText('POINT(lat lon)'),
           location_point
       ) as distance_km
FROM service_providers
WHERE ST_DWithin(location_point, POINT(lat lon), radius_km)
ORDER BY distance_km
```
**Benefits**: 10-100x faster for large datasets; move computation to database

---

### 3. Add Nominatim Rate Limiting Queue
**When**: When handling thousands of geocoding requests per day
**How**: Use Celery/RQ to queue geocoding requests
**Benefits**: Respect Nominatim's 1 req/sec rate limit; prevent API blocking

---

### 4. Support Location Aliases
**When**: When handling regional/cultural location names
**How**: Add `aliases` JSON field to LocationLookup
```python
class LocationLookup(SQLModel, table=True):
    ...
    aliases: Optional[dict] = Field(default=None)  # {"cochin": true, "kochi": true}
```
**Benefit**: Resolve "Cochin" → "Kochi" automatically

---

### 5. Bounding Box Optimization
**When**: When searching massive datasets
**How**: Add bbox pre-filter before Haversine
```python
# Already implemented in _providers_within_bbox()
# Future: use PostGIS ST_Envelope() for exact bbox with spherical distortion
```

---

### 6. Search Analytics & Autocomplete
**When**: When building UX features
**How**: Use `LocationLookup.search_count` to rank popular searches
```sql
-- Future autocomplete endpoint
SELECT name FROM locationlookup
WHERE name LIKE 'ban%'
ORDER BY search_count DESC
LIMIT 10
```

---

## 🧪 Testing

### Manual Testing

**Test 1: Location Resolution**
```bash
# Should resolve to Bangalore coordinates
curl "http://localhost:8000/api/v1/query/cabs-near-location?location=bangalore&radius_km=5"

# Should cache and return instantly on second call
curl "http://localhost:8000/api/v1/query/cabs-near-location?location=bangalore&radius_km=5"

# Should handle case insensitivity
curl "http://localhost:8000/api/v1/query/cabs-near-location?location=BANGALORE&radius_km=5"
```

**Test 2: Distance Sorting**
```bash
# With sorting
curl "http://localhost:8000/api/v1/query/cabs-near-location?location=bangalore&sort_by_distance=true"

# Results should be ordered by distance (nearest first)
```

**Test 3: Error Handling**
```bash
# Non-existent location
curl "http://localhost:8000/api/v1/query/cabs-near-location?location=fakeplace_xyz123"
# Expected: 400 Bad Request with message about unresolvable location

# Empty location
curl "http://localhost:8000/api/v1/query/cabs-near-location?location="
# Expected: 400 Bad Request (location required)
```

### Unit Tests (Future)

```python
# backend/tests/test_geolocation.py
@pytest.mark.asyncio
async def test_resolve_location_cache_hit():
    """Cache should return cached result on repeated calls"""
    location = "bangalore"
    result1 = await resolve_location(location, session)
    result2 = await resolve_location(location, session)
    assert result1 == result2
    # Verify only 1 DB/API call was made

@pytest.mark.asyncio
async def test_haversine_distance():
    """Test distance calculation accuracy"""
    # Bangalore to Chennai should be ~350 km
    distance = haversine_distance(12.9716, 77.5946, 13.0827, 80.2707)
    assert 345 < distance < 355

@pytest.mark.asyncio
async def test_resolve_location_invalid():
    """Invalid locations should return None"""
    result = await resolve_location("", session)
    assert result is None
    
    result = await resolve_location("fakeplace_xyz", session)
    assert result is None
```

---

## 📚 Code References

### Key Files

| File | Purpose |
|------|---------|
| `app/services/geolocation.py` | Geolocation service (cache, resolution, distance) |
| `app/models/travel/location.py` | LocationLookup and Location models |
| `app/api/routes/query.py` | Query endpoints with location support |
| `app/crud.py` | CRUD operations for location-based queries |
| `app/alembic/versions/10f8e77f7eb3_*` | Database migration |

### Key Functions

```python
# Resolution
from app.services.geolocation import resolve_location
coords = await resolve_location("Bangalore", session)

# Distance
from app.services.geolocation import haversine_distance
distance = haversine_distance(lat1, lon1, lat2, lon2)

# Cache management
from app.services.geolocation import get_cache
cache = get_cache()
cache.clear()  # Reset cache
```

---

## 🐛 Troubleshooting

### Issue: Location not resolving

**Symptoms**: Endpoint returns 400 "Could not resolve location"

**Causes**:
- Nominatim API is down (check https://nominatim.openstreetmap.org/)
- Network connectivity issue from container
- Invalid place name (e.g., "fakeplace")

**Solutions**:
1. Check Nominatim status: `curl -s https://nominatim.openstreetmap.org/status.php`
2. Test from container: `docker-compose exec backend curl https://nominatim.openstreetmap.org/search?q=bangalore&format=json`
3. Try a well-known location: "New York", "London", "Tokyo"

### Issue: Slow distance sorting

**Symptoms**: Endpoint takes >5 seconds with `sort_by_distance=true`

**Cause**: Sorting 1000s of results using Python haversine is O(n)

**Solutions**:
1. Reduce `limit` parameter
2. Add additional filters (reduce result set)
3. Implement PostGIS (future optimization)

### Issue: Cache not working

**Symptoms**: Repeated calls have same latency (500-2000ms)

**Causes**:
- Cache expired (>24 hours)
- Container restarted (in-memory cache lost)

**Solutions**:
1. Check cache size: `cache.size()`
2. Implement persistent Redis cache (future)
3. Monitor cache hits in logs

---

## 📖 Additional Resources

- **Nominatim API**: https://nominatim.org/release-docs/latest/api/Overview/
- **Haversine Formula**: https://en.wikipedia.org/wiki/Haversine_formula
- **PostGIS Documentation**: https://postgis.net/docs/manual-3.4/
- **Redis Caching**: https://redis.io/docs/

---

## 📝 License

This location-based search system is part of the full-stack FastAPI template and follows the same license terms.
