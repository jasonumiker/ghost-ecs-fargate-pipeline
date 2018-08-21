# Ghost running on ECS Fargate via CI/CD Pipeline
This project takes the already well-containerised (https://hub.docker.com/_/ghost/) Ghost microblogging platform (https://github.com/TryGhost/Ghost) and deploys it to ECS Fargate serverless mode.

It is intended more to be a demo on how to use various AWS services (ECS, Fargate, MySQL RDS w/IAM Auth, CloudFormation, CodeBuild, CodePipeline, etc.) than for actually running a Ghost - but it certainly can do that too.

## Fargate Pipeline Quick Start Instuctions
The `quickstart/quickstart.template` Nested Stack CloudFormation template creates:
1. A VPC Stack
1. The required pre-req IAM roles for ECS in a Stack
1. An ECS Cluster for Fargate
1. The Dependency stack (IAM roles, ALB, security groups, RDS MySQL DB, CloudWatch Log Group, etc.)
1. A Fargate deployment of Ghost in a Stack
1. CodeCommit, CodeBuild and CodePipeline Stacks to (re)build the ghost container on pushes to master and deploy it to Fargate on successful builds
    1. This pipeline will run the image through a Clair scan in the post_build step in CodeBuild via klar (https://github.com/optiopay/klar)
1. A Fargate deployment of the Clair (https://github.com/coreos/clair) image scanning service to run the scans when requested in the build by klar in a Stack
    1. This stack also deploys the required Postgres RDS, ALB, etc.

It is opinionated to be as simple as possible and pretty much takes the defaults of the AWS VPC Quickstart (i.e. 10.0.0.0/16) and the template underpinning the ECS Console's Create Cluster wizard.

The only Parameters to provide are:
1. An EC2 SSH key (must be created before the stack is run)
1. A password for the RDS DB root user that will be passed to the RDS creation and DB init Lambda. The tasks will then use IAM authentication to the database.
    1. It is hidden in the CF stacks but you can change it after creation if you'd like for maximum security.
1. The ghost Docker image to pull (you can use jasonumiker/ghost:latest if you don't want to build/host it yourself)
1. The IAM principal (user or role) that can administer the KMS key for the RDS.
    1. If in doubt, use the root account in the form of `arn:aws:iam::111122223333:root` where the number is your account number
    1. An IAM user ARN will be in the form `arn:aws:iam::111122223333:user/KMSAdminUser`
    1. A user logging in Federated from on-prem SAML will often be in the form `arn:aws:sts::111122223333:assumed-role/Role/user@company.com`
        1. If you check CloudTrail for any event this user has done it'll be the arn under UserIdentity
1. Whether to deploy the optional Cloud9 IDE with this project cloned into it
    1. Note that if Cloud9 is not supported in the region the stack is being deployed into the deployment will fail

WARNING - Go to `/admin` on your URL to do the initial setup including setting the site admin password as soon as possible after it is public before somebody else gets to it first.

## Testing the pipeline and Clair scanner
Once it is done you'll have a new CodeCommit repo `ghost-ecs-fargate-pipeline` with this repo cloned into it. Any changes to master on that CodeCommit repo will trigger the CodePipeline to rebuild the Ghost container and redeploy it if successful.

A good way to show that Clair works in this scenario is to change the `FROM` line in the `ghost-container/Dockerfile` to `node:6.9.4-alpine` which has many CVEs then doing a git commit and push. This will fail the build and stop the pipeline from deploying and you'll see details in the build logs as to what vulnerabilities it found.

## Architecture
All state for Ghost is stored in a MySQL RDS leaving the containers fully stateless.

The `dependencies.template` CloudFormation template: 
1. Creates the encrypted MySQL RDS to store the state and associated KMS key
1. Creates the IAM roles
1. Creates the security groups
1. Creates the ALB and Target Group that will present the service(s)
1. Creates the CloudWatch Logs Group for Ghost
1. Creates a Lamba-backed Custom Resource to set up the database for IAM authentication and add the app's user

The `ghost-deploy-fargate.template` CloudFormation template deploys Ghost to Fargate. This is invoked in the quickstart by the CodePipeline.

The `ghost-container/ghost-container-build.template` Template sets up a CodeBuild project to build our container image

The `ghost-container/ghost-container-build-pipeline.template` Template sets up a CodePipeline to watch the CodeCommit repo and run the build and deploy on changes

The `quickstart/clair-deploy-fargate.template` Template deploys the Clair scanner used by CodeBuild. For more information on that see (https://github.com/jasonumiker/clair-ecs-fargate)

These templates were created by using Troposphere (https://github.com/cloudtools/troposphere) in the corresponding `.py` files.