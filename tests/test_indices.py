import numpy as np
from verdesat.ingestion.indices import ndvi


def test_ndvi_simple():
    """Test NDVI calculation with simple arrays."""
    red = np.array([0.2, 0.5, 0.0])
    nir = np.array([0.8, 0.5, 1.0])
    expected = (nir - red) / (nir + red)
    result = ndvi(red, nir)
    assert np.allclose(result, expected)
