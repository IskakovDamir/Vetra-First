"""
🌍 TIMEZONE DETECTION UTILITY for Vetra AI
Automatically detects user timezone from Google Calendar settings
Supports multi-user deployment with different timezones
"""

import logging
import pytz
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

def get_user_timezone_from_calendar(calendar_service, user_id: int) -> str:
    """
    🌍 Get user's timezone from their Google Calendar settings
    
    Args:
        calendar_service: Google Calendar API service
        user_id: Telegram user ID for logging
    
    Returns:
        User's timezone string (e.g., 'Europe/London', 'America/New_York')
    """
    try:
        # Get the primary calendar
        calendar_list = calendar_service.calendarList().list().execute()
        
        for calendar in calendar_list.get('items', []):
            if calendar.get('primary', False):
                timezone = calendar.get('timeZone', 'UTC')
                logger.info(f"✅ User {user_id} timezone detected: {timezone}")
                return timezone
        
        # Fallback to settings if no primary calendar found
        try:
            settings = calendar_service.settings().list().execute()
            for setting in settings.get('items', []):
                if setting.get('id') == 'timezone':
                    timezone = setting.get('value', 'UTC')
                    logger.info(f"✅ User {user_id} timezone from settings: {timezone}")
                    return timezone
        except Exception as e:
            logger.warning(f"⚠️ Could not get timezone from settings: {e}")
        
        logger.warning(f"⚠️ No timezone found for user {user_id}, using UTC")
        return 'UTC'
        
    except Exception as e:
        logger.error(f"❌ Error getting timezone for user {user_id}: {e}")
        return 'UTC'

def validate_timezone(timezone_str: str) -> str:
    """
    ✅ Validate and normalize timezone string
    
    Args:
        timezone_str: Timezone string to validate
    
    Returns:
        Valid timezone string or 'UTC' if invalid
    """
    try:
        # Test if timezone is valid
        tz = pytz.timezone(timezone_str)
        logger.info(f"✅ Timezone '{timezone_str}' is valid")
        return timezone_str
    except pytz.UnknownTimeZoneError:
        logger.warning(f"⚠️ Unknown timezone '{timezone_str}', using UTC")
        return 'UTC'

def get_timezone_info(timezone_str: str) -> dict:
    """
    📊 Get detailed timezone information
    
    Args:
        timezone_str: Timezone string
    
    Returns:
        Dictionary with timezone details
    """
    try:
        tz = pytz.timezone(timezone_str)
        now = datetime.now(tz)
        
        return {
            'timezone': timezone_str,
            'current_time': now.strftime('%H:%M'),
            'current_date': now.strftime('%Y-%m-%d'),
            'utc_offset': now.strftime('%z'),
            'dst_active': bool(now.dst()),
            'timezone_name': now.tzname(),
        }
    except Exception as e:
        logger.error(f"❌ Error getting timezone info: {e}")
        return {
            'timezone': 'UTC',
            'current_time': datetime.utcnow().strftime('%H:%M'),
            'current_date': datetime.utcnow().strftime('%Y-%m-%d'),
            'utc_offset': '+0000',
            'dst_active': False,
            'timezone_name': 'UTC',
        }

def format_time_for_user(dt: datetime, user_timezone: str) -> str:
    """
    🕐 Format datetime for user's timezone
    
    Args:
        dt: Datetime object
        user_timezone: User's timezone string
    
    Returns:
        Formatted time string
    """
    try:
        tz = pytz.timezone(user_timezone)
        
        # Convert to user's timezone if needed
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        
        user_dt = dt.astimezone(tz)
        
        return user_dt.strftime('%H:%M %Z')
        
    except Exception as e:
        logger.error(f"❌ Error formatting time: {e}")
        return dt.strftime('%H:%M UTC')

# Common timezone mappings for user-friendly names
TIMEZONE_ALIASES = {
    # Europe
    'london': 'Europe/London',
    'paris': 'Europe/Paris',
    'berlin': 'Europe/Berlin',
    'moscow': 'Europe/Moscow',
    'rome': 'Europe/Rome',
    'madrid': 'Europe/Madrid',
    
    # Asia
    'tokyo': 'Asia/Tokyo',
    'beijing': 'Asia/Shanghai',
    'shanghai': 'Asia/Shanghai',
    'delhi': 'Asia/Kolkata',
    'mumbai': 'Asia/Kolkata',
    'dubai': 'Asia/Dubai',
    'singapore': 'Asia/Singapore',
    'hong_kong': 'Asia/Hong_Kong',
    'almaty': 'Asia/Almaty',
    'tashkent': 'Asia/Tashkent',
    'astana': 'Asia/Almaty',
    
    # Americas
    'new_york': 'America/New_York',
    'los_angeles': 'America/Los_Angeles',
    'chicago': 'America/Chicago',
    'toronto': 'America/Toronto',
    'vancouver': 'America/Vancouver',
    'mexico_city': 'America/Mexico_City',
    'sao_paulo': 'America/Sao_Paulo',
    'buenos_aires': 'America/Argentina/Buenos_Aires',
    
    # Australia/Oceania
    'sydney': 'Australia/Sydney',
    'melbourne': 'Australia/Melbourne',
    'perth': 'Australia/Perth',
    'auckland': 'Pacific/Auckland',
    
    # Africa
    'cairo': 'Africa/Cairo',
    'lagos': 'Africa/Lagos',
    'johannesburg': 'Africa/Johannesburg',
}

