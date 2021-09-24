from setuptools import setup, find_packages, Extension


def get_long_description():
    with open("README.md", encoding="utf-8") as file:
        return file.read()


VERSION = "3.2.0"

classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
]


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
    ext_modules=[Extension("aiohttplimiter.utils", ["aiohttplimiter/utils.pyx"])],
    package_data={"aiohttplimiter": ["*.pyi"]},
    setup_requires=["Cython"]
)
