from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="pyJira",
    version="0.0.1",
    author="Mathias Lummefors",
    description="A Jira command line interface",
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    #
    install_requires=[
        'prompt_toolkit',
        'pyyaml',
        'aiohttp',
        'click'
    ],
    packages=find_packages(),
    py_modules=['jira_cli'],
    include_package_data=True,
    entry_points={
        'console_scripts': ['jira=jira_cli:pyjira'],
    },
    python_requires=">=3.9",
)
