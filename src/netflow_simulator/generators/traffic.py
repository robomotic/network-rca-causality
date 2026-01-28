from typing import List, Dict, Any
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
    def __init__(self, router_config: RouterConfig, workstation_model: WorkstationModel):
        self.router_config = router_config
        self.workstation_model = workstation_model
        # Simplified subnet assumptions
        self.internal_subnet = "192.168.1."
        self.external_ips = ["8.8.8.8", "1.1.1.1", "20.112.52.29", "142.250.187.174", "104.21.5.7"]

    def generate_hourly_traffic(self, timestamp: datetime.datetime, is_workday: bool) -> List[FlowRecord]:
        hour = timestamp.hour
        workstations = self.workstation_model.get_count()
        records = []
        
        for name, proto_def in PROTOCOLS.items():
            state = self.router_config.get_protocol_state(name)
            
            # 1. Determine base volume
            factor = proto_def.get_hourly_volume_factor(hour, is_workday)
            
            # Baseline: ~1-10 flows per workstation per hour per protocol depending on usage
            num_flows = int(workstations * factor * random.uniform(0.5, 2.0))
            
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
