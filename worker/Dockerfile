FROM python:3.12-slim-bookworm

ENV INDICO_VIRTUALENV="/opt/indico/.venv" INDICO_CONFIG="/opt/indico/etc/indico.conf" PYTHONPATH="/opt/indico/extensions"

ARG tag="3.3.13"



# create indico user, install apt dependencies as root and setup uwsgi etc.
USER root

RUN set -ex && \
    groupadd -r -g 999 indico && \
    useradd -r -u 999 -g indico -m -d /opt/indico indico && \
    usermod indico --add-subuids 1000000-1065535 --add-subgids 1000000-1065535

COPY fetch_debs.py /tmp/fetch_debs.py
RUN --mount=type=cache,target=/var/cache/apt --mount=type=cache,target=/var/lib/apt/lists set -ex && \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && \
    python /tmp/fetch_debs.py libpq-dev postgresql-client gcc gettext libldap2-dev libsasl2-dev rsync libcairo2 libpango-1.0-0 fonts-dejavu-core && \
    apt-get -y install --no-install-recommends libpq-dev postgresql-client gcc gettext libldap2-dev libsasl2-dev rsync libcairo2 libpango-1.0-0 fonts-dejavu-core && \
    apt-get clean

RUN --mount=type=cache,target=/var/cache/apt --mount=type=cache,target=/var/lib/apt/lists \
    apt-get update && apt-get -y install --no-install-recommends libpangoft2-1.0-0 libharfbuzz-subset0 && apt-get clean && \
    mkdir -p /var/cache/fontconfig && chown -R indico:indico /var/cache/fontconfig

COPY --from=ghcr.io/astral-sh/uv@sha256:cdc6093146eb3ff6a40107b38f008b789e050e77ad87865e381d9917da55a168 /uv /uvx /bin/

COPY uwsgi.ini /etc/uwsgi.ini
WORKDIR /opt/indico

RUN set -ex && \
    mkdir -p --mode=750 /opt/indico/etc && \
    mkdir -p --mode=777 /opt/indico/tmp && \
    mkdir -p --mode=750 /opt/indico/log && \
    mkdir -p --mode=750 /opt/indico/cache && \
    mkdir -p --mode=750 /opt/indico/archive && \
    mkdir -p --mode=750 /opt/indico/static-shared && \
    chown -R indico:indico /opt/indico

# XXX do we still need this?
RUN chmod g=u /etc/passwd

# all the installations etc can be done using the unprivileged indico user
USER indico

ENV UV_CACHE_DIR="/opt/indico/.cache/uv" UV_CONCURRENT_DOWNLOADS=4

RUN --mount=type=cache,target=/opt/indico/.cache/uv,uid=999,gid=999 set -ex && \
    python -m venv ${INDICO_VIRTUALENV} && \
    uv pip install --python ${INDICO_VIRTUALENV}/bin/python uwsgi

COPY fetch_wheels.py /tmp/fetch_wheels.py
RUN --mount=type=cache,target=/opt/indico/.cache/uv,uid=999,gid=999 \
    --mount=type=cache,target=/opt/indico/.cache/wheels,uid=999,gid=999 \
    python /tmp/fetch_wheels.py ${tag} && \
    uv pip install --python ${INDICO_VIRTUALENV}/bin/python --find-links /opt/indico/.cache/wheels indico==${tag}


RUN ${INDICO_VIRTUALENV}/bin/indico setup create-symlinks /opt/indico

COPY --chown=indico:indico run_indico.sh run_celery.sh docker_entrypoint.sh /opt/indico/
COPY --chown=indico:indico extension /opt/indico/extensions/
RUN sed -i 's/\r$//' /opt/indico/*.sh && chmod 755 /opt/indico/*.sh

ENTRYPOINT ["/opt/indico/docker_entrypoint.sh"]
EXPOSE 59999
