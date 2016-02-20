import sys
from distutils.core import setup

if sys.version_info < (3, 5):
    install_requires = ["typing"]
else:
    install_requires = []


setup(
    name='asyncio-apns',
    version='0.0.1',
    install_requires=install_requires,
    dependency_links=["git+https://github.com/python-hyper/hyper-h2@2d41ef196c686f0b1895eb0cfa220082cb2c07f1#egg=h2"],
    packages=['asyncio_apns'],
    url='https://github.com/etataurov/asyncio-apns',
    license='MIT',
    author='etataurov',
    author_email='tatauroff@gmail.com',
    description='asyncio client for Apple Push Notification Service'
)
