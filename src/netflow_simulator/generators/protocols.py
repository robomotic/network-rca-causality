import random
from typing import Dict, Tuple
from abc import ABC, abstractmethod

class ProtocolDefinition(ABC):
    def __init__(self, name: str, port: int, avg_packet_size: int, is_internal_only: bool = False):
        self.name = name
        self.port = port
        self.avg_packet_size = avg_packet_size
        self.is_internal_only = is_internal_only

    @abstractmethod
    def get_hourly_volume_factor(self, hour: int, is_workday: bool) -> float:
        """Returns a multiplier (0.0 - 1.0+) representing traffic intensity for the hour."""
        pass

class WebProtocol(ProtocolDefinition):
    def get_hourly_volume_factor(self, hour: int, is_workday: bool) -> float:
        # Business hours peak, lower at night
        if is_workday:
            if 8 <= hour <= 18:
                return random.uniform(0.8, 1.2)
            else:
                return random.uniform(0.1, 0.3)
        else: # Weekend
            return random.uniform(0.1, 0.4)

class WorkProtocol(ProtocolDefinition):
    """RDP, SSH, SMB, SMTP - Highly correlated with work hours"""
    def get_hourly_volume_factor(self, hour: int, is_workday: bool) -> float:
        if is_workday:
            if 9 <= hour <= 17:
                return random.uniform(0.9, 1.5)
            elif 8 <= hour <= 20:
                return random.uniform(0.3, 0.6)
            else:
                return random.uniform(0.01, 0.1)
        else:
            return random.uniform(0.0, 0.1)

class InfrastructureProtocol(ProtocolDefinition):
    """DNS, NTP, SNMP, ICMP - Constant low noise, some spikes"""
    def get_hourly_volume_factor(self, hour: int, is_workday: bool) -> float:
        base = random.uniform(0.2, 0.4)
        if 8 <= hour <= 18 and is_workday:
            return base * 1.5
        return base

class RSTPProtocol(ProtocolDefinition):
    """
    RSTP (Rapid Spanning Tree Protocol) - Special protocol for fault triggering.
    
    Design for causal analysis:
    - Higher base volume than other infrastructure protocols
    - Strong correlation with business hours (confounder with admin actions!)
    - High variance to sometimes exceed fault threshold
    - Volume INCREASES when workstation count is high (interaction effect)
    """
    def get_hourly_volume_factor(self, hour: int, is_workday: bool) -> float:
        # Base is higher than other infrastructure protocols
        base = random.uniform(0.8, 1.5)  # Much higher than 0.2-0.4
        
        # Strong business hours effect (creates confounding with admin actions!)
        if is_workday:
            if 9 <= hour <= 17:
                # Peak during business hours - correlates with when admin is active
                base *= random.uniform(2.0, 4.0)
            elif 8 <= hour <= 20:
                base *= random.uniform(1.2, 1.8)
            else:
                base *= random.uniform(0.3, 0.6)
        else:
            # Weekend - low but not zero
            base *= random.uniform(0.4, 0.8)
        
        # Add occasional spikes (can trigger faults)
        if random.random() < 0.1:  # 10% chance of spike
            base *= random.uniform(2.0, 5.0)
        
        return base

# Definitions
PROTOCOLS = {
    "HTTP": WebProtocol("HTTP", 80, 800),
    "HTTPS": WebProtocol("HTTPS", 443, 850),
    "DNS": InfrastructureProtocol("DNS", 53, 120),
    "SMTP": WorkProtocol("SMTP", 25, 400),
    "SSH": WorkProtocol("SSH", 22, 150),
    "RDP": WorkProtocol("RDP", 3389, 1200),
    "SMB": WorkProtocol("SMB", 445, 1400, is_internal_only=True),
    "FTP": WorkProtocol("FTP", 21, 1000),
    "NTP": InfrastructureProtocol("NTP", 123, 90),
    "ICMP": InfrastructureProtocol("ICMP", 0, 84),
    "RSTP": RSTPProtocol("RSTP", 0, 120, is_internal_only=True),  # Increased packet size for higher volume
    "SNMP": InfrastructureProtocol("SNMP", 161, 150)
}
