import random
import datetime
from typing import List, Dict, Deque, Optional
from collections import deque
from ..core.appliance import RouterConfig, ActionType, ProtocolState
from ..generators.protocols import PROTOCOLS

class ScheduledTask:
    def __init__(self, execute_at: datetime.datetime, protocol: str, action: ActionType, reason: str):
        self.execute_at = execute_at
        self.protocol = protocol
        self.action = action
        self.reason = reason

class AdminActor:
    """
    Simulates an IT administrator making configuration changes.
    
    Design for causal analysis challenge (correlation-resistant):
    1. Admin MORE LIKELY to throttle during HIGH TRAFFIC (confounder!)
    2. Admin has BIAS towards throttling RSTP (it's "known problematic")
    3. Actions cluster in time (autocorrelation)
    4. Some actions are reactive to observed traffic patterns
    """
    
    # Configuration for confounding behavior
    BASE_ACTION_PROBABILITY = 0.03  # 3% base chance per working hour
    HIGH_TRAFFIC_MULTIPLIER = 3.0   # 3x more likely when traffic is high (CONFOUNDER!)
    RSTP_THROTTLE_BIAS = 4.0        # 4x more likely to throttle RSTP than other protocols
    
    def __init__(self, router_config: RouterConfig):
        self.router_config = router_config
        self.pending_tasks: Deque[ScheduledTask] = deque()
        self.admin_log: List[Dict] = []
        self.last_hour_traffic: Dict[str, float] = {}  # Track traffic for reactive decisions

    def tick(self, timestamp: datetime.datetime, is_workday: bool, 
             current_traffic: Optional[List] = None):
        """
        Called every simulation hour.
        
        Args:
            timestamp: Current simulation time
            is_workday: Whether it's a working day
            current_traffic: Current hour's traffic records (for reactive decisions)
        """
        
        # Calculate traffic levels if provided (for confounding behavior)
        traffic_level = 0.0
        rstp_traffic = 0.0
        if current_traffic:
            traffic_level = sum(r.bytes for r in current_traffic) / (1024 * 1024)  # MB
            rstp_traffic = sum(r.bytes for r in current_traffic if r.protocol == "RSTP")
            self.last_hour_traffic = {
                "total_mb": traffic_level,
                "rstp_bytes": rstp_traffic
            }
        
        # 1. Process pending reversions
        remaining_tasks = deque()
        while self.pending_tasks:
            task = self.pending_tasks.popleft()
            if timestamp >= task.execute_at:
                # Execute reversion
                self.router_config.update_protocol(
                    task.protocol, 
                    task.action, 
                    timestamp=timestamp
                )
                self.admin_log.append({
                    "timestamp": timestamp,
                    "actor": "Admin (Auto-Revert)",
                    "action": f"Revert {task.protocol} to {task.action.value}",
                    "reason": task.reason
                })
            else:
                remaining_tasks.append(task)
        self.pending_tasks = remaining_tasks

        # 2. Decide on new interventions
        # Only active during work hours on workdays
        if not is_workday:
            return
        if not (9 <= timestamp.hour <= 17):
            return

        # CONFOUNDING: Higher traffic = higher probability of admin action!
        # This creates spurious correlation between traffic and crashes
        action_probability = self.BASE_ACTION_PROBABILITY
        if traffic_level > 10:  # More than 10MB/hour total
            action_probability *= self.HIGH_TRAFFIC_MULTIPLIER
        
        if random.random() < action_probability:
            self._perform_action(timestamp, rstp_traffic)

    def _perform_action(self, timestamp: datetime.datetime, rstp_traffic: float = 0):
        """
        Decide and execute an admin action.
        
        RSTP is throttled MORE OFTEN due to:
        1. Admin bias (it's "known to cause issues")
        2. Reactive behavior when RSTP traffic is high
        """
        
        # Weight protocols - RSTP has strong bias
        protocol_weights = {}
        for proto_name in PROTOCOLS.keys():
            weight = 1.0
            if proto_name == "RSTP":
                weight = self.RSTP_THROTTLE_BIAS
                # REACTIVE: Even more likely if RSTP traffic was high
                if rstp_traffic > 5000:  # > 5KB
                    weight *= 2.0
            protocol_weights[proto_name] = weight
        
        # Weighted random selection
        total = sum(protocol_weights.values())
        r = random.random() * total
        cumulative = 0
        selected_protocol = list(PROTOCOLS.keys())[0]
        for proto, weight in protocol_weights.items():
            cumulative += weight
            if r <= cumulative:
                selected_protocol = proto
                break
        
        current_state = self.router_config.get_protocol_state(selected_protocol)
        
        # Decide action type - prefer throttle over disable
        action_type = random.choices(
            ['disable_temp', 'throttle_temp'],
            weights=[0.3, 0.7]  # 70% throttle, 30% disable
        )[0]
        
        if action_type == 'disable_temp':
            duration_hours = random.randint(1, 24)
            self.router_config.update_protocol(selected_protocol, ActionType.DENY, timestamp=timestamp)
            
            self.admin_log.append({
                "timestamp": timestamp,
                "actor": "Admin",
                "action": f"Disable {selected_protocol}",
                "reason": f"Investigating issue, blocked for {duration_hours}h"
            })
            
            revert_time = timestamp + datetime.timedelta(hours=duration_hours)
            self.pending_tasks.append(
                ScheduledTask(revert_time, selected_protocol, ActionType.ALLOW, "Planned maintenance end")
            )
            
        elif action_type == 'throttle_temp':
            duration_hours = random.randint(4, 48)  # Longer throttle durations
            limit = random.randint(100, 1000)
            
            self.router_config.update_protocol(
                selected_protocol, 
                ActionType.THROTTLE, 
                throttle_kbps=limit, 
                timestamp=timestamp
            )
            
            self.admin_log.append({
                "timestamp": timestamp,
                "actor": "Admin",
                "action": f"Throttle {selected_protocol} to {limit}kbps",
                "reason": f"Bandwidth management for {duration_hours}h (traffic was high)"
            })
            
            revert_time = timestamp + datetime.timedelta(hours=duration_hours)
            self.pending_tasks.append(
                ScheduledTask(revert_time, selected_protocol, ActionType.ALLOW, "End throttling")
            )
