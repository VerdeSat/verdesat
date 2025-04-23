import ee
from ee import Image


def compute_ndvi(img: Image) -> Image:
    """Normalized Difference Vegetation Index."""
    return img.normalizedDifference(["B5", "B4"]).rename("NDVI")


def compute_evi(img: Image) -> Image:
    """
    Enhanced Vegetation Index: G*(NIR-RED)/(NIR+C1*RED-C2*BLUE+L)
    using default NASA coefficients.
    """
    return img.expression(
        "G * ((NIR - RED) / (NIR + C1*RED - C2*BLUE + L))",
        {
            "NIR": img.select("B5"),
            "RED": img.select("B4"),
            "BLUE": img.select("B2"),
            "G": 2.5,
            "C1": 6.0,
            "C2": 7.5,
            "L": 1.0,
        },
    ).rename("EVI")
