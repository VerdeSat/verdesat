class SensorSpec:
    """
    Holds metadata for a sensor (bands, collection ID, etc).
    """
    def __init__(self, bands: dict, native_resolution: int, collection_id: str, cloud_mask_method: str):
        self.bands = bands
        self.native_resolution = native_resolution
        self.collection_id = collection_id
        self.cloud_mask_method = cloud_mask_method