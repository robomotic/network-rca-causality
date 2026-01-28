from typing import List, Dict, Any, Optional
import datetime
import random
from ..core.appliance import RouterConfig, ActionType, ProtocolState
from ..core.network import WorkstationModel
from .protocols import PROTOCOLS, ProtocolDefinition

class FlowRecord:
    def __init__(self, timestamp, protocol, src_ip, dst_ip, packets, bytes_count, action="allow"):
        self.timestamp = timestamp
        self.protocol = protocol
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.packets = packets
        self.bytes = bytes_count
        self.action = action

class TrafficGenerator:
    def __init__(self, router_config: RouterConfig, workstation_model: WorkstationModel, 
                 confounder_settings: Optional[Dict] = None):
        self.router_config = router_config
        self.workstation_model = workstation_model
        self.confounder_settings = confounder_settings or {'enabled': False, 'levels': [], 'multiplier': 1.0}
        
        # Simplified subnet assumptions
        self.internal_subnet = "192.168.1."
        self.external_ips = ["8.8.8.8", "1.1.1.1", "20.112.52.29", "142.250.187.174", "104.21.5.7"]

    def _is_conf_active(self, level: int) -> bool:
        return self.confounder_settings['enabled'] and level in self.confounder_settings['levels']

    def generate_hourly_traffic(self, timestamp: datetime.datetime, is_workday: bool, 
                                 hours_since_reboot: int = 999) -> List[FlowRecord]:
        hour = timestamp.hour
        workstations = self.workstation_model.get_count()
        records = []
        
        for name, proto_def in PROTOCOLS.items():
            state = self.router_config.get_protocol_state(name)
            
            # 1. Determine base volume
            factor = proto_def.get_hourly_volume_factor(hour, is_workday)
            
            # --- Confounding Logic ---
            
            # Level 4: Post-Crash Recovery Surge (Reverse Causation)
            # Systems reconnecting/syncing after being down
            if self._is_conf_active(4) and hours_since_reboot <= 2:
                if name in ["DNS", "HTTP", "HTTPS", "NTP"]:
                    factor *= self.confounder_settings['multiplier'] * (3 - hours_since_reboot)
            
            # Level 3: Workstation-Driven Correlation (Common Cause)
            # Make RSTP and SMB/RDP even more sensitive to workstation spikes
            if self._is_conf_active(3):
                if name in ["RSTP", "SMB", "RDP"]:
                    # If workstation count is high, amplify these protocols specifically
                    if workstations > 150:
                        factor *= self.confounder_settings['multiplier']
            
            # Level 5: Lagged Confounder (HTTP spike 3h before potential crashes)
            # True cause is RSTP throttle + volume during 9-17.
            # We want HTTP to spike 3h before the CRASH triggered by these conditions.
            # Crash triggers at T+3. So if conditions met at T, crash at T+3.
            # If we make HTTP spike at T, it will look causal to the crash at T+3.
            if self._is_conf_active(5) and name == "HTTP":
                if is_workday and 9 <= hour <= 17:
                    # Sync with RSTP's peak hours to mimic the trigger timing
                    factor *= self.confounder_settings['multiplier']

            # Baseline: ~1-10 flows per workstation per hour per protocol depending on usage
            num_flows = int(workstations * factor * random.uniform(0.5, 2.0))
            
            # Level 2: Correlated Protocol Traffic
            # Couple DNS and HTTP/HTTPS traffic
            if self._is_conf_active(2):
                if name in ["HTTP", "HTTPS", "DNS"]:
                    # Create a "group spike" effect
                    if random.random() < 0.2: # 20% chance of a group burst
                        num_flows = int(num_flows * self.confounder_settings['multiplier'])
            
            if state.action == ActionType.DENY:
                # Still generate flows, but mark as denied/dropped
                # Maybe fewer attempts if users know it's blocked? keeping it simple for now
                pass 
            elif state.action == ActionType.THROTTLE:
                # Volume might be capped
                pass

            if num_flows == 0:
                continue

            for _ in range(num_flows):
                src = f"{self.internal_subnet}{random.randint(10, 254)}"
                
                if proto_def.is_internal_only:
                    dst = f"{self.internal_subnet}{random.randint(10, 254)}"
                else:
                    # Mixed internal/external
                    if random.random() > 0.7:
                         dst = f"{self.internal_subnet}{random.randint(10, 254)}"
                    else:
                        dst = random.choice(self.external_ips)
                
                # Calculate size
                pkts = max(1, int(random.expovariate(1.0/10))) # Exponential distribution for packets
                bytes_c = pkts * proto_def.avg_packet_size
                
                # Apply throttling logic
                final_action = state.action.value
                if state.action == ActionType.THROTTLE and state.throttle_limit_kbps:
                    # Simple heuristic: if flow is huge, it gets clipped or marked
                    # For simulation, we'll just cap the bytes if it exceeds instantaneous rate?
                    # Since this is hourly agg, it's hard to simulate exact throttling.
                    # We'll just reduce the bytes count to simulate "slowdown"
                    bytes_c = int(bytes_c * 0.5) 
                
                records.append(FlowRecord(
                    timestamp=timestamp,
                    protocol=name,
                    src_ip=src,
                    dst_ip=dst,
                    packets=pkts,
                    bytes_count=bytes_c,
                    action=final_action
                ))
                
        return records
