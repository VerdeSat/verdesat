from typing import List
from geo.aoi import AOI
from core.config import ConfigManager

class VerdeSatProject:
    """
    Represents a client project containing multiple AOIs and project-level metadata.
    """
    def __init__(self, name: str, customer: str, aois: List[AOI], config: ConfigManager):
        self.name = name
        self.customer = customer
        self.aois = aois
        self.config = config

    def add_aoi(self, aoi: AOI):
        self.aois.append(aoi)