FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=src.app

WORKDIR /app

# requirements.txt for the app, requirements-test.txt for the test image.
ARG REQUIREMENTS=requirements.txt
COPY requirements.txt requirements-test.txt ./
RUN pip install --no-cache-dir -r ${REQUIREMENTS}

COPY . .

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "wsgi:app"]
