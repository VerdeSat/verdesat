"""
Compute spectral indices either in‐memory or via Earth Engine.
"""


def ndvi(red, nir):
    """Normalized Difference Vegetation Index."""
    return (nir - red) / (nir + red)


def evi(red, nir, blue, G=2.5, C1=6.0, C2=7.5, L=1.0):
    """Enhanced Vegetation Index."""
    return G * ((nir - red) / (nir + C1 * red - C2 * blue + L))


class CustomIndexProcessor:
    def compute(self, image, indices):
        """
        image: EE.Image or numpy array dict.
        indices: list of callables or names.
        """
        raise NotImplementedError("Hook up Earth Engine logic here.")
