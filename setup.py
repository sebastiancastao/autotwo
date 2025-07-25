#!/usr/bin/env python3
"""
Setup script for Gmail OAuth Automation
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="gmail-oauth-automation",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Automated Google OAuth authentication for Gmail access",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/gmail-oauth-automation",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Internet :: WWW/HTTP :: Browsers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Systems Administration :: Authentication/Directory",
    ],
    python_requires=">=3.7",
    install_requires=requirements,
    extras_require={
        "supabase": ["supabase>=2.0.0"],
        "dev": ["python-dotenv>=1.0.0", "pytest>=7.0.0"],
    },
    entry_points={
        "console_scripts": [
            "gmail-oauth-automation=oauth_automation:main",
        ],
    },
    keywords="gmail oauth automation selenium google api",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/gmail-oauth-automation/issues",
        "Source": "https://github.com/yourusername/gmail-oauth-automation",
        "Documentation": "https://github.com/yourusername/gmail-oauth-automation/blob/main/README.md",
    },
) 