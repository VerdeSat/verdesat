# setup.py
from setuptools import setup, find_packages


def parse_reqs(fname="requirements.txt"):
    with open(fname) as f:
        # strip comments and empty lines
        return [l.strip() for l in f if l.strip() and not l.startswith("#")]


setup(
    name="verdesat",
    version="0.1.0",
    packages=find_packages(
        include=[
            "core",
            "ingestion",
            "analytics",
            "modeling",
            "biodiversity",
            "agri_health",
            "carbon_flux",
            "webapp",
        ]
    ),
    install_requires=parse_reqs(),
    include_package_data=True,
    python_requires=">=3.8",
    entry_points={"console_scripts": ["verdesat=core.cli:cli"]},
)
