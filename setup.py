import sys
from distutils.core import setup

install_requires = ["h2>=2.2.0"]
if sys.version_info < (3, 5):
    install_requires.append("typing")

setup(
    name='asyncio-apns',
    version='0.0.1',
    install_requires=install_requires,
    packages=['asyncio_apns'],
    url='https://github.com/etataurov/asyncio-apns',
    license='MIT',
    author='etataurov',
    author_email='tatauroff@gmail.com',
    description='asyncio client for Apple Push Notification Service'
)
