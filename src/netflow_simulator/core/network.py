import random
from typing import Tuple

class WorkstationModel:
    """
    Simulates the dynamics of workstation counts in the network.
    Uses a bounded random walk model.
    """
    def __init__(self, start_count: int = 100, min_count: int = 50, max_count: int = 500, volatility: float = 0.05):
        self.current_count = start_count
        self.min_count = min_count
        self.max_count = max_count
        self.volatility = volatility

    def next_day(self) -> int:
        """
        Calculates the number of workstations for the next day.
        Introduces a random change based on volatility.
        """
        change_pct = random.uniform(-self.volatility, self.volatility)
        change = int(self.current_count * change_pct)
        
        # Ensure at least some movement occasionally, but not always
        if change == 0 and random.random() < 0.3:
            change = random.choice([-1, 1])

        new_count = self.current_count + change
        
        # Apply bounds
        new_count = max(self.min_count, min(self.max_count, new_count))
        
        self.current_count = new_count
        return self.current_count

    def get_count(self) -> int:
        return self.current_count
