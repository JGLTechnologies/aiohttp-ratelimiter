from setuptools import setup, find_packages
import sys

if sys.version_info < (3, 7):
    raise RuntimeError("aiohttp-ratelimiter requires python 3.7 or later.")


def get_long_description():
    with open("README.md", encoding="utf-8") as file:
        return file.read()


VERSION = "4.1.2"

classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
]

setup(
    name="aiohttp-ratelimiter",
    version=VERSION,
    description="A simple rate limiter for aiohttp.web",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/skythecodemaster/aiohttp-ratelimiter",
    author="George Luca, SkyTheCodeMaster",
    author_email="fixingg@gmail.com, sky@skystuff.cc",
    license="MIT",
    classifiers=classifiers,
    keywords="",
    packages=find_packages(),
    extras_require={"memcached": ["emcache"], "redis": ["coredis"]},
    install_requires=["aiohttp", "limits"]
)
