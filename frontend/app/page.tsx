'use client';

import { useState, useEffect, useCallback } from 'react';
import api, { Event, EventFilters } from '@/lib/api';
import EventCard from '@/components/EventCard';
import EventFiltersComponent from '@/components/EventFilters';
import { Loader2 } from 'lucide-react';

export default function HomePage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<EventFilters>({
    page: 1,
    limit: 20,
  });
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

  const fetchEvents = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.getEvents(filters);
      setEvents(response.events);
      setTotalPages(response.total_pages);
      setTotal(response.total);
    } catch (err) {
      setError('Failed to load events. Make sure the backend is running.');
      console.error('Error fetching events:', err);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  const handleFilterChange = (newFilters: Partial<EventFilters>) => {
    setFilters(prev => ({
      ...prev,
      ...newFilters,
      page: 1, // Reset to first page when filters change
    }));
  };

  const handlePageChange = (page: number) => {
    setFilters(prev => ({ ...prev, page }));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleNearMe = () => {
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setFilters(prev => ({
            ...prev,
            lat: position.coords.latitude,
            lng: position.coords.longitude,
            radius_km: 5,
            page: 1,
          }));
        },
        (err) => {
          console.error('Geolocation error:', err);
          alert('Could not get your location. Please enable location services.');
        }
      );
    } else {
      alert('Geolocation is not supported by your browser.');
    }
  };

  const clearLocationFilter = () => {
    setFilters(prev => {
      const { lat, lng, radius_km, ...rest } = prev;
      return { ...rest, page: 1 };
    });
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2">
          Discover Bangkok&apos;s{' '}
          <span className="bg-gradient-to-r from-primary-400 to-primary-600 bg-clip-text text-transparent">
            Hidden Events
          </span>
        </h1>
        <p className="text-gray-400 text-lg">
          Rooftop parties, underground shows, pop-ups, and more
        </p>
      </div>

      {/* Filters */}
      <EventFiltersComponent
        filters={filters}
        onFilterChange={handleFilterChange}
        onNearMe={handleNearMe}
        onClearLocation={clearLocationFilter}
      />

      {/* Results count */}
      {!loading && !error && (
        <p className="text-gray-400 mb-6">
          {total} event{total !== 1 ? 's' : ''} found
          {filters.lat && filters.lng && ` within ${filters.radius_km || 10}km`}
        </p>
      )}

      {/* Loading state */}
      {loading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
          <span className="ml-3 text-gray-400">Loading events...</span>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-6 text-center">
          <p className="text-red-400">{error}</p>
          <button
            onClick={fetchEvents}
            className="mt-4 bg-red-600 hover:bg-red-700 px-4 py-2 rounded-lg transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* Event grid */}
      {!loading && !error && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {events.map((event) => (
              <EventCard key={event.id} event={event} />
            ))}
          </div>

          {/* Empty state */}
          {events.length === 0 && (
            <div className="text-center py-20">
              <p className="text-gray-400 text-lg">No events found matching your filters.</p>
              <button
                onClick={() => setFilters({ page: 1, limit: 20 })}
                className="mt-4 text-primary-400 hover:text-primary-300 underline"
              >
                Clear all filters
              </button>
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex justify-center items-center space-x-2 mt-10">
              <button
                onClick={() => handlePageChange(filters.page! - 1)}
                disabled={filters.page === 1}
                className="px-4 py-2 rounded-lg bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-700 transition-colors"
              >
                Previous
              </button>
              <span className="text-gray-400">
                Page {filters.page} of {totalPages}
              </span>
              <button
                onClick={() => handlePageChange(filters.page! + 1)}
                disabled={filters.page === totalPages}
                className="px-4 py-2 rounded-lg bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-700 transition-colors"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