def resolve_timezone_alias(timezone_input: str) -> str:
    """
    🔍 Resolve timezone alias to proper timezone string
    
    Args:
        timezone_input: User input (could be alias or proper timezone)
    
    Returns:
        Proper timezone string
    """
    # Clean input
    clean_input = timezone_input.lower().replace(' ', '_').replace('-', '_')
    
    # Check if it's an alias
    if clean_input in TIMEZONE_ALIASES:
        resolved = TIMEZONE_ALIASES[clean_input]
        logger.info(f"✅ Resolved timezone alias '{timezone_input}' to '{resolved}'")
        return resolved
    
    # Check if it's already a valid timezone
    try:
        pytz.timezone(timezone_input)
        return timezone_input
    except pytz.UnknownTimeZoneError:
        pass
    
    # Try with common prefixes
    common_prefixes = ['Europe/', 'Asia/', 'America/', 'Australia/', 'Africa/', 'Pacific/']
    for prefix in common_prefixes:
        candidate = prefix + timezone_input.replace(' ', '_').title()
        try:
            pytz.timezone(candidate)
            logger.info(f"✅ Resolved timezone '{timezone_input}' to '{candidate}'")
            return candidate
        except pytz.UnknownTimeZoneError:
            continue
    
    logger.warning(f"⚠️ Could not resolve timezone '{timezone_input}', using UTC")
    return 'UTC'

def get_supported_timezones() -> list:
    """
    📋 Get list of commonly used timezones for selection
    
    Returns:
        List of timezone dictionaries with display names
    """
    common_timezones = [
        # Europe
        {'id': 'Europe/London', 'name': 'London (GMT/BST)', 'region': 'Europe'},
        {'id': 'Europe/Paris', 'name': 'Paris (CET/CEST)', 'region': 'Europe'},
        {'id': 'Europe/Berlin', 'name': 'Berlin (CET/CEST)', 'region': 'Europe'},
        {'id': 'Europe/Moscow', 'name': 'Moscow (MSK)', 'region': 'Europe'},
        {'id': 'Europe/Rome', 'name': 'Rome (CET/CEST)', 'region': 'Europe'},
        
        # Asia
        {'id': 'Asia/Almaty', 'name': 'Almaty (ALMT)', 'region': 'Asia'},
        {'id': 'Asia/Tashkent', 'name': 'Tashkent (UZT)', 'region': 'Asia'},
        {'id': 'Asia/Tokyo', 'name': 'Tokyo (JST)', 'region': 'Asia'},
        {'id': 'Asia/Shanghai', 'name': 'Beijing/Shanghai (CST)', 'region': 'Asia'},
        {'id': 'Asia/Kolkata', 'name': 'Delhi/Mumbai (IST)', 'region': 'Asia'},
        {'id': 'Asia/Dubai', 'name': 'Dubai (GST)', 'region': 'Asia'},
        {'id': 'Asia/Singapore', 'name': 'Singapore (SGT)', 'region': 'Asia'},
        
        # Americas
        {'id': 'America/New_York', 'name': 'New York (EST/EDT)', 'region': 'Americas'},
        {'id': 'America/Los_Angeles', 'name': 'Los Angeles (PST/PDT)', 'region': 'Americas'},
        {'id': 'America/Chicago', 'name': 'Chicago (CST/CDT)', 'region': 'Americas'},
        {'id': 'America/Toronto', 'name': 'Toronto (EST/EDT)', 'region': 'Americas'},
        {'id': 'America/Mexico_City', 'name': 'Mexico City (CST/CDT)', 'region': 'Americas'},
        
        # Australia/Oceania
        {'id': 'Australia/Sydney', 'name': 'Sydney (AEST/AEDT)', 'region': 'Australia'},
        {'id': 'Australia/Melbourne', 'name': 'Melbourne (AEST/AEDT)', 'region': 'Australia'},
        {'id': 'Pacific/Auckland', 'name': 'Auckland (NZST/NZDT)', 'region': 'Oceania'},
        
        # UTC
        {'id': 'UTC', 'name': 'UTC (Coordinated Universal Time)', 'region': 'UTC'},
    ]
    
    return common_timezones