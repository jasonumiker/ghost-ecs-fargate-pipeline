# Troposphere to create CloudFormation template to build the init-db-lambda.zip bundle
# By Jason Umiker (jason.umiker@gmail.com)

from troposphere import Ref, Template, Output
from troposphere import s3, iam, codebuild

t = Template()

# Create the S3 Bucket for Output
S3Bucket = t.add_resource(
    s3.Bucket(
        "InitDBBuildOutput"
    )
)

# CodeBuild Service Role
ServiceRole = t.add_resource(iam.Role(
    "InstanceRole",
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
                                "codecommit:GitPull"
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
    Location=Ref(S3Bucket)
)

ImageEnvironment = codebuild.Environment(
    ComputeType="BUILD_GENERAL1_SMALL",
    Image="aws/codebuild/docker:17.09.0",
    Type="LINUX_CONTAINER",
    EnvironmentVariables=[{'Name': 'S3BUCKET', 'Value': Ref(S3Bucket)}],
    PrivilegedMode=True
)

ImageSource = codebuild.Source(
    Location="https://github.com/jasonumiker/ghost-ecs-fargate-pipeline",
    Type="GITHUB",
    BuildSpec="init-db-lambda/buildspec.yml"
)

ImageProject = codebuild.Project(
    "ImageBuildProject",
    Artifacts=ImageArtifacts,
    Environment=ImageEnvironment,
    Name="init-db-lambda-build",
    ServiceRole=Ref(ServiceRole),
    Source=ImageSource,
    DependsOn=ServiceRole
)
t.add_resource(ImageProject)

# Outputs

# Output the S3 Bucket where the artifact is stored
t.add_output(Output(
    "OutputBucket",
    Description="Name of the new S3 Bucket that the Output is being stored in",
    Value=Ref(S3Bucket)
))

print(t.to_json())