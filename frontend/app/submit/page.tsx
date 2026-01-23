'use client';

import { useState } from 'react';
import api, { EventSubmission } from '@/lib/api';
import { MapPin, Calendar, Clock, Image as ImageIcon, Check, AlertCircle } from 'lucide-react';
import Link from 'next/link';

const DISTRICTS = [
  'Sukhumvit',
  'Thonglor',
  'Ekkamai',
  'Phrom Phong',
  'Siam',
  'Silom',
  'Sathorn',
  'Bangna',
  'Central Bangkok',
  'Ratchathewi',
  'Ari',
  'Lat Phrao',
  'Other',
];

const CATEGORIES = [
  'party',
  'music',
  'art',
  'food',
  'wellness',
  'workshop',
  'market',
  'networking',
  'other',
];

export default function SubmitPage() {
  const [formData, setFormData] = useState<Partial<EventSubmission>>({
    latitude: 13.7563,
    longitude: 100.5018,
    tags: [],
  });
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tagInput, setTagInput] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Validate required fields
      if (!formData.title || !formData.start_datetime || !formData.latitude || !formData.longitude) {
        throw new Error('Please fill in all required fields');
      }

      await api.submitEvent(formData as EventSubmission);
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit event');
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleAddTag = () => {
    if (tagInput.trim() && !formData.tags?.includes(tagInput.trim())) {
      setFormData(prev => ({
        ...prev,
        tags: [...(prev.tags || []), tagInput.trim().toLowerCase()],
      }));
      setTagInput('');
    }
  };

  const handleRemoveTag = (tag: string) => {
    setFormData(prev => ({
      ...prev,
      tags: prev.tags?.filter(t => t !== tag) || [],
    }));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddTag();
    }
  };

  const handleLocationClick = () => {
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setFormData(prev => ({
            ...prev,
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          }));
        },
        (err) => {
          console.error('Geolocation error:', err);
          alert('Could not get your location. Please enter coordinates manually.');
        }
      );
    }
  };

  if (success) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16 text-center">
        <div className="bg-green-900/30 border border-green-700 rounded-xl p-8">
          <Check className="w-16 h-16 text-green-400 mx-auto mb-4" />
          <h1 className="text-2xl font-bold mb-4">Event Submitted!</h1>
          <p className="text-gray-400 mb-6">
            Your event has been submitted for review. It will appear on the site once approved by our team.
          </p>
          <div className="flex gap-4 justify-center">
            <Link
              href="/"
              className="bg-gray-700 hover:bg-gray-600 px-6 py-3 rounded-lg font-medium transition-colors"
            >
              Back to Events
            </Link>
            <button
              onClick={() => {
                setSuccess(false);
                setFormData({ latitude: 13.7563, longitude: 100.5018, tags: [] });
              }}
              className="bg-primary-600 hover:bg-primary-700 px-6 py-3 rounded-lg font-medium transition-colors"
            >
              Submit Another
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-2">Submit an Event</h1>
      <p className="text-gray-400 mb-8">
        Know about a cool event happening in Bangkok? Share it with the community!
      </p>

      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 mb-6 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
          <p className="text-red-400">{error}</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Title */}
        <div>
          <label htmlFor="title" className="block text-sm font-medium mb-2">
            Event Title <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            id="title"
            name="title"
            required
            value={formData.title || ''}
            onChange={handleInputChange}
            placeholder="e.g., Rooftop Sunset Sessions"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg py-3 px-4 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        {/* Description */}
        <div>
          <label htmlFor="description" className="block text-sm font-medium mb-2">
            Description
          </label>
          <textarea
            id="description"
            name="description"
            rows={4}
            value={formData.description || ''}
            onChange={handleInputChange}
            placeholder="Tell people what to expect..."
            className="w-full bg-gray-800 border border-gray-700 rounded-lg py-3 px-4 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
          />
        </div>

        {/* Date & Time */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="start_datetime" className="block text-sm font-medium mb-2">
              Start Date & Time <span className="text-red-400">*</span>
            </label>
            <input
              type="datetime-local"
              id="start_datetime"
              name="start_datetime"
              required
              value={formData.start_datetime?.slice(0, 16) || ''}
              onChange={(e) => {
                setFormData(prev => ({
                  ...prev,
                  start_datetime: new Date(e.target.value).toISOString(),
                }));
              }}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg py-3 px-4 text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <div>
            <label htmlFor="end_datetime" className="block text-sm font-medium mb-2">
              End Date & Time
            </label>
            <input
              type="datetime-local"
              id="end_datetime"
              name="end_datetime"
              value={formData.end_datetime?.slice(0, 16) || ''}
              onChange={(e) => {
                setFormData(prev => ({
                  ...prev,
                  end_datetime: e.target.value ? new Date(e.target.value).toISOString() : undefined,
                }));
              }}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg py-3 px-4 text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
        </div>

        {/* Venue */}
        <div>
          <label htmlFor="venue_name" className="block text-sm font-medium mb-2">
            Venue Name
          </label>
          <input
            type="text"
            id="venue_name"
            name="venue_name"
            value={formData.venue_name || ''}
            onChange={handleInputChange}
            placeholder="e.g., Vanilla Sky Rooftop"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg py-3 px-4 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        {/* Address */}
        <div>
          <label htmlFor="address" className="block text-sm font-medium mb-2">
            Address
          </label>
          <input
            type="text"
            id="address"
            name="address"
            value={formData.address || ''}
            onChange={handleInputChange}
            placeholder="Full address"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg py-3 px-4 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        {/* District & Category */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="district" className="block text-sm font-medium mb-2">
              District
            </label>
            <select
              id="district"
              name="district"
              value={formData.district || ''}
              onChange={handleInputChange}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg py-3 px-4 text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="">Select district</option>
              {DISTRICTS.map(d => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="category" className="block text-sm font-medium mb-2">
              Category
            </label>
            <select
              id="category"
              name="category"
              value={formData.category || ''}
              onChange={handleInputChange}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg py-3 px-4 text-white focus:outline-none focus:ring-2 focus:ring-primary-500 capitalize"
            >
              <option value="">Select category</option>
              {CATEGORIES.map(c => (
                <option key={c} value={c} className="capitalize">{c}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Location coordinates */}
        <div>
          <label className="block text-sm font-medium mb-2">
            Location <span className="text-red-400">*</span>
          </label>
          <div className="flex gap-4">
            <input
              type="number"
              name="latitude"
              step="any"
              required
              value={formData.latitude || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, latitude: parseFloat(e.target.value) }))}
              placeholder="Latitude"
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg py-3 px-4 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <input
              type="number"
              name="longitude"
              step="any"
              required
              value={formData.longitude || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, longitude: parseFloat(e.target.value) }))}
              placeholder="Longitude"
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg py-3 px-4 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <button
              type="button"
              onClick={handleLocationClick}
              className="bg-gray-700 hover:bg-gray-600 px-4 rounded-lg transition-colors"
              title="Use my location"
            >
              <MapPin className="w-5 h-5" />
            </button>
          </div>
          <p className="text-gray-500 text-sm mt-1">
            Tip: Right-click on Google Maps to copy coordinates
          </p>
        </div>

        {/* Tags */}
        <div>
          <label htmlFor="tags" className="block text-sm font-medium mb-2">
            Tags
          </label>
          <div className="flex gap-2 mb-2">
            <input
              type="text"
              id="tags"
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Add tags (press Enter)"
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg py-3 px-4 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <button
              type="button"
              onClick={handleAddTag}
              className="bg-gray-700 hover:bg-gray-600 px-4 rounded-lg transition-colors"
            >
              Add
            </button>
          </div>
          {formData.tags && formData.tags.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {formData.tags.map((tag, index) => (
                <span
                  key={index}
                  className="bg-gray-700 text-gray-300 px-3 py-1 rounded-full text-sm flex items-center gap-2"
                >
                  #{tag}
                  <button
                    type="button"
                    onClick={() => handleRemoveTag(tag)}
                    className="hover:text-red-400"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Price */}
        <div>
          <label htmlFor="price_info" className="block text-sm font-medium mb-2">
            Price Info
          </label>
          <input
            type="text"
            id="price_info"
            name="price_info"
            value={formData.price_info || ''}
            onChange={handleInputChange}
            placeholder="e.g., Free, 500 THB, 300-600 THB"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg py-3 px-4 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        {/* Image URL */}
        <div>
          <label htmlFor="image_url" className="block text-sm font-medium mb-2">
            Image URL
          </label>
          <input
            type="url"
            id="image_url"
            name="image_url"
            value={formData.image_url || ''}
            onChange={handleInputChange}
            placeholder="https://..."
            className="w-full bg-gray-800 border border-gray-700 rounded-lg py-3 px-4 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        {/* Organizer */}
        <div>
          <label htmlFor="organizer_name" className="block text-sm font-medium mb-2">
            Organizer Name
          </label>
          <input
            type="text"
            id="organizer_name"
            name="organizer_name"
            value={formData.organizer_name || ''}
            onChange={handleInputChange}
            placeholder="Your name or organization"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg py-3 px-4 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        {/* Contact Email */}
        <div>
          <label htmlFor="contact_email" className="block text-sm font-medium mb-2">
            Contact Email
          </label>
          <input
            type="email"
            id="contact_email"
            name="contact_email"
            value={formData.contact_email || ''}
            onChange={handleInputChange}
            placeholder="your@email.com"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg py-3 px-4 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <p className="text-gray-500 text-sm mt-1">
            Not displayed publicly. Used for event verification only.
          </p>
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-primary-600 hover:bg-primary-700 py-4 rounded-lg font-bold text-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Submitting...' : 'Submit Event for Review'}
        </button>

        <p className="text-gray-500 text-sm text-center">
          Events are reviewed before being published. This usually takes 24-48 hours.
        </p>
      </form>
    </div>
  );
}
