# syntax=docker/dockerfile:1.6
# Backend image (Django). Build context: this folder (heroes_api/).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first to take advantage of the Docker cache (dev | prod)
ARG REQUIREMENTS=dev
COPY requirements/ /app/requirements/
RUN pip install -r requirements/${REQUIREMENTS}.txt

COPY . /app/

COPY docker/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
