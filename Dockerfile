FROM python:3.12-alpine

LABEL maintainer="Michael Morandi"

# Git commit hash (short version)
ARG COMMIT_ID="development"
ENV COMMIT_ID=$COMMIT_ID

# system prerquisites
RUN apk update
RUN apk upgrade
RUN apk add --update tzdata
RUN apk add --no-cache mongodb-tools
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
COPY --chown=radar app app
RUN mkdir resources
COPY resources/mil_ranges.csv resources/
COPY flightradar.py ./
COPY --chown=radar contrib/start.sh ./
RUN echo "{ \"commit_id\": \"$COMMIT_ID\", \"build_timestamp\": \"`date -I'seconds'`\"}" > resources/meta.json


# runtime config
EXPOSE 8083 
ENTRYPOINT ["/bin/sh", "./start.sh"]