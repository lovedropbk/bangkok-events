import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, DateTime, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geography
from app.database import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text)

    # When
    start_datetime = Column(DateTime(timezone=True), nullable=False)
    end_datetime = Column(DateTime(timezone=True))

    # Where
    venue_name = Column(String(255))
    address = Column(Text)
    location = Column(Geography(geometry_type='POINT', srid=4326))
    district = Column(String(100))

    # Categorization
    category = Column(String(50))
    tags = Column(ARRAY(Text))

    # Source tracking
    source = Column(String(50))
    source_url = Column(Text)
    source_id = Column(String(255))

    # Media
    image_url = Column(Text)

    # Metadata
    price_info = Column(String(100))
    organizer_name = Column(String(255))

    # Status
    status = Column(String(20), default='pending')
    is_featured = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
