from typing import List
from verdesat.geo.aoi import AOI
from verdesat.core.config import ConfigManager
from verdesat.ingestion.vector_preprocessor import VectorPreprocessor
from verdesat.ingestion.dataingestor import DataIngestor
from verdesat.ingestion.sensorspec import SensorSpec
from verdesat.analytics.timeseries import TimeSeries
from verdesat.visualization.visualizer import Visualizer


class VerdeSatProject:
    """
    Represents a client project containing multiple AOIs and project-level metadata.
    """

    def __init__(
        self, name: str, customer: str, aois: List[AOI], config: ConfigManager
    ):
        self.name = name
        self.customer = customer
        self.aois = aois
        self.config = config

    def add_aoi(self, aoi: AOI):
        self.aois.append(aoi)

    @classmethod
    def from_directory(
        cls, name: str, customer: str, input_dir: str, config: ConfigManager
    ) -> "VerdeSatProject":
        """
        Factory: build a project by preprocessing vector inputs into AOIs.
        """
        vp = VectorPreprocessor(input_dir)
        gdf = vp.run()
        aois = AOI.from_gdf(gdf, id_col=config.get("id_col", "id"))
        return cls(name, customer, aois, config)

    def run_pipeline(
        self,
        collection_id: str,
        index: str,
        start_date: str,
        end_date: str,
        scale: int,
        freq: str,
        output_dir: str,
        report_title: str | None = None,
    ) -> None:
        """
        Execute the full workflow: download timeseries, attach to AOIs, and generate a report.
        """
        # Instantiate ingestion components
        sensor = SensorSpec.from_collection_id(collection_id)
        ingestor = DataIngestor(sensor)
        # Download and attach timeseries for each AOI
        for aoi in self.aois:
            df = ingestor.download_timeseries(
                aoi, start_date, end_date, scale, index, freq
            )
            ts = TimeSeries.from_dataframe(df, index=index)
            aoi.add_timeseries(index, ts)
        # Generate HTML report
        viz = Visualizer()
        title = report_title or self.config.get("report_title", "VerdeSat Report")
        viz.generate_report(self, output_dir, title=title)
