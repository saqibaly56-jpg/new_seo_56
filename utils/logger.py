import logging
import os
import sys
from pythonjsonlogger import jsonlogger

class SensitiveDataFilter(logging.Filter):
    """Filter to redact sensitive API keys from logs"""
    def __init__(self):
        super().__init__()
        self.sensitive_strings = [
            os.getenv("OPENROUTER_API_KEY", ""),
            os.getenv("WP_APP_PASSWORD", "")
        ]
        # Remove empty strings to avoid replacing everything
        self.sensitive_strings = [s for s in self.sensitive_strings if s]

    def filter(self, record):
        if isinstance(record.msg, str):
            for s in self.sensitive_strings:
                if s in record.msg:
                    record.msg = record.msg.replace(s, "***REDACTED***")
        return True

def get_logger(agent_name: str) -> logging.Logger:
    """
    Returns a configured logger for the given agent/module.
    Logs are structured as JSON and sent to stdout for container platforms.
    """
    logger = logging.getLogger(agent_name)
    # Only configure if it doesn't already have handlers to avoid duplicates
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        formatter = jsonlogger.JsonFormatter('%(asctime)s %(name)s %(levelname)s %(message)s')
        
        # Container platforms collect stdout; do not require a writable local filesystem.
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)

        sensitive_filter = SensitiveDataFilter()
        stream_handler.addFilter(sensitive_filter)
        logger.addHandler(stream_handler)
        
    return logger
