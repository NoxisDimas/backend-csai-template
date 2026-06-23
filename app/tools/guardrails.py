"""
Middleware Guardrails.
"""

from datetime import datetime
from typing import Dict, Any
import structlog
from app.services.telegram_service import log_and_alert_error_sync

logger = structlog.get_logger(__name__)

def is_within_operational_hours(hours_config: Dict[str, Any], current_time: datetime = None) -> bool:
    """
    Checks if the current time falls within the configured operational hours.
    
    Args:
        hours_config: JSONB dict from SystemConfig e.g., {"monday": {"start": "08:00", "end": "17:00"}}
    """
    try:
        if current_time is None:
            current_time = datetime.now()
            
        day_name = current_time.strftime('%A').lower()
        
        if isinstance(hours_config, str):
            import json
            hours_config = json.loads(hours_config)
            
        if not isinstance(hours_config, dict):
            return True
            
        if day_name not in hours_config:
            return False
            
        day_config = hours_config[day_name]
        
        start_time_str = None
        end_time_str = None
        
        if isinstance(day_config, str):
            try:
                import json
                parsed = json.loads(day_config)
                if isinstance(parsed, dict):
                    day_config = parsed
            except Exception as e:
                logger.warning("failed_to_parse_hours_config", error=str(e))
                
        if isinstance(day_config, dict):
            start_time_str = day_config.get("start")
            end_time_str = day_config.get("end")
        elif isinstance(day_config, str) and "-" in day_config:
            parts = day_config.split("-")
            if len(parts) == 2:
                start_time_str = parts[0].strip()
                end_time_str = parts[1].strip()
        else:
            return True
        
        if not start_time_str or not end_time_str:
            return False
            
        start_time = datetime.strptime(start_time_str, "%H:%M").time()
        end_time = datetime.strptime(end_time_str, "%H:%M").time()
        
        return start_time <= current_time.time() <= end_time
    except Exception as e:
        logger.error("operational_hours_check_failed", error=str(e))
        log_and_alert_error_sync(e, "Customer Support Agent", "is_within_operational_hours", "Checking operational hours")
        return True  # Fail open to prevent blocking customers
