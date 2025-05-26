import time
from dataclasses import dataclass


@dataclass
class SourceBackoff:
    """Tracks exponential backoff for a specific metadata source"""
    retry_count: int = 0
    last_attempt: float = 0.0
    
    def can_retry_now(self) -> bool:
        """Check if enough time has passed for exponential backoff"""
        if self.retry_count == 0:
            return True
        
        # Exponential backoff: 2^retry_count seconds (capped at 300 seconds = 5 minutes)
        backoff_seconds = min(2 ** self.retry_count, 300)
        return time.time() - self.last_attempt >= backoff_seconds
    
    def record_failure(self) -> None:
        """Record a failed attempt"""
        self.retry_count += 1
        self.last_attempt = time.time()
        
    def reset(self) -> None:
        """Reset backoff on success"""
        self.retry_count = 0
        self.last_attempt = 0.0