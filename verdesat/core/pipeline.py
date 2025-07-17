from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import pandas as pd

from verdesat.geo.aoi import AOI
from verdesat.analytics.timeseries import TimeSeries
from verdesat.ingestion.base import BaseDataIngestor
from verdesat.visualization.visualizer import Visualizer
from verdesat.visualization._chips_config import ChipsConfig
import geopandas as gpd


@dataclass
class ReportPipeline:
    """Encapsulate the NDVI report workflow."""

    aois: List[AOI]
    ingestor: BaseDataIngestor
    visualizer: Visualizer

    def _export_geojson(self, out_dir: str) -> str:
        """Write AOIs to GeoJSON and return the file path."""
        gdf = gpd.GeoDataFrame(
            [{**aoi.static_props, "geometry": aoi.geometry} for aoi in self.aois],
            crs="EPSG:4326",
        )
        path = os.path.join(out_dir, "aoi.geojson")
        os.makedirs(out_dir, exist_ok=True)
        gdf.to_file(path, driver="GeoJSON")
        return path

    def run(
        self,
        start: str,
        end: str,
        out_dir: str,
        map_png: Optional[str] = None,
        title: str = "VerdeSat Report",
    ) -> str:
        """Execute the full pipeline and return path to report."""
        os.makedirs(out_dir, exist_ok=True)
        self._export_geojson(out_dir)

        # 1. Download monthly NDVI time-series for all AOIs
        df_list: List[pd.DataFrame] = []
        for aoi in self.aois:
            df = self.ingestor.download_timeseries(
                aoi,
                start_date=start,
                end_date=end,
                scale=30,
                index="ndvi",
                chunk_freq="YE",
                freq="ME",
            )
            df_list.append(df)
        timeseries_df = pd.concat(df_list, ignore_index=True)
        timeseries_csv = os.path.join(out_dir, "timeseries.csv")
        timeseries_df.to_csv(timeseries_csv, index=False)

        # 2. Aggregate & fill gaps
        ts = TimeSeries.from_dataframe(timeseries_df, index="ndvi")
        monthly_csv = os.path.join(out_dir, "timeseries_monthly.csv")
        ts.aggregate("ME").to_csv(monthly_csv)
        filled_ts = ts.aggregate("ME").fill_gaps()
        filled_csv = os.path.join(out_dir, "timeseries_filled.csv")
        filled_ts.to_csv(filled_csv)

        # 3. Decompose seasonality
        decomp_dir = os.path.join(out_dir, "decomp")
        os.makedirs(decomp_dir, exist_ok=True)
        results = filled_ts.decompose()
        for pid, res in results.items():
            df_out = pd.DataFrame(
                {
                    "date": res.observed.index,
                    "observed": res.observed.values,
                    "trend": res.trend.values,
                    "seasonal": res.seasonal.values,
                    "resid": res.resid.values,
                }
            )
            df_out.to_csv(
                os.path.join(decomp_dir, f"{pid}_decomposition.csv"), index=False
            )
            self.visualizer.plot_decomposition(
                res, os.path.join(decomp_dir, f"{pid}_decomposition.png")
            )

        # 4. Export image chips
        chips_dir = os.path.join(out_dir, "chips")
        yearly_cfg = ChipsConfig.from_cli(
            collection=self.ingestor.sensor.collection_id,
            start=start,
            end=end,
            period="Y",
            chip_type="ndvi",
            scale=30,
            buffer=0,
            buffer_percent=None,
            min_val=None,
            max_val=None,
            gamma=None,
            percentile_low=None,
            percentile_high=None,
            palette_arg="white-green",
            fmt="png",
            out_dir=chips_dir,
            mask_clouds=True,
        )
        self.ingestor.download_chips(self.aois, yearly_cfg)

        monthly_chips_dir = os.path.join(out_dir, "chips_monthly")
        monthly_cfg = ChipsConfig.from_cli(
            collection=self.ingestor.sensor.collection_id,
            start=start,
            end=end,
            period="ME",
            chip_type="ndvi",
            scale=30,
            buffer=0,
            buffer_percent=None,
            min_val=None,
            max_val=None,
            gamma=None,
            percentile_low=None,
            percentile_high=None,
            palette_arg="white-green",
            fmt="png",
            out_dir=monthly_chips_dir,
            mask_clouds=True,
        )
        self.ingestor.download_chips(self.aois, monthly_cfg)

        # 5. Animated GIFs per year
        gifs_dir = os.path.join(out_dir, "gifs")
        start_year = datetime.strptime(start, "%Y-%m-%d").year
        end_year = datetime.strptime(end, "%Y-%m-%d").year
        for year in range(start_year, end_year + 1):
            pattern = f"*_{year}-*.png"
            year_dir = os.path.join(gifs_dir, str(year))
            self.visualizer.make_gifs_per_site(
                images_dir=monthly_chips_dir,
                pattern=pattern,
                output_dir=year_dir,
            )

        # 6. Interactive plot
        timeseries_html = os.path.join(out_dir, "timeseries.html")
        self.visualizer.plot_timeseries_html(
            filled_ts.df, "mean_ndvi", timeseries_html, agg_freq="ME"
        )

        # 7. Final report
        return self.visualizer.generate_report(
            out_dir,
            title=title,
            map_png=map_png,
            timeseries_csv=filled_csv,
        )
