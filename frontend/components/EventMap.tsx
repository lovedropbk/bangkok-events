'use client';

import { useEffect, useRef, useState } from 'react';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';
import { Event } from '@/lib/api';

interface EventMapProps {
  events: Event[];
  center?: [number, number];
  zoom?: number;
  onEventClick?: (event: Event) => void;
  selectedEventId?: string;
}

// Note: Replace with your Mapbox token or set NEXT_PUBLIC_MAPBOX_TOKEN
const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN || 'pk.your_token_here';

export default function EventMap({
  events,
  center = [100.5018, 13.7563], // Bangkok center
  zoom = 12,
  onEventClick,
  selectedEventId,
}: EventMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const markersRef = useRef<mapboxgl.Marker[]>([]);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);

  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    // Check if we have a valid token
    if (!MAPBOX_TOKEN || MAPBOX_TOKEN === 'pk.your_token_here') {
      setMapError('Please set NEXT_PUBLIC_MAPBOX_TOKEN in your environment variables');
      return;
    }

    mapboxgl.accessToken = MAPBOX_TOKEN;

    try {
      map.current = new mapboxgl.Map({
        container: mapContainer.current,
        style: 'mapbox://styles/mapbox/dark-v11',
        center: center,
        zoom: zoom,
      });

      map.current.addControl(new mapboxgl.NavigationControl(), 'top-right');

      map.current.on('load', () => {
        setMapLoaded(true);
      });

      map.current.on('error', (e) => {
        console.error('Map error:', e);
        setMapError('Failed to load map. Check your Mapbox token.');
      });
    } catch (error) {
      console.error('Map initialization error:', error);
      setMapError('Failed to initialize map');
    }

    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, []);

  // Update markers when events change
  useEffect(() => {
    if (!map.current || !mapLoaded) return;

    // Clear existing markers
    markersRef.current.forEach(marker => marker.remove());
    markersRef.current = [];

    // Add new markers
    events.forEach((event) => {
      if (event.latitude && event.longitude) {
        const el = document.createElement('div');
        el.className = 'event-marker';
        el.innerHTML = `
          <div class="w-8 h-8 rounded-full flex items-center justify-center cursor-pointer transform transition-transform hover:scale-110 ${
            event.id === selectedEventId
              ? 'bg-primary-500 ring-4 ring-primary-300'
              : event.is_featured
              ? 'bg-yellow-500'
              : 'bg-primary-600'
          }">
            <span class="text-white text-sm">${getCategoryEmoji(event.category)}</span>
          </div>
        `;

        el.addEventListener('click', () => {
          onEventClick?.(event);
        });

        const marker = new mapboxgl.Marker(el)
          .setLngLat([event.longitude, event.latitude])
          .addTo(map.current!);

        markersRef.current.push(marker);
      }
    });
  }, [events, mapLoaded, selectedEventId, onEventClick]);

  // Center on selected event
  useEffect(() => {
    if (!map.current || !selectedEventId) return;

    const event = events.find(e => e.id === selectedEventId);
    if (event?.latitude && event?.longitude) {
      map.current.flyTo({
        center: [event.longitude, event.latitude],
        zoom: 15,
        duration: 1000,
      });
    }
  }, [selectedEventId, events]);

  if (mapError) {
    return (
      <div className="w-full h-full bg-gray-800 rounded-xl flex items-center justify-center">
        <div className="text-center p-6">
          <p className="text-gray-400 mb-2">{mapError}</p>
          <p className="text-sm text-gray-500">
            Get your free token at{' '}
            <a
              href="https://mapbox.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary-400 hover:underline"
            >
              mapbox.com
            </a>
          </p>
        </div>
      </div>
    );
  }

  return <div ref={mapContainer} className="w-full h-full rounded-xl" />;
}

function getCategoryEmoji(category: string | null): string {
  const emojis: Record<string, string> = {
    party: '🎉',
    music: '🎵',
    art: '🎨',
    food: '🍜',
    wellness: '🧘',
    workshop: '📚',
  };
  return category ? emojis[category] || '📍' : '📍';
}
