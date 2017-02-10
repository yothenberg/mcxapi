from setuptools import setup, find_packages
import mcxapi

setup(
    name='mcxapi',
    description='CLI to access the MaritzCX HTTP API',
    version=mcxapi.__version__,
    license='MIT',
    author='Mark Wright',
    author_email='m.e.wright@gmail.com',
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'click', 'requests', 'anytree'
    ],
    entry_points='''
        [console_scripts]
        mcx=mcxapi.cli:cli
    ''',
)
