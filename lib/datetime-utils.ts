/**
 * Utility functions for date/time formatting with Indian Standard Time (IST)
 */

/**
 * Parse a timestamp string to ensure it's interpreted as UTC
 * This prevents timezone interpretation issues
 */
function parseUTCTimestamp(timestamp: string | Date): Date {
  if (typeof timestamp === 'object') {
    return timestamp;
  }

  // If it's an ISO string without timezone, treat it as UTC
  if (typeof timestamp === 'string') {
    // Add Z if not present to explicitly mark as UTC
    if (!timestamp.endsWith('Z') && !timestamp.includes('+') && !timestamp.includes('-')) {
      // Check if it's just a date or datetime
      return new Date(timestamp + 'Z');
    }
    return new Date(timestamp);
  }

  return new Date();
}

/**
 * Format a date to Indian Standard Time (IST)
 * IST is UTC+5:30
 * 
 * @param date - Date object or ISO string (assumed UTC if no timezone specified)
 * @param format - 'short' for DD/MM/YYYY HH:MM:SS or 'long' for full format
 * @returns Formatted string in IST
 */
export function formatToIST(date: string | Date, format: 'short' | 'long' = 'long'): string {
  try {
    // Ensure the date is parsed as UTC
    const dateObj = parseUTCTimestamp(date);
    
    // Validate date
    if (isNaN(dateObj.getTime())) {
      return 'Invalid Date';
    }
    
    // Format options for Indian Standard Time
    const options: Intl.DateTimeFormatOptions = {
      timeZone: 'Asia/Kolkata',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    };
    
    const istFormatter = new Intl.DateTimeFormat('en-IN', options);
    const parts = istFormatter.formatToParts(dateObj);
    
    const partMap = parts.reduce((acc: Record<string, string>, part) => {
      acc[part.type] = part.value;
      return acc;
    }, {});
    
    if (format === 'short') {
      return `${partMap.day}/${partMap.month}/${partMap.year} ${partMap.hour}:${partMap.minute}:${partMap.second}`;
    }
    
    // Long format with day name
    const dayName = dateObj.toLocaleDateString('en-IN', { 
      timeZone: 'Asia/Kolkata',
      weekday: 'short' 
    });
    
    return `${dayName}, ${partMap.day}/${partMap.month}/${partMap.year} ${partMap.hour}:${partMap.minute}:${partMap.second} IST`;
  } catch (error) {
    console.error('Error formatting date to IST:', error);
    return 'Invalid Date';
  }
}

/**
 * Get current time in Indian Standard Time
 * @returns Current time formatted as IST string
 */
export function getCurrentTimeIST(): string {
  return formatToIST(new Date(), 'short');
}

/**
 * Format time for display in UI (DD/MM/YYYY HH:MM:SS IST)
 * @param date - Date object or ISO string (assumed UTC if no timezone specified)
 * @returns Formatted time string
 */
export function formatTimeForUI(date: string | Date): string {
  return formatToIST(date, 'short') + ' IST';
}

/**
 * Get time ago string in Indian context
 * @param date - Date object or ISO string
 * @returns String like "5 minutes ago", "2 hours ago", etc.
 */
export function getTimeAgo(date: string | Date): string {
  try {
    const dateObj = typeof date === 'string' ? new Date(date) : date;
    const now = new Date();
    const seconds = Math.floor((now.getTime() - dateObj.getTime()) / 1000);
    
    if (seconds < 60) return 'just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)} minute${Math.floor(seconds / 60) > 1 ? 's' : ''} ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)} hour${Math.floor(seconds / 3600) > 1 ? 's' : ''} ago`;
    if (seconds < 604800) return `${Math.floor(seconds / 86400)} day${Math.floor(seconds / 86400) > 1 ? 's' : ''} ago`;
    
    return formatToIST(date, 'short');
  } catch (error) {
    console.error('Error calculating time ago:', error);
    return 'Unknown';
  }
}
