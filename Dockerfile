FROM python:3.9

COPY ./fetchstats.py ./requirements.txt /

RUN pip install -r /requirements.txt
RUN apt update && apt install -y cron
# cronjob to execute python script every hour
# stdout is appended to /data/twstats.csv
# stderr is appended to /data/twstats.log
RUN echo "0 * * * * /usr/local/bin/python3 /fetchstats.py /servers.txt >> /data/twstats.csv 2>>/data/twstats.log" > /var/spool/cron/crontabs/root
# activate crontab
RUN crontab /var/spool/cron/crontabs/root

# start cron in foreground, -l 0 for most verbose logs and -L for writing logs to file
CMD ["cron", "-f", "-l", "0", "-L", "/data/cron.log"]
