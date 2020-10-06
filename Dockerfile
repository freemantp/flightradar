FROM python:3.8.6-alpine 

LABEL maintainer="Michael Morandi"

ARG COMMIT_ID="undefined"

# system prerquisites
RUN apk update
RUN apk upgrade
RUN apk add --update tzdata
RUN ln -s /usr/share/zoneinfo/Europe/Zurich /etc/localtime

RUN adduser -D radar
USER radar
WORKDIR /home/radar

# install python packages
COPY requirements.txt requirements.txt
RUN python -m venv venv
RUN venv/bin/pip install --upgrade pip
RUN venv/bin/pip install -r requirements.txt

# install app
COPY app app
RUN mkdir resources
COPY resources/mil_ranges.csv resources/
COPY resources/BaseStation.sqb.tar.bz2 resources/
RUN tar xfvj resources/BaseStation.sqb.tar.bz2 -C resources
RUN rm resources/BaseStation.sqb.tar.bz2
RUN chown radar resources/BaseStation.sqb
COPY flightradar.py ./
COPY --chown=radar contrib/start.sh ./
RUN echo "{ \"gitCommitId\": \"$COMMIT_ID\", \"buildTimestamp\": \"`date -I'seconds'`\"}" > resources/meta.json

# prepare dbs
ENV FLASK_APP flightradar.py
RUN venv/bin/python -m flask initschema

# runtime config
EXPOSE 5000 
ENTRYPOINT ["/bin/sh", "./start.sh"]