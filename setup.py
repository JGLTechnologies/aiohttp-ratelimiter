from setuptools import setup, find_packages
import pip

def install(package):
    if hasattr(pip, 'main'):
        pip.main(['install', package])
    else:
        pip._internal.main(['install', package])

install("Cython")

def get_long_description():
    with open("README.md", encoding="utf-8") as file:
        return file.read()


VERSION = "3.0.9"

classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
]
from Cython.Build import cythonize
setup(
    name="aiohttp-ratelimiter",
    version=VERSION,
    description="A simple ratelimiter for aiohttp.web",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/Nebulizer1213/aiohttp-ratelimiter",
    author="George Luca",
    author_email="fixingg@gmail.com",
    license="MIT",
    classifiers=classifiers,
    keywords="",
    packages=find_packages(),
    install_requires=["aiohttp"],
    ext_modules=cythonize("aiohttplimiter/utils.pyx"),
    package_data={"aiohttplimiter": ["*.pyi"]}
)
