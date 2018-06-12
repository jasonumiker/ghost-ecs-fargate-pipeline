# https://docs.ghost.org/supported-node-versions/
# https://github.com/nodejs/LTS
FROM node:6-alpine

# grab su-exec for easy step-down from root
RUN apk add --no-cache 'su-exec>=0.2' bash supervisor python py-pip py-setuptools ca-certificates curl groff less

ENV NODE_ENV production

ENV GHOST_CLI_VERSION 1.8.0
RUN npm install -g "ghost-cli@$GHOST_CLI_VERSION"

ENV GHOST_INSTALL /var/lib/ghost
ENV GHOST_CONTENT /var/lib/ghost/content

ENV GHOST_VERSION 1.23.0

RUN set -ex; \
        mkdir -p "$GHOST_INSTALL"; \
        chown node:node "$GHOST_INSTALL"; \
        \
        su-exec node ghost install "$GHOST_VERSION" --db sqlite3 --no-prompt --no-stack --no-setup --dir "$GHOST_INSTALL"; \
        \
# Tell Ghost to listen on all ips and not prompt for additional configuration
        cd "$GHOST_INSTALL"; \
        su-exec node ghost config --ip 0.0.0.0 --port 2368 --no-prompt --db sqlite3 --url http://localhost:2368 --dbpath "$GHOST_CONTENT/data/ghost.db"; \
        su-exec node ghost config paths.contentPath "$GHOST_CONTENT"; \
        \
# make a config.json symlink for NODE_ENV=development (and sanity check that it's correct)
        su-exec node ln -s config.production.json "$GHOST_INSTALL/config.development.json"; \
        readlink -f "$GHOST_INSTALL/config.development.json"; \
        \
# need to save initial content for pre-seeding empty volumes
        mv "$GHOST_CONTENT" "$GHOST_INSTALL/content.orig"; \
        mkdir -p "$GHOST_CONTENT"; \
        chown node:node "$GHOST_CONTENT"; \
        \
# sanity check to ensure knex-migrator was installed
        "$GHOST_INSTALL/current/node_modules/knex-migrator/bin/knex-migrator" --version

# add knex-migrator bins into PATH
# we want these from the context of Ghost's "node_modules" directory (instead of doing "npm install -g knex-migrator") so they can share the DB driver modules
ENV PATH $PATH:$GHOST_INSTALL/current/node_modules/knex-migrator/bin

WORKDIR $GHOST_INSTALL
VOLUME $GHOST_CONTENT

COPY docker-entrypoint.sh /usr/local/bin
RUN chmod a=rx,u=rwx /usr/local/bin/docker-entrypoint.sh

COPY connection.js $GHOST_INSTALL/current/core/server/data/db
COPY index.js $GHOST_INSTALL/current/node_modules/knex/lib/dialects/mysql2
COPY utils.js $GHOST_INSTALL/current/core/server/config
COPY config.production.json $GHOST_INSTALL/current/core/server/config/env
COPY database.js $GHOST_INSTALL/current/node_modules/knex-migrator/lib
RUN sed -i "/this.isMySQL/c\    this.isMySQL = this.dbConfig.client === 'mysql2';" $GHOST_INSTALL/current/node_modules/knex-migrator/lib/index.js

COPY supervisord.conf /etc/supervisor.d/supervisord.ini
COPY setup_cron.sh /usr/local/bin
RUN chmod a=rx,u=rwx /usr/local/bin/setup_cron.sh

RUN set -ex; \
        cd "$GHOST_INSTALL/current"; \
        npm install mysql2

RUN pip install --upgrade pip && \
    pip --no-cache-dir install botocore awscli && \
    rm -rf /var/cache/apk/*

EXPOSE 2368

CMD ["supervisord"]