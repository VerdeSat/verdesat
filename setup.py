# setup.py
from setuptools import setup, find_packages


def parse_reqs(fname="requirements.txt"):
    with open(fname) as f:
        # strip comments and empty lines
        return [l.strip() for l in f if l.strip() and not l.startswith("#")]


setup(
    name="verdesat",
    version="0.1.0",
    package_dir={"verdesat": "verdesat"},
    packages=find_packages(include=["verdesat", "verdesat.*"]),
    install_requires=parse_reqs(),
    include_package_data=True,
    python_requires=">=3.8",
    entry_points={"console_scripts": ["verdesat=verdesat.core.cli:cli"]},
)
