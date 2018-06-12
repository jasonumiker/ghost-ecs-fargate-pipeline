# ghost IAM RDS auth container build
I cloned this from the official Docker build scripts at https://github.com/docker-library/ghost and then changed it as required to allow Ghost to use IAM authentication to the MySQL RDS.

This container is already built (using CodeBuild against the buildspec in the folder) and published on the public hub.docker.com as `jasonumiker/ghost:latest` if you'd prefer not to build it yourself.

NOTE: The changes versus the upstream ghost container may now actually require you to use IAM authentication against the underlying MySQL - I have not tested a non-SSL and/or password login after the changes. 
## Instructions
There is a `buildspec.yml` to build this container in CodeBuild as well as a `ghost-container-build.template` CloudFormation template to fully set up the CodeBuild project to do that build.

You also can build it anywhere else using just the `Dockerfile` with a `docker build`.

## (Optional) Clair-Scanned Build Pipeline
There is an alternative `buildspec_clair.yml` as well as `ghost-container-build-clair.template` which will set up a build that requires the Ghost container image to pass a Clair scan before succeeding. Clair is an open-sourced scanner by CoreOS that looks for CVEs and security vulnerabilities in Docker images (https://github.com/coreos/clair).

This requires a running Clair and there is a CloudFormation script to deploy that to Fargate at `/clair/clair_deploy_fargate.template`

If you want to see Clair find issues and fail a build change the `FROM` in the `Dockerfile` to `node:6.9.4-alpine`

## Changes from the official container build
The approach was inspired by https://cloudonaut.io/passwordless-database-authentication-for-aws-lambda/

The required changes were:
1. Add the retrieval of the login token via the CLI and store it in the required environment variable (database__connection__password) to the `docker-entrypoint.sh`.
1. Add a supervisord wrapper to restart docker-entrypoint every 14 minutes (rotating the credential and reconnecting before the expiry at 15 minutes)
1. Replace mysql package with mysql2 - which is mostly compatible with the former yet, unlike the former, supports the required SSL with mysql_clear_password.
1. Add in the ssl and authSwitchHandler parameters as required to auth via IAM
1. Change the ORM (knex) to allow through the authSwitchHandler parameter to the underlying mysql2

## TODO
Have the app get a new Token on each new connection in the node code rather than restart the process via supervisord. This is buried in a knex ORM so is a bit of a challenge.
