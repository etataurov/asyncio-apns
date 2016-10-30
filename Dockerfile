FROM python:{{python_version}}-alpine
RUN pip install --upgrade pip
RUN pip install --upgrade setuptools
COPY . app
WORKDIR app
RUN pip install -r requirements-test.txt && pip install python-coveralls && pip install flake8
RUN python setup.py install