FROM postgres:17-bookworm@sha256:051f7b7b3abdd564d5d1bd1e8c4b9c1b6e77087d1dd22020ede611c096a272e0
RUN apt-get update && apt-get install -y --no-install-recommends age python3 awscli \
    && rm -rf /var/lib/apt/lists/*
COPY entrypoint.sh /usr/local/bin/guten-postgres-entrypoint
COPY archive.py /usr/local/bin/guten-archive
RUN chmod 755 /usr/local/bin/guten-postgres-entrypoint /usr/local/bin/guten-archive
ENTRYPOINT ["guten-postgres-entrypoint"]
CMD ["postgres", "-c", "config_file=/etc/guten/postgresql.conf"]
