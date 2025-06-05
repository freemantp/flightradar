import logging

def disable_urllibs_response_warnings(func):
    '''Decorator to disable warnings in the urllib3 response'''
  
    def wrap(*args, **kwargs):
        try:
            urllib3logger = logging.getLogger('urllib3.response')

            if urllib3logger:
                urllib3logger.setLevel(logging.ERROR)
        
            response = func(*args, **kwargs)            
        finally:
            if urllib3logger:
                urllib3logger.setLevel(logging.WARN)

        return response

    return wrap