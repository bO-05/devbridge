from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = fh.read().splitlines()

VERSION = "0.1.4" 

setup(
    name="devbridge",
    version=VERSION,
    author="bO-05 - DevBridge Team", 
    author_email="gilangbram@gmail.com", 
    description="AI-Powered Cross-Project Knowledge Bridge for Developers",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bO-05/devbridge",
    project_urls={
        "Bug Tracker": "https://github.com/bO-05/devbridge/issues",
        "Documentation": "https://github.com/bO-05/devbridge/blob/main/README.md",
        "Source Code": "https://github.com/bO-05/devbridge",
    },
    keywords="developer tools, AI, codegen, knowledge base, cli, devops, productivity, amazon q",
    packages=find_packages(),
    include_package_data=True, # To include files specified in MANIFEST.in
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Utilities",
        "Operating System :: OS Independent", # Assuming it is, given Python nature
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "devbridge=devbridge.cli:app",
        ],
    },
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.18.0",
            "build", # For building the package
            "twine", # For uploading the package
        ],
    },
)