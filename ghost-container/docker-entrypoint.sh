#!/bin/bash
set -e

# allow the container to be started with `--user`
if [[ "$*" == node*current/index.js* ]] && [ "$(id -u)" = '0' ]; then
        chown -R node "$GHOST_CONTENT"
        exec su-exec node "$BASH_SOURCE" "$@"
fi

if [[ "$*" == node*current/index.js* ]]; then
        baseDir="$GHOST_INSTALL/content.orig"
        for src in "$baseDir"/*/ "$baseDir"/themes/*; do
                src="${src%/}"
                target="$GHOST_CONTENT/${src#$baseDir/}"
                mkdir -p "$(dirname "$target")"
                if [ ! -e "$target" ]; then
                        tar -cC "$(dirname "$src")" "$(basename "$src")" | tar -xC "$(dirname "$target")"
                fi
        done

        # Determine what region we are in and save that as AWSREGION
        # export AWSREGION=$(curl -s 169.254.169.254/latest/meta-data/placement/availability-zone | sed 's/.$//')

        # Set the database__connection__password environmnet variable to the temporary auth token
        export database__connection__password=$(aws rds generate-db-auth-token \
        --hostname $database__connection__host \
        --port 3306 \
        --username $database__connection__user \
        --region $AWSREGION)

        knex-migrator-migrate --init --mgpath "$GHOST_INSTALL/current"
fi

exec "$@"