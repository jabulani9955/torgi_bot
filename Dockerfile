FROM python:3.9

WORKDIR /torgi
COPY requirements.txt .

RUN apt-get update

RUN pip install --upgrade pip
RUN pip install --upgrade setuptools
RUN pip install -r requirements.txt

# RUN chmod 755 .

COPY . ./

RUN mv rosreestr/rosreestr2coord ../usr/local/lib/python3.9/site-packages/rosreestr2coord
RUN mv rosreestr/rosreestr2coord-4.2.7.dist-info ../usr/local/lib/python3.9/site-packages/rosreestr2coord-4.2.7.dist-info
RUN rm rosreestr

# CMD ["python", "-m", "torgi"]
