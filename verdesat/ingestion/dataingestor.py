from geo.geoobject import GeoObject

class DataIngestor:
    """
    Abstract base for data ingestion (EE, local, openEO).
    """
    def download_timeseries(self, geoobject: GeoObject, sensor, index: str, **kwargs):
        raise NotImplementedError()