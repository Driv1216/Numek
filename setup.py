from setuptools import find_packages, setup


setup(
    name="datatrust",
    version="0.1.0",
    description="Local-first dataset reliability reports for AI teams.",
    packages=find_packages("src"),
    package_dir={"": "src"},
    package_data={"datatrust": ["templates/*.html", "static/app/*", "static/app/assets/*", "text_model_artifacts.json", "text_search_profile.json", "image_model_artifacts.json", "cross_model_artifacts.json"], "confidenceguard": ["templates/*.html", "static/*", "schemas/*.json"]},
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
    extras_require={"documents": ["pdfplumber==0.11.9", "python-docx==1.2.0"], "cross-models": ["torch==2.8.0", "transformers==4.57.1", "tokenizers==0.22.1", "safetensors==0.6.2", "sentencepiece==0.2.1", "protobuf==6.33.5"], "images": ["Pillow==12.3.0", "ijson==3.4.0.post0", "PyYAML==6.0.3", "pycocotools==2.0.10"], "image-embeddings": ["torch==2.8.0", "transformers==4.57.1", "tokenizers==0.22.1", "safetensors==0.6.2"], "parquet": ["pyarrow>=19,<26"], "dev": ["pypdf>=6,<7", "pytest>=7.0"], "statistics": ["scipy>=1.10,<2"]},
    entry_points={"console_scripts": ["datatrust=datatrust.cli:main", "confidenceguard=confidenceguard.cli:main"]},
)
