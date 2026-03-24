ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache \
    python3 \
    py3-websocket-client

COPY run.sh /run.sh
COPY pinger.py /pinger.py

RUN chmod a+x /run.sh

CMD [ "/run.sh" ]