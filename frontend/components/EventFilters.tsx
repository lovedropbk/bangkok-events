'use client';

import { useState, useEffect } from 'react';
import { EventFilters } from '@/lib/api';
import api from '@/lib/api';
import { Search, MapPin, X, ChevronDown } from 'lucide-react';

interface EventFiltersProps {
  filters: EventFilters;
  onFilterChange: (filters: Partial<EventFilters>) => void;
  onNearMe: () => void;
  onClearLocation: () => void;
}

export default function EventFiltersComponent({
  filters,
  onFilterChange,
  onNearMe,
  onClearLocation,
}: EventFiltersProps) {
  const [searchQuery, setSearchQuery] = useState(filters.q || '');
  const [districts, setDistricts] = useState<string[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [showMoreFilters, setShowMoreFilters] = useState(false);

  useEffect(() => {
    // Fetch available districts and categories
    const fetchOptions = async () => {
      try {
        const [districtsData, categoriesData] = await Promise.all([
          api.getDistricts(),
          api.getCategories(),
        ]);
        setDistricts(districtsData);
        setCategories(categoriesData);
      } catch (err) {
        console.error('Error fetching filter options:', err);
      }
    };
    fetchOptions();
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    onFilterChange({ q: searchQuery || undefined });
  };

  const handleDistrictChange = (district: string) => {
    onFilterChange({ district: district || undefined });
  };

  const handleCategoryChange = (category: string) => {
    onFilterChange({ category: category || undefined });
  };

  const handleDateChange = (field: 'start_date' | 'end_date', value: string) => {
    onFilterChange({ [field]: value ? new Date(value).toISOString() : undefined });
  };

  const hasLocationFilter = filters.lat !== undefined && filters.lng !== undefined;

  return (
    <div className="mb-6 space-y-4">
      {/* Search bar */}
      <form onSubmit={handleSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search events, venues, tags..."
            className="w-full bg-gray-800 border border-gray-700 rounded-lg py-3 pl-10 pr-4 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          />
        </div>
        <button
          type="submit"
          className="bg-primary-600 hover:bg-primary-700 px-6 py-3 rounded-lg font-medium transition-colors"
        >
          Search
        </button>
      </form>

      {/* Quick filters */}
      <div className="flex flex-wrap gap-3 items-center">
        {/* Near Me button */}
        <button
          onClick={hasLocationFilter ? onClearLocation : onNearMe}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
            hasLocationFilter
              ? 'bg-primary-600 text-white'
              : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
          }`}
        >
          <MapPin className="w-4 h-4" />
          {hasLocationFilter ? 'Near Me' : 'Near Me'}
          {hasLocationFilter && <X className="w-4 h-4" />}
        </button>

        {/* District filter */}
        <div className="relative">
          <select
            value={filters.district || ''}
            onChange={(e) => handleDistrictChange(e.target.value)}
            className="appearance-none bg-gray-800 border border-gray-700 rounded-lg py-2 pl-4 pr-10 text-white focus:outline-none focus:ring-2 focus:ring-primary-500 cursor-pointer"
          >
            <option value="">All Districts</option>
            {districts.map((district) => (
              <option key={district} value={district}>
                {district}
              </option>
            ))}
          </select>
          <ChevronDown className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4 pointer-events-none" />
        </div>

        {/* Category filter */}
        <div className="relative">
          <select
            value={filters.category || ''}
            onChange={(e) => handleCategoryChange(e.target.value)}
            className="appearance-none bg-gray-800 border border-gray-700 rounded-lg py-2 pl-4 pr-10 text-white focus:outline-none focus:ring-2 focus:ring-primary-500 cursor-pointer capitalize"
          >
            <option value="">All Categories</option>
            {categories.map((category) => (
              <option key={category} value={category} className="capitalize">
                {category}
              </option>
            ))}
          </select>
          <ChevronDown className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4 pointer-events-none" />
        </div>

        {/* More filters toggle */}
        <button
          onClick={() => setShowMoreFilters(!showMoreFilters)}
          className="text-gray-400 hover:text-white text-sm underline"
        >
          {showMoreFilters ? 'Less filters' : 'More filters'}
        </button>

        {/* Featured only toggle */}
        <label className="flex items-center gap-2 text-gray-300 cursor-pointer ml-auto">
          <input
            type="checkbox"
            checked={filters.featured_only || false}
            onChange={(e) => onFilterChange({ featured_only: e.target.checked || undefined })}
            className="w-4 h-4 rounded bg-gray-700 border-gray-600 text-primary-600 focus:ring-primary-500 focus:ring-offset-gray-900"
          />
          <span className="text-sm">Featured only</span>
        </label>
      </div>

      {/* Advanced filters */}
      {showMoreFilters && (
        <div className="flex flex-wrap gap-4 p-4 bg-gray-800/50 rounded-lg">
          <div className="flex items-center gap-2">
            <label className="text-gray-400 text-sm">From:</label>
            <input
              type="date"
              onChange={(e) => handleDateChange('start_date', e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded-lg py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <div className="flex items-center gap-2">
            <label className="text-gray-400 text-sm">To:</label>
            <input
              type="date"
              onChange={(e) => handleDateChange('end_date', e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded-lg py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          {hasLocationFilter && (
            <div className="flex items-center gap-2">
              <label className="text-gray-400 text-sm">Radius:</label>
              <select
                value={filters.radius_km || 5}
                onChange={(e) => onFilterChange({ radius_km: Number(e.target.value) })}
                className="bg-gray-800 border border-gray-700 rounded-lg py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="1">1 km</option>
                <option value="2">2 km</option>
                <option value="5">5 km</option>
                <option value="10">10 km</option>
                <option value="20">20 km</option>
              </select>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
