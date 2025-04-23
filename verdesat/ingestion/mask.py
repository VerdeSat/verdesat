import ee

# Bits to exclude in Fmask band
_FMASK_EXCLUDE = {
    "FILL": 1,
    "WATER": 2,
    "SHADOW": 4,
    "SNOW": 8,
    "CLOUD": 16,
}
_EXCLUDE_MASK = sum(_FMASK_EXCLUDE.values())


def mask_fmask_bits(img: ee.Image) -> ee.Image:
    """
    Keep only pixels where none of the Fmask exclude bits are set.
    """
    fmask = img.select("Fmask")
    valid = fmask.bitwiseAnd(_EXCLUDE_MASK).eq(0)
    return img.updateMask(valid)
