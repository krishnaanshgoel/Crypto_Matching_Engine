from setuptools import setup, find_packages

setup(
    name="goquant3",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.109.0",
        "uvicorn>=0.27.0",
        "pydantic>=2.6.0",
        "websockets>=12.0",
        "pytest>=8.0.0",
    ],
    python_requires=">=3.8",
) 