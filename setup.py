from setuptools import setup, find_packages

setup(
    # Mandatory
    name='daqx',  
    version='0.0.1',
    packages=find_packages(),

    # Optional metadata
    # author='',
    # author_email='',
    # description='',
    # long_description=open('README.md').read(),
    # long_description_content_type='text/markdown',
    url='https://github.com/wtmtmw/daqx',
    install_requires=[
        'mcculw',
        'ctypes',
        'numpy',
        'traceback',
        'time',
        'threading',
        'inspect',
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Windows only',
    ],
)