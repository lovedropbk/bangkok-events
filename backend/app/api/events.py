from datetime import datetime
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text, and_, or_
from geoalchemy2.functions import ST_DWithin, ST_Distance, ST_MakePoint, ST_SetSRID

from app.database import get_db
from app.models.event import Event
from app.schemas.event import (
    EventResponse,
    EventListResponse,
    EventSubmit,
)

router = APIRouter(prefix="/events", tags=["events"])


def event_to_response(event: Event, distance_km: Optional[float] = None) -> EventResponse:
    """Convert SQLAlchemy Event model to Pydantic EventResponse"""
    lat, lng = None, None
    if event.location is not None:
        # Extract lat/lng from geography point
        result = Session.object_session(event).execute(
            text("SELECT ST_Y(location::geometry), ST_X(location::geometry) FROM events WHERE id = :id"),
            {"id": event.id}
        ).fetchone()
        if result:
            lat, lng = result[0], result[1]

    return EventResponse(
        id=event.id,
        title=event.title,
        description=event.description,
        start_datetime=event.start_datetime,
        end_datetime=event.end_datetime,
        venue_name=event.venue_name,
        address=event.address,
        district=event.district,
        category=event.category,
        tags=event.tags or [],
        source=event.source,
        source_url=event.source_url,
        image_url=event.image_url,
        price_info=event.price_info,
        organizer_name=event.organizer_name,
        status=event.status,
        is_featured=event.is_featured or False,
        latitude=lat,
        longitude=lng,
        distance_km=distance_km,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


@router.get("", response_model=EventListResponse)
async def list_events(
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lng: Optional[float] = Query(None, ge=-180, le=180),
    radius_km: Optional[float] = Query(None, ge=0, le=100),
    district: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    q: Optional[str] = Query(None, max_length=200),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    featured_only: bool = Query(False),
    db: Session = Depends(get_db),
):
    """
    List events with filters.

    - **lat, lng, radius_km**: Location-based filter (finds events within radius)
    - **district**: Filter by district name (Sukhumvit, Thonglor, etc.)
    - **category**: Filter by category (party, music, art, food, etc.)
    - **start_date, end_date**: Filter by date range
    - **q**: Full-text search query
    - **featured_only**: Only return featured events
    """
    # Base query - only approved events
    query = db.query(Event).filter(Event.status == 'approved')

    # Apply filters
    if district:
        query = query.filter(Event.district.ilike(f"%{district}%"))

    if category:
        query = query.filter(Event.category == category)

    if start_date:
        query = query.filter(Event.start_datetime >= start_date)

    if end_date:
        query = query.filter(Event.start_datetime <= end_date)

    if featured_only:
        query = query.filter(Event.is_featured == True)

    # Full-text search
    if q:
        search_query = func.plainto_tsquery('english', q)
        query = query.filter(
            func.to_tsvector('english', Event.title + ' ' + func.coalesce(Event.description, '')).op('@@')(search_query)
        )

    # Location filter
    distance_km_col = None
    if lat is not None and lng is not None:
        point = func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326)

        if radius_km:
            radius_m = radius_km * 1000
            query = query.filter(
                func.ST_DWithin(Event.location, point, radius_m)
            )

        # Calculate distance for sorting
        distance_km_col = (func.ST_Distance(Event.location, point) / 1000).label('distance_km')
        query = query.add_columns(distance_km_col)
        query = query.order_by(distance_km_col)
    else:
        # Default sort: featured first, then by start date
        query = query.order_by(Event.is_featured.desc(), Event.start_datetime.asc())

    # Get total count
    if lat is not None and lng is not None:
        count_query = query.with_entities(func.count(Event.id))
        total = db.execute(count_query.statement).scalar() or 0
    else:
        total = query.count()

    # Pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    # Execute query
    results = query.all()

    # Build response
    events = []
    for result in results:
        if lat is not None and lng is not None:
            event, distance = result
            events.append(event_to_response(event, distance_km=distance))
        else:
            events.append(event_to_response(result))

    total_pages = (total + limit - 1) // limit

    return EventListResponse(
        events=events,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(event_id: UUID, db: Session = Depends(get_db)):
    """Get a single event by ID"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event_to_response(event)


@router.post("/submit", response_model=EventResponse, status_code=201)
async def submit_event(event_data: EventSubmit, db: Session = Depends(get_db)):
    """
    Submit a new event for review.
    Events submitted through this endpoint will have status='pending' and need admin approval.
    """
    # Create geography point from lat/lng
    location_wkt = f"POINT({event_data.longitude} {event_data.latitude})"

    event = Event(
        title=event_data.title,
        description=event_data.description,
        start_datetime=event_data.start_datetime,
        end_datetime=event_data.end_datetime,
        venue_name=event_data.venue_name,
        address=event_data.address,
        location=location_wkt,
        district=event_data.district,
        category=event_data.category,
        tags=event_data.tags,
        image_url=event_data.image_url,
        price_info=event_data.price_info,
        organizer_name=event_data.organizer_name,
        source='manual',
        status='pending',
        is_featured=False,
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return event_to_response(event)


@router.get("/districts/list", response_model=list[str])
async def list_districts(db: Session = Depends(get_db)):
    """Get list of all districts with events"""
    result = db.query(Event.district).filter(
        Event.status == 'approved',
        Event.district.isnot(None)
    ).distinct().order_by(Event.district).all()

    return [r[0] for r in result if r[0]]


@router.get("/categories/list", response_model=list[str])
async def list_categories(db: Session = Depends(get_db)):
    """Get list of all categories with events"""
    result = db.query(Event.category).filter(
        Event.status == 'approved',
        Event.category.isnot(None)
    ).distinct().order_by(Event.category).all()

    return [r[0] for r in result if r[0]]
