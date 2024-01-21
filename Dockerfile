FROM python:3.10-slim-buster

WORKDIR /app

ADD . /app

RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install -y \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info

EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", ":5000", "app:app"]