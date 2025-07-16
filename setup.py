from setuptools import setup, find_packages

setup(
    name="devops-orchestrator",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "uvicorn",
        "pydantic",
        "kafka-python",
        "python-dotenv",
    ],
)
