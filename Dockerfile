FROM python:3.9-alpine

LABEL Name=new_tv_shows_ng Version=0.0.1

WORKDIR /
COPY requirements.txt .

# pip Ausführen
RUN python3 -m pip install -r requirements.txt

COPY newTvShow.py /
COPY crontab /
RUN mkdir out
RUN mkdir data

RUN crontab crontab

# Skript beim start einmal ausführen und dach cron deamon starten
CMD python /newTvShow.py && crond -f 

