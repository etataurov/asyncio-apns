import sys
from distutils.core import setup

install_requires = ["h2==2.1.3dev"]
if sys.version_info < (3, 5):
    install_requires.append("typing")

setup(
    name='asyncio-apns',
    version='0.0.1',
    install_requires=install_requires,
    dependency_links=["git+https://github.com/python-hyper/hyper-h2@2d41ef196c686f0b1895eb0cfa220082cb2c07f1#egg=h2-2.1.3dev"],
    packages=['asyncio_apns'],
    url='https://github.com/etataurov/asyncio-apns',
    license='MIT',
    author='etataurov',
    author_email='tatauroff@gmail.com',
    description='asyncio client for Apple Push Notification Service'
)
