import logging
from timeit import default_timer as timer

logger = logging.getLogger('PerformanceMonitor')

class PerformanceMonitor:
    def __init__(self):
        self.timers = {}
        self.start_time = None
        
    def start_timer(self, name):
        """Start a named timer"""
        if name == 'main':
            self.start_time = timer()
        else:
            self.timers[name] = {'start': timer()}
            
    def stop_timer(self, name):
        """Stop a named timer and return the duration"""
        if name == 'main':
            return timer() - self.start_time
        elif name in self.timers:
            self.timers[name]['end'] = timer()
            self.timers[name]['duration'] = self.timers[name]['end'] - self.timers[name]['start']
            return self.timers[name]['duration']
        return 0
            
    def log_performance(self, threshold=0.2):
        """Log performance metrics if the total time exceeds threshold"""
        total_time = self.stop_timer('main')
        if total_time > threshold:
            log_message = f'Flight data times: total={total_time*1000:.2f}ms'
            for name, data in self.timers.items():
                if 'duration' in data:
                    log_message += f', {name}={data["duration"]*1000:.2f}ms'
            logger.debug(log_message)
            
    def reset(self):
        """Reset all timers"""
        self.timers = {}
        self.start_time = None