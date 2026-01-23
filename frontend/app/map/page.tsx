'use client';

import { useState, useEffect, useCallback } from 'react';
import api, { Event } from '@/lib/api';
import EventMap from '@/components/EventMap';
import { format } from 'date-fns';
import { MapPin, Calendar, X, Loader2 } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';

export default function MapPage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedEvent, setSelectedEvent] = useState<Event | null>(null);
  const [userLocation, setUserLocation] = useState<[number, number] | null>(null);

  useEffect(() => {
    const fetchEvents = async () => {
      try {
        setLoading(true);
        const response = await api.getEvents({ limit: 100 });
        setEvents(response.events);
      } catch (err) {
        console.error('Error fetching events:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchEvents();

    // Try to get user location
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setUserLocation([position.coords.longitude, position.coords.latitude]);
        },
        (err) => {
          console.log('Geolocation not available:', err);
        }
      );
    }
  }, []);

  const handleEventClick = useCallback((event: Event) => {
    setSelectedEvent(event);
  }, []);

  const formatDate = (dateString: string) => {
    return format(new Date(dateString), 'EEE, MMM d');
  };

  const formatTime = (dateString: string) => {
    return format(new Date(dateString), 'h:mm a');
  };

  return (
    <div className="h-[calc(100vh-64px)] flex">
      {/* Map */}
      <div className="flex-1 relative">
        {loading ? (
          <div className="w-full h-full bg-gray-800 flex items-center justify-center">
            <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
          </div>
        ) : (
          <EventMap
            events={events}
            center={userLocation || [100.5018, 13.7563]}
            zoom={13}
            onEventClick={handleEventClick}
            selectedEventId={selectedEvent?.id}
          />
        )}

        {/* Legend */}
        <div className="absolute bottom-4 left-4 bg-gray-900/90 backdrop-blur-sm rounded-lg p-4">
          <h4 className="text-sm font-medium mb-2">Categories</h4>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="flex items-center gap-1">🎉 Party</span>
            <span className="flex items-center gap-1">🎵 Music</span>
            <span className="flex items-center gap-1">🎨 Art</span>
            <span className="flex items-center gap-1">🍜 Food</span>
            <span className="flex items-center gap-1">🧘 Wellness</span>
          </div>
        </div>
      </div>

      {/* Sidebar - selected event */}
      {selectedEvent && (
        <div className="w-96 bg-gray-800 border-l border-gray-700 overflow-y-auto">
          {/* Close button */}
          <button
            onClick={() => setSelectedEvent(null)}
            className="absolute top-4 right-4 p-2 hover:bg-gray-700 rounded-lg z-10"
          >
            <X className="w-5 h-5" />
          </button>

          {/* Image */}
          <div className="relative h-48">
            {selectedEvent.image_url ? (
              <Image
                src={selectedEvent.image_url}
                alt={selectedEvent.title}
                fill
                className="object-cover"
              />
            ) : (
              <div className="w-full h-full bg-gradient-to-br from-primary-900 to-gray-800 flex items-center justify-center">
                <span className="text-6xl">🎉</span>
              </div>
            )}
          </div>

          {/* Content */}
          <div className="p-6">
            {/* Category */}
            {selectedEvent.category && (
              <span className="inline-block bg-primary-500/20 text-primary-400 px-2 py-1 rounded text-xs font-medium mb-3">
                {selectedEvent.category}
              </span>
            )}

            <h2 className="text-xl font-bold mb-4">{selectedEvent.title}</h2>

            {/* Date & Time */}
            <div className="flex items-center text-gray-400 mb-3">
              <Calendar className="w-4 h-4 mr-2" />
              <span>
                {formatDate(selectedEvent.start_datetime)} · {formatTime(selectedEvent.start_datetime)}
              </span>
            </div>

            {/* Location */}
            {(selectedEvent.venue_name || selectedEvent.address) && (
              <div className="flex items-start text-gray-400 mb-4">
                <MapPin className="w-4 h-4 mr-2 mt-0.5" />
                <div>
                  {selectedEvent.venue_name && (
                    <p className="text-white">{selectedEvent.venue_name}</p>
                  )}
                  {selectedEvent.address && <p className="text-sm">{selectedEvent.address}</p>}
                </div>
              </div>
            )}

            {/* Description */}
            {selectedEvent.description && (
              <p className="text-gray-400 text-sm mb-4 line-clamp-4">
                {selectedEvent.description}
              </p>
            )}

            {/* Price */}
            {selectedEvent.price_info && (
              <p className="text-primary-400 font-medium mb-4">
                {selectedEvent.price_info}
              </p>
            )}

            {/* Tags */}
            {selectedEvent.tags && selectedEvent.tags.length > 0 && (
              <div className="flex flex-wrap gap-1 mb-6">
                {selectedEvent.tags.map((tag, index) => (
                  <span
                    key={index}
                    className="bg-gray-700 text-gray-300 px-2 py-0.5 rounded text-xs"
                  >
                    #{tag}
                  </span>
                ))}
              </div>
            )}

            {/* Actions */}
            <div className="space-y-2">
              <Link
                href={`/events/${selectedEvent.id}`}
                className="block w-full bg-primary-600 hover:bg-primary-700 text-center py-3 rounded-lg font-medium transition-colors"
              >
                View Details
              </Link>
              {selectedEvent.latitude && selectedEvent.longitude && (
                <a
                  href={`https://www.google.com/maps/dir/?api=1&destination=${selectedEvent.latitude},${selectedEvent.longitude}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block w-full bg-gray-700 hover:bg-gray-600 text-center py-3 rounded-lg font-medium transition-colors"
                >
                  Get Directions
                </a>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
