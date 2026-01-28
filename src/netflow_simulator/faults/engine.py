from typing import List, Dict, Optional, Tuple
import datetime
import random
from collections import deque
from ..core.appliance import RouterConfig, ActionType

class FaultEvent:
    def __init__(self, timestamp: datetime.datetime, event_type: str, details: str = ""):
        self.timestamp = timestamp
        self.event_type = event_type
        self.details = details

class PendingCrash:
    """Represents a crash scheduled to occur after a delay."""
    def __init__(self, trigger_time: datetime.datetime, crash_time: datetime.datetime, reason: str):
        self.trigger_time = trigger_time  # When conditions were met
        self.crash_time = crash_time      # When crash will occur (delayed)
        self.reason = reason

class FaultEngine:
    """
    Engine for evaluating fault conditions and triggering crashes.
    
    Design for causal discoverability (but correlation-resistant):
    1. Lower threshold (10KB instead of 50MB) so faults actually trigger
    2. Time-delayed causation (3-hour lag) - defeats simple t-1 correlation
    3. Interaction effects (multiple conditions required)
    4. NO random crashes - all crashes are deterministic from conditions
    5. Probabilistic trigger (80% when conditions met)
    """
    
    # Fault configuration
    RSTP_VOLUME_THRESHOLD_BYTES = 10 * 1024  # 10KB - lowered from 50MB
    CRASH_DELAY_HOURS = 3  # Crash occurs 3 hours after conditions met
    FAULT_PROBABILITY = 0.8  # 80% chance when conditions met
    MIN_WORKSTATIONS_FOR_FAULT = 70  # Interaction effect: need enough endpoints
    REQUIRE_BUSINESS_HOURS = True  # Interaction effect: only during 9-17
    
    def __init__(self, router_config: RouterConfig, confounder_settings: Optional[Dict] = None):
        self.router_config = router_config
        self.fault_log: List[FaultEvent] = []
        self.pending_crashes: deque = deque()  # Delayed crashes waiting to trigger
        self.ground_truth_log: List[Dict] = []  # For validation (hidden from analysis)
        self.confounder_settings = confounder_settings or {'enabled': False, 'levels': [], 'multiplier': 1.0}

    def _is_conf_active(self, level: int) -> bool:
        return self.confounder_settings['enabled'] and level in self.confounder_settings['levels']

    def check_for_faults(self, timestamp: datetime.datetime, traffic_records: List, 
                         workstation_count: int = 100) -> bool:
        """
        Checks system state and traffic to see if a fault occurs.
        Returns True if a system reboot is triggered.
        
        Key changes for causal analysis:
        - Crash is DELAYED by 3 hours (defeats t-1 correlation)
        - Requires interaction of multiple conditions
        - NO random crashes (all are deterministic)
        """
        reboot_triggered = False
        hour = timestamp.hour
        is_business_hours = 9 <= hour <= 17

        # 1. Check if any PENDING crashes should trigger now
        while self.pending_crashes and self.pending_crashes[0].crash_time <= timestamp:
            pending = self.pending_crashes.popleft()
            reboot_triggered = True
            # Log with GENERIC message (hide the true cause!)
            self._log_fault(timestamp, "System Crash", "Kernel panic - not syncing: Fatal exception")
        
        if reboot_triggered:
            return True

        # 2. Check if NEW fault conditions are met (will schedule delayed crash)
        rstp_state = self.router_config.get_protocol_state("RSTP")
        
        if rstp_state.action == ActionType.THROTTLE:
            # Check RSTP volume
            rstp_traffic = sum(r.bytes for r in traffic_records if r.protocol == "RSTP")
            
            # INTERACTION EFFECTS: All conditions must be met
            conditions_met = (
                rstp_traffic > self.RSTP_VOLUME_THRESHOLD_BYTES and  # Volume threshold
                workstation_count >= self.MIN_WORKSTATIONS_FOR_FAULT and  # Workstation threshold
                (not self.REQUIRE_BUSINESS_HOURS or is_business_hours)  # Time constraint
            )
            
            if conditions_met:
                # Probabilistic trigger (not always deterministic)
                if random.random() < self.FAULT_PROBABILITY:
                    # Schedule DELAYED crash (3 hours from now)
                    crash_time = timestamp + datetime.timedelta(hours=self.CRASH_DELAY_HOURS)
                    
                    # Check we don't already have a pending crash
                    if not any(p.crash_time == crash_time for p in self.pending_crashes):
                        self.pending_crashes.append(PendingCrash(
                            trigger_time=timestamp,
                            crash_time=crash_time,
                            reason=f"RSTP throttle + volume={rstp_traffic}B + ws={workstation_count}"
                        ))
                        
                        # Log ground truth (for validation ONLY - not in public output!)
                        self.ground_truth_log.append({
                            "condition_met_time": timestamp.isoformat(),
                            "scheduled_crash_time": crash_time.isoformat(),
                            "rstp_throttled": True,
                            "rstp_volume_bytes": rstp_traffic,
                            "workstation_count": workstation_count,
                            "hour": hour,
                            "delay_hours": self.CRASH_DELAY_HOURS
                        })

        # NO RANDOM CRASHES - all crashes are deterministic from the causal mechanism
        # This ensures causal methods CAN find the true cause

        return reboot_triggered

    def _log_fault(self, timestamp, type, reason):
        self.fault_log.append(FaultEvent(timestamp, type, reason))

    def get_public_fault_logs(self) -> List[Dict]:
        """Returns logs formatted for CSV export (NO causal details!)."""
        return [
            {
                "timestamp": f.timestamp, 
                "event": f.event_type,
                # Details intentionally hidden to make RCA challenging
            }
            for f in self.fault_log
        ]
    
    def get_ground_truth(self) -> List[Dict]:
        """
        Returns the hidden ground truth for validation AFTER analysis.
        This should NOT be used during causal discovery!
        """
        return self.ground_truth_log
