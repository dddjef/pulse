import setuptools

with open("README.rst", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pulse",
    version="0.0.1",
    author="Jean-François Sarazin",
    author_email="dddjef@gmail.com",
    description="Pulse is a version control system designed for creative projects",
    long_description=long_description,
    long_description_content_type="text/reST",
    url="https://github.com/dddjef/pulse",
    project_urls={
        "Bug Tracker": "https://github.com/dddjef/pulse/issues",
    },
    license="License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    python_requires=">=3.6",
)
