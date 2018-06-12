# Troposphere to create CloudFormation template for CodeBuild to initialise CodeCommit repo
# By Jason Umiker (jason.umiker@gmail.com)

from troposphere import Ref, Template, Parameter
from troposphere import s3, iam, codebuild

t = Template()

t.add_description("Template to set up a CodeBuild to initialise our CodeCommit repo")

# Get Parameters

codecommit_repo_addr = t.add_parameter(Parameter(
    "CodeCommitRepoAddr",
    Description="The address of the CodeCommit Repo",
    Type="String"
))

# Create Resources

# Create the S3 Bucket for Output
ArtifactBucket = t.add_resource(
    s3.Bucket(
        "CodeCommitInitBuildOutput"
    )
)

# CodeBuild Service Role
ServiceRole = t.add_resource(iam.Role(
    "CodeBuildServiceRole",
    AssumeRolePolicyDocument={
        "Statement": [
            {
                'Effect': 'Allow',
                'Principal': {'Service': 'codebuild.amazonaws.com'},
                "Action": "sts:AssumeRole"
            }
        ]
    }
))

# CodeBuild Service Policy
CodeBuildServiceRolePolicy = t.add_resource(iam.PolicyType(
    "CodeBuildServiceRolePolicy",
    PolicyName="CodeBuildServiceRolePolicy",
    PolicyDocument={"Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "CloudWatchLogsPolicy",
                            "Effect": "Allow",
                            "Action": [
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents"
                            ],
                            "Resource": [
                                "*"
                            ]
                        },
                        {
                            "Sid": "CodeCommitPolicy",
                            "Effect": "Allow",
                            "Action": [
                                "codecommit:GitPull",
                                "codecommit:GitPush"
                            ],
                            "Resource": [
                                "*"
                            ]
                        },
                        {
                            "Sid": "S3GetObjectPolicy",
                            "Effect": "Allow",
                            "Action": [
                                "s3:GetObject",
                                "s3:GetObjectVersion"
                            ],
                            "Resource": [
                                "*"
                            ]
                        },
                        {
                            "Sid": "S3PutObjectPolicy",
                            "Effect": "Allow",
                            "Action": [
                                "s3:PutObject"
                            ],
                            "Resource": [
                                "*"
                            ]
                        },
                    ]},
    Roles=[Ref(ServiceRole)],
))

# Create CodeBuild Projects
# Image Build
ImageArtifacts = codebuild.Artifacts(
    Type='S3',
    Name='artifacts',
    Location=Ref(ArtifactBucket)
)

ImageEnvironment = codebuild.Environment(
    ComputeType="BUILD_GENERAL1_SMALL",
    Image="aws/codebuild/docker:17.09.0",
    Type="LINUX_CONTAINER",
    EnvironmentVariables=[{'Name': 'CODECOMMIT_REPO_ADDR', 'Value': Ref(codecommit_repo_addr)}],
)

ImageSource = codebuild.Source(
    Location="https://github.com/jasonumiker/ghost-ecs-fargate-pipeline",
    Type="GITHUB",
    BuildSpec = "init-codecommit-pipeline/buildspec.yml"
)

ImageProject = codebuild.Project(
    "CodeCommitInitBuildProject",
    Artifacts=ImageArtifacts,
    Environment=ImageEnvironment,
    Name="init-codecommit-build",
    ServiceRole=Ref(ServiceRole),
    Source=ImageSource,
    DependsOn=CodeBuildServiceRolePolicy
)
t.add_resource(ImageProject)

print(t.to_json())