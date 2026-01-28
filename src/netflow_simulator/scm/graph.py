import networkx as nx
from typing import Dict, Any, List, Optional
import pydot

class SimulationSCM:
    """
    Structural Causal Model for Network Traffic Simulation.
    Defines the dependencies between various simulation factors.
    """
    def __init__(self, confounder_settings: Optional[Dict] = None):
        self.graph = nx.DiGraph()
        self.confounder_settings = confounder_settings or {'enabled': False, 'levels': [], 'multiplier': 1.0}
        self._build_graph()

    def _is_conf_active(self, level: int) -> bool:
        return self.confounder_settings['enabled'] and level in self.confounder_settings['levels']

    def _build_graph(self):
        """Builds the DAG of the simulation."""
        
        # Temporal Factors (Root Nodes)
        self.graph.add_node("Timestamp", type="temporal")
        self.graph.add_node("HourOfDay", type="temporal")
        self.graph.add_node("DayOfWeek", type="temporal")
        self.graph.add_node("MonthOfYear", type="temporal")
        self.graph.add_node("IsHoliday", type="temporal")
        
        # Environmental Factors
        self.graph.add_node("WorkstationCount", type="environment")
        
        # Admin Actions
        self.graph.add_node("AdminIntervention", type="action")
        self.graph.add_node("ProtocolConfig", type="config") # Allow/Deny/Throttle
        
        # Traffic Factors
        self.graph.add_node("TrafficVolume", type="metric")
        self.graph.add_node("ProtocolTraffic", type="metric")
        
        # Faults
        self.graph.add_node("SystemFault", type="event")
        self.graph.add_node("RebootEvent", type="event")

        # Edges (Causal Links)
        
        # Time influences IsHoliday, Admin Actions, and Traffic
        self.graph.add_edge("Timestamp", "HourOfDay")
        self.graph.add_edge("Timestamp", "DayOfWeek")
        self.graph.add_edge("Timestamp", "MonthOfYear")
        self.graph.add_edge("Timestamp", "IsHoliday")

        # Admin is active during business hours mainly
        self.graph.add_edge("HourOfDay", "AdminIntervention")
        self.graph.add_edge("DayOfWeek", "AdminIntervention")
        self.graph.add_edge("IsHoliday", "AdminIntervention")
        
        # Admin interventions change protocol configs
        self.graph.add_edge("AdminIntervention", "ProtocolConfig")
        
        # Traffic depends on Time, Workstations, and Configs
        self.graph.add_edge("HourOfDay", "TrafficVolume")
        self.graph.add_edge("DayOfWeek", "TrafficVolume")
        self.graph.add_edge("WorkstationCount", "TrafficVolume")
        
        self.graph.add_edge("TrafficVolume", "ProtocolTraffic")
        self.graph.add_edge("ProtocolConfig", "ProtocolTraffic")

        # --- Confounder Spurious Edges ---
        
        # Level 1: Admin reactions to traffic
        if self._is_conf_active(1):
            self.graph.add_edge("ProtocolTraffic", "AdminIntervention", label="spurious_reactive")
            
        # Level 2: Cross-protocol correlation
        if self._is_conf_active(2):
            self.graph.add_edge("ProtocolTraffic", "ProtocolTraffic", label="group_burst")

        # Level 3: Workstation common cause
        if self._is_conf_active(3):
            # Already exists (WorkstationCount -> TrafficVolume), but reinforcing the SMB/RSTP link
            pass
            
        # Level 4: Reverse causation (Reboot -> Traffic)
        if self._is_conf_active(4):
            # RebootEvent -> ProtocolTraffic already exists but now it's a + surge rather than - drop
            pass
            
        # Level 5: Lagged confounder
        if self._is_conf_active(5):
            self.graph.add_edge("HourOfDay", "ProtocolTraffic", label="lagged_mimic")
        
        # Faults depend on traffic and config (e.g. throttling + high volume)
        self.graph.add_edge("ProtocolTraffic", "SystemFault")
        self.graph.add_edge("ProtocolConfig", "SystemFault")
        
        # Faults lead to reboots
        self.graph.add_edge("SystemFault", "RebootEvent")
        
        # Reboot impacts traffic (drops to zero)
        self.graph.add_edge("RebootEvent", "ProtocolTraffic")

    def export_graph(self, path: str = "scm_graph.dot"):
        """Exports the DAG to a DOT file."""
        try:
            pdot = nx.drawing.nx_pydot.to_pydot(self.graph)
            pdot.write_dot(path)
        except ImportError:
            # Fallback if graphviz/pydot not installed in environment fully
            pass

    def get_dependencies(self, node: str) -> List[str]:
        """Returns the immediate ancestors (causes) of a node."""
        return list(self.graph.predecessors(node))

    def get_topological_sort(self) -> List[str]:
        """Returns nodes in topological order for processing."""
        return list(nx.topological_sort(self.graph))
