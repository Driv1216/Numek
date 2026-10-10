from setuptools import find_packages, setup


setup(
    name="datatrust",
    version="0.1.0",
    description="Local-first dataset reliability reports for AI teams.",
    packages=find_packages("src"),
    package_dir={"": "src"},
    package_data={"datatrust": ["templates/*.html"]},
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0",
        "flask>=3.0",
        "jinja2>=3.0",
        "pandas>=1.5",
        "numpy>=1.23",
        "weasyprint>=69,<70",
        "duckdb>=1.5.6,<1.6",
        "psutil>=5.9",
        "tzdata>=2025.2",
    ],
    extras_require={"parquet": ["pyarrow>=19,<26"], "dev": ["pypdf>=6,<7", "pytest>=7.0"], "statistics": ["scipy>=1.10,<2"]},
    entry_points={"console_scripts": ["datatrust=datatrust.cli:main"]},
)
