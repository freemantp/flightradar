from datetime import datetime, timezone
from typing import Tuple


def make_datetimes_comparable(dt1: datetime, dt2: datetime) -> Tuple[datetime, datetime]:
    """
    Utility function to make two datetime objects comparable by ensuring they both have
    consistent timezone information.
    
    Args:
        dt1: First datetime object
        dt2: Second datetime object
        
    Returns:
        Tuple of (dt1, dt2) where both have consistent timezone information
    """
    # Check if both have timezone info
    dt1_has_tzinfo = hasattr(dt1, 'tzinfo') and dt1.tzinfo is not None
    dt2_has_tzinfo = hasattr(dt2, 'tzinfo') and dt2.tzinfo is not None
    
    # If they're both the same (both aware or both naive), just return them
    if dt1_has_tzinfo == dt2_has_tzinfo:
        return dt1, dt2
    
    # If dt1 has timezone but dt2 doesn't, make dt2 aware
    if dt1_has_tzinfo and not dt2_has_tzinfo:
        return dt1, dt2.replace(tzinfo=timezone.utc)
    
    # If dt2 has timezone but dt1 doesn't, make dt1 aware
    if dt2_has_tzinfo and not dt1_has_tzinfo:
        return dt1.replace(tzinfo=timezone.utc), dt2
    
    # This shouldn't happen given the checks above, but just in case
    return dt1, dt2
