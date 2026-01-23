'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import api, { Event } from '@/lib/api';
import { format } from 'date-fns';
import {
  MapPin,
  Calendar,
  Clock,
  Tag,
  ExternalLink,
  ArrowLeft,
  Share2,
  DollarSign,
  User,
} from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';

export default function EventDetailPage() {
  const params = useParams();
  const eventId = params.id as string;

  const [event, setEvent] = useState<Event | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchEvent = async () => {
      try {
        setLoading(true);
        const data = await api.getEvent(eventId);
        setEvent(data);
      } catch (err) {
        setError('Event not found');
        console.error('Error fetching event:', err);
      } finally {
        setLoading(false);
      }
    };

    if (eventId) {
      fetchEvent();
    }
  }, [eventId]);

  const handleShare = async () => {
    if (navigator.share && event) {
      try {
        await navigator.share({
          title: event.title,
          text: event.description || `Check out ${event.title}`,
          url: window.location.href,
        });
      } catch (err) {
        // User cancelled or share failed
        console.log('Share cancelled');
      }
    } else {
      // Fallback: copy to clipboard
      navigator.clipboard.writeText(window.location.href);
      alert('Link copied to clipboard!');
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="animate-pulse">
          <div className="h-8 w-32 bg-gray-700 rounded mb-8"></div>
          <div className="h-96 bg-gray-700 rounded-xl mb-8"></div>
          <div className="h-10 w-3/4 bg-gray-700 rounded mb-4"></div>
          <div className="h-6 w-1/2 bg-gray-700 rounded mb-8"></div>
          <div className="space-y-4">
            <div className="h-4 bg-gray-700 rounded"></div>
            <div className="h-4 bg-gray-700 rounded"></div>
            <div className="h-4 w-2/3 bg-gray-700 rounded"></div>
          </div>
        </div>
      </div>
    );
  }

  if (error || !event) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <Link
          href="/"
          className="inline-flex items-center text-gray-400 hover:text-white mb-8"
        >
          <ArrowLeft className="w-5 h-5 mr-2" />
          Back to events
        </Link>
        <div className="text-center py-20">
          <h1 className="text-2xl font-bold mb-4">Event not found</h1>
          <p className="text-gray-400">This event may have been removed or doesn&apos;t exist.</p>
        </div>
      </div>
    );
  }

  const formatDate = (dateString: string) => {
    return format(new Date(dateString), 'EEEE, MMMM d, yyyy');
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

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Back button */}
      <Link
        href="/"
        className="inline-flex items-center text-gray-400 hover:text-white mb-8 transition-colors"
      >
        <ArrowLeft className="w-5 h-5 mr-2" />
        Back to events
      </Link>

      {/* Hero image */}
      <div className="relative h-96 rounded-xl overflow-hidden mb-8">
        {event.image_url ? (
          <Image
            src={event.image_url}
            alt={event.title}
            fill
            className="object-cover"
            priority
          />
        ) : (
          <div className="w-full h-full bg-gradient-to-br from-primary-900 to-gray-800 flex items-center justify-center">
            <span className="text-8xl">🎉</span>
          </div>
        )}

        {/* Featured badge */}
        {event.is_featured && (
          <div className="absolute top-4 left-4 bg-yellow-500 text-black px-3 py-1.5 rounded-full font-bold flex items-center gap-2">
            ⭐ Featured Event
          </div>
        )}

        {/* Share button */}
        <button
          onClick={handleShare}
          className="absolute top-4 right-4 bg-black/50 backdrop-blur-sm p-3 rounded-full hover:bg-black/70 transition-colors"
        >
          <Share2 className="w-5 h-5" />
        </button>
      </div>

      {/* Content */}
      <div className="grid lg:grid-cols-3 gap-8">
        {/* Main content */}
        <div className="lg:col-span-2">
          {/* Category & tags */}
          <div className="flex flex-wrap gap-2 mb-4">
            {event.category && (
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${categoryColors[event.category] || 'bg-gray-500/20 text-gray-400'}`}>
                {event.category}
              </span>
            )}
            {event.tags?.map((tag, index) => (
              <span
                key={index}
                className="bg-gray-700 text-gray-300 px-3 py-1 rounded-full text-sm"
              >
                #{tag}
              </span>
            ))}
          </div>

          {/* Title */}
          <h1 className="text-4xl font-bold mb-6">{event.title}</h1>

          {/* Description */}
          {event.description && (
            <div className="prose prose-invert max-w-none mb-8">
              <p className="text-gray-300 text-lg leading-relaxed whitespace-pre-wrap">
                {event.description}
              </p>
            </div>
          )}

          {/* Source link */}
          {event.source_url && (
            <a
              href={event.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-primary-400 hover:text-primary-300 transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              View original source
            </a>
          )}
        </div>

        {/* Sidebar */}
        <div className="lg:col-span-1">
          <div className="bg-gray-800 rounded-xl p-6 sticky top-24 space-y-6">
            {/* Date & Time */}
            <div>
              <h3 className="text-gray-400 text-sm uppercase tracking-wide mb-3">When</h3>
              <div className="flex items-start gap-3">
                <Calendar className="w-5 h-5 text-primary-400 mt-0.5" />
                <div>
                  <p className="font-medium">{formatDate(event.start_datetime)}</p>
                  <p className="text-gray-400">
                    {formatTime(event.start_datetime)}
                    {event.end_datetime && ` - ${formatTime(event.end_datetime)}`}
                  </p>
                </div>
              </div>
            </div>

            {/* Location */}
            {(event.venue_name || event.address) && (
              <div>
                <h3 className="text-gray-400 text-sm uppercase tracking-wide mb-3">Where</h3>
                <div className="flex items-start gap-3">
                  <MapPin className="w-5 h-5 text-primary-400 mt-0.5" />
                  <div>
                    {event.venue_name && <p className="font-medium">{event.venue_name}</p>}
                    {event.address && <p className="text-gray-400">{event.address}</p>}
                    {event.district && (
                      <p className="text-gray-500 text-sm mt-1">{event.district}</p>
                    )}
                  </div>
                </div>
                {event.latitude && event.longitude && (
                  <a
                    href={`https://www.google.com/maps/search/?api=1&query=${event.latitude},${event.longitude}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 text-primary-400 hover:text-primary-300 text-sm mt-3 transition-colors"
                  >
                    <ExternalLink className="w-4 h-4" />
                    Open in Google Maps
                  </a>
                )}
              </div>
            )}

            {/* Price */}
            {event.price_info && (
              <div>
                <h3 className="text-gray-400 text-sm uppercase tracking-wide mb-3">Price</h3>
                <div className="flex items-center gap-3">
                  <DollarSign className="w-5 h-5 text-primary-400" />
                  <p className="font-medium text-lg">{event.price_info}</p>
                </div>
              </div>
            )}

            {/* Organizer */}
            {event.organizer_name && (
              <div>
                <h3 className="text-gray-400 text-sm uppercase tracking-wide mb-3">Organizer</h3>
                <div className="flex items-center gap-3">
                  <User className="w-5 h-5 text-primary-400" />
                  <p className="font-medium">{event.organizer_name}</p>
                </div>
              </div>
            )}

            {/* CTA */}
            <div className="pt-4 border-t border-gray-700">
              <Link
                href="/map"
                className="block w-full bg-primary-600 hover:bg-primary-700 text-center py-3 rounded-lg font-medium transition-colors"
              >
                View on Map
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
