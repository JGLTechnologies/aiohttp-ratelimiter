from setuptools import setup, find_packages, Extension
import sys
import os

if sys.version_info < (3, 7):
    raise RuntimeError("aiohttp-ratelimiter requires python 3.7 or later.")

try:
    from Cython.Build import cythonize
except ImportError:
    cythonize = None


def get_long_description():
    with open("README.md", encoding="utf-8") as file:
        return file.read()


VERSION = "3.3.1"

classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
]


def no_cythonize(extensions, **_ignore):
    for extension in extensions:
        sources = []
        for sfile in extension.sources:
            path, ext = os.path.splitext(sfile)
            if ext in (".pyx", ".py"):
                if extension.language == "c++":
                    ext = ".cpp"
                else:
                    ext = ".c"
                sfile = path + ext
            sources.append(sfile)
        extension.sources[:] = sources
    return extensions


extensions = [Extension("aiohttplimiter.utils", ["aiohttplimiter/utils.pyx"])]

CYTHONIZE = bool(int(os.getenv("CYTHONIZE", 0))) and cythonize is not None

if CYTHONIZE:
    compiler_directives = {"language_level": 3, "embedsignature": True}
    extensions = cythonize(extensions, compiler_directives=compiler_directives)
else:
    extensions = no_cythonize(extensions)

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
    ext_modules=extensions,
    package_data={"aiohttplimiter": ["*.pyi"]},
    setup_requires=["Cython"]
)
