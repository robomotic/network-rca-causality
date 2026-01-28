from typing import Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field
import datetime

class ActionType(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    THROTTLE = "throttle"

class ProtocolState(BaseModel):
    name: str
    action: ActionType = ActionType.ALLOW
    throttle_limit_kbps: Optional[int] = None
    qos_priority: int = 0  # 0-7, 7 is highest
    
class RouterConfig:
    """
    Models the configuration state of the Cisco-like router/switch.
    """
    def __init__(self, supported_protocols: List[str]):
        self.protocols: Dict[str, ProtocolState] = {
            p: ProtocolState(name=p) for p in supported_protocols
        }
        self.global_bandwidth_limit_mbps: int = 1000
        self.config_log: List[Dict] = []

    def get_protocol_state(self, protocol: str) -> ProtocolState:
        return self.protocols.get(protocol)

    def update_protocol(self, protocol: str, action: ActionType, 
                        throttle_kbps: Optional[int] = None, 
                        priority: Optional[int] = None,
                        timestamp: datetime.datetime = None):
        """
        Updates the configuration for a specific protocol.
        """
        if protocol not in self.protocols:
            return # Ignore unknown protocols or raise error

        state = self.protocols[protocol]
        old_state = state.model_copy()
        
        state.action = action
        if throttle_kbps is not None:
            state.throttle_limit_kbps = throttle_kbps
        if priority is not None:
            state.qos_priority = priority
            
        # Log the change
        if timestamp:
            self.config_log.append({
                "timestamp": timestamp,
                "protocol": protocol,
                "action": "update",
                "details": {
                    "old_action": old_state.action,
                    "new_action": state.action,
                    "throttle": state.throttle_limit_kbps,
                    "qos": state.qos_priority
                }
            })

    def reset_defaults(self, timestamp: datetime.datetime = None):
        """Resets all protocols to ALLOW state."""
        for p in self.protocols.values():
            p.action = ActionType.ALLOW
            p.throttle_limit_kbps = None
            p.qos_priority = 0
            
        if timestamp:
            self.config_log.append({
                "timestamp": timestamp,
                "action": "reset_defaults",
                "details": "All protocols reset to ALLOW"
            })
