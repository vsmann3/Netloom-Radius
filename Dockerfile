ARG PYTHON_IMAGE
FROM ${PYTHON_IMAGE} AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends gcc pkg-config default-libmysqlclient-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY requirements.txt .
RUN pip wheel --wheel-dir=/wheels -r requirements.txt

FROM ${PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends libmariadb3 && rm -rf /var/lib/apt/lists/* && useradd --uid 10001 --create-home app
COPY --from=build /wheels /wheels
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r /tmp/requirements.txt && rm -rf /wheels
WORKDIR /app
COPY --chown=app:app manage.py ./
COPY --chown=app:app netloom ./netloom
COPY --chown=app:app core ./core
COPY --chown=app:app templates ./templates
COPY --chown=app:app deploy/radius/mods-enabled/netloom_sql ./deploy/radius/mods-enabled/netloom_sql
RUN DJANGO_SECRET_KEY=static-build-only DB_PASSWORD=static-build-only python manage.py collectstatic --noinput
USER app
EXPOSE 8000
CMD ["gunicorn", "netloom.wsgi:application", "--bind", "0.0.0.0:8000", "--no-control-socket", "--workers", "2", "--timeout", "30", "--access-logfile", "/dev/null", "--error-logfile", "-"]
