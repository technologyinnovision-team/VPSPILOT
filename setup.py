from setuptools import setup, find_packages

setup(
    name="vpspilot",
    version="1.0.0",
    description="VPSPilot: The Autonomous Next-Gen VPS Command Center & Online Management Dashboard",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "vpspilot": [
            "static/*",
            "static/css/*",
            "static/js/*",
            "static/vendor/*",
            "templates/*"
        ]
    },
    install_requires=[
        "aiohttp>=3.8.0",
        "psutil>=5.8.0"
    ],
    entry_points={
        "console_scripts": [
            "vpspilot=vpspilot.cli:main"
        ]
    },
    python_requires=">=3.9"
)
