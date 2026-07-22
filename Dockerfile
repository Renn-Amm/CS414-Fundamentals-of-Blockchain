FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-dev \
    libssl-dev \
    libffi-dev \
    gcc \
    libsodium-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /home/python/requirements.txt

WORKDIR /home/python

ENV PIP_ROOT_USER_ACTION=ignore

RUN python -m pip install --upgrade pip wheel \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY src /home/python/src
COPY topologies /home/python/topologies

CMD ["sh", "-c", "python -u src/run.py \"$PID\" \"$TOPOLOGY\" \"$ALGORITHM\" -docker"]