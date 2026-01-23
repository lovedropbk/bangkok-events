'use client';

import { Event } from '@/lib/api';
import { format } from 'date-fns';
import { MapPin, Calendar, Tag, Star, ExternalLink } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';

interface EventCardProps {
  event: Event;
}

export default function EventCard({ event }: EventCardProps) {
  const formatDate = (dateString: string) => {
    return format(new Date(dateString), 'EEE, MMM d');
  };

  const formatTime = (dateString: string) => {
    return format(new Date(dateString), 'h:mm a');
  };

  const categoryColors: Record<string, string> = {
    party: 'bg-pink-500/20 text-pink-400',
    music: 'bg-purple-500/20 text-purple-400',
    art: 'bg-blue-500/20 text-blue-400',
    food: 'bg-orange-500/20 text-orange-400',
    wellness: 'bg-green-500/20 text-green-400',
    workshop: 'bg-yellow-500/20 text-yellow-400',
  };

  const getCategoryColor = (category: string | null) => {
    return category ? categoryColors[category] || 'bg-gray-500/20 text-gray-400' : 'bg-gray-500/20 text-gray-400';
  };

  return (
    <Link href={`/events/${event.id}`}>
      <div className="bg-gray-800 rounded-xl overflow-hidden hover:ring-2 hover:ring-primary-500/50 transition-all duration-200 cursor-pointer group h-full flex flex-col">
        {/* Image */}
        <div className="relative h-48 overflow-hidden">
          {event.image_url ? (
            <Image
              src={event.image_url}
              alt={event.title}
              fill
              className="object-cover group-hover:scale-105 transition-transform duration-300"
            />
          ) : (
            <div className="w-full h-full bg-gradient-to-br from-primary-900 to-gray-800 flex items-center justify-center">
              <span className="text-4xl">🎉</span>
            </div>
          )}

          {/* Featured badge */}
          {event.is_featured && (
            <div className="absolute top-3 left-3 bg-yellow-500 text-black px-2 py-1 rounded-full text-xs font-bold flex items-center gap-1">
              <Star className="w-3 h-3" />
              Featured
            </div>
          )}

          {/* Category badge */}
          {event.category && (
            <div className={`absolute top-3 right-3 px-2 py-1 rounded-full text-xs font-medium ${getCategoryColor(event.category)}`}>
              {event.category}
            </div>
          )}

          {/* Distance badge */}
          {event.distance_km !== null && (
            <div className="absolute bottom-3 right-3 bg-black/70 backdrop-blur-sm px-2 py-1 rounded-full text-xs">
              {event.distance_km.toFixed(1)} km
            </div>
          )}
        </div>

        {/* Content */}
        <div className="p-4 flex-1 flex flex-col">
          <h3 className="font-bold text-lg mb-2 line-clamp-2 group-hover:text-primary-400 transition-colors">
            {event.title}
          </h3>

          {/* Date & Time */}
          <div className="flex items-center text-gray-400 text-sm mb-2">
            <Calendar className="w-4 h-4 mr-2 flex-shrink-0" />
            <span>
              {formatDate(event.start_datetime)} · {formatTime(event.start_datetime)}
            </span>
          </div>

          {/* Location */}
          {(event.venue_name || event.district) && (
            <div className="flex items-center text-gray-400 text-sm mb-3">
              <MapPin className="w-4 h-4 mr-2 flex-shrink-0" />
              <span className="truncate">
                {event.venue_name || event.district}
              </span>
            </div>
          )}

          {/* Tags */}
          {event.tags && event.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-3">
              {event.tags.slice(0, 3).map((tag, index) => (
                <span
                  key={index}
                  className="bg-gray-700 text-gray-300 px-2 py-0.5 rounded text-xs"
                >
                  #{tag}
                </span>
              ))}
              {event.tags.length > 3 && (
                <span className="text-gray-500 text-xs">+{event.tags.length - 3}</span>
              )}
            </div>
          )}

          {/* Footer */}
          <div className="mt-auto pt-3 border-t border-gray-700 flex items-center justify-between">
            {event.price_info && (
              <span className="text-primary-400 font-medium text-sm">
                {event.price_info}
              </span>
            )}
            {event.source && event.source !== 'manual' && (
              <span className="text-gray-500 text-xs flex items-center gap-1">
                <ExternalLink className="w-3 h-3" />
                {event.source}
              </span>
            )}
          </div>
        </div>
      </div>
    </Link>
  );
}
