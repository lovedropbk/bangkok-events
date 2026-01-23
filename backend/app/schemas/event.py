from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class EventBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    start_datetime: datetime
    end_datetime: Optional[datetime] = None
    venue_name: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = None
    district: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = Field(None, max_length=50)
    tags: Optional[list[str]] = None
    image_url: Optional[str] = None
    price_info: Optional[str] = Field(None, max_length=100)
    organizer_name: Optional[str] = Field(None, max_length=255)


class EventCreate(EventBase):
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    source_url: Optional[str] = None


class EventSubmit(EventBase):
    """Schema for manual event submission by organizers"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    contact_email: Optional[str] = None


class EventUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    venue_name: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = None
    district: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = Field(None, max_length=50)
    tags: Optional[list[str]] = None
    image_url: Optional[str] = None
    price_info: Optional[str] = Field(None, max_length=100)
    organizer_name: Optional[str] = Field(None, max_length=255)
    status: Optional[str] = Field(None, max_length=20)
    is_featured: Optional[bool] = None


class EventResponse(EventBase):
    id: UUID
    source: Optional[str] = None
    source_url: Optional[str] = None
    status: str
    is_featured: bool
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_km: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    events: list[EventResponse]
    total: int
    page: int
    limit: int
    total_pages: int


class EventFilters(BaseModel):
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lng: Optional[float] = Field(None, ge=-180, le=180)
    radius_km: Optional[float] = Field(None, ge=0, le=100)
    district: Optional[str] = None
    category: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    q: Optional[str] = None
    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)
    featured_only: bool = False
