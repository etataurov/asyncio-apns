FROM python:3.5-alpine
RUN pip install --upgrade pip
RUN pip install --upgrade setuptools
COPY . .
RUN pip install -r requirements-test.txt && pip install python-coveralls && pip install flake8
RUN python setup.py install