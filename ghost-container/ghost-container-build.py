# Troposphere to create CloudFormation template to build the ghost image
# By Jason Umiker (jason.umiker@gmail.com)

from troposphere import Output, Join, Ref, Template, Parameter
from troposphere import AWS_ACCOUNT_ID, AWS_REGION
from troposphere import ecr, s3, iam, codebuild, ec2

t = Template()

t.add_description("Template to build the Ghost image with CodeBuild with an embedded Clair scan")

# Get Parameters

# Get the Clair URL Parameter
clair_url = t.add_parameter(Parameter(
    "ClairURL",
    Description="The URL to the Clair scanner",
    Type="String"
))

build_vpc = t.add_parameter(Parameter(
    'BuildVPC',
    Type='AWS::EC2::VPC::Id',
    Description='A VPC subnet ID for the build.',
))

build_subnet = t.add_parameter(Parameter(
    'BuildSubnet',
    Type='AWS::EC2::Subnet::Id',
    Description='A VPC subnet ID for the build.',
))

build_subnet2 = t.add_parameter(Parameter(
    'BuildSubnet2',
    Type='AWS::EC2::Subnet::Id',
    Description='A 2nd VPC subnet ID for the build.',
))

# Create the ghost Repository
Repository = t.add_resource(
    ecr.Repository(
        "Repository",
        RepositoryName="ghost"
    )
)

# Create the S3 Bucket for Output
S3Bucket = t.add_resource(
    s3.Bucket(
        "GhostClairBuildOutput"
    )
)

# Create Security group for the build jobs
build_security_group = ec2.SecurityGroup(
    "BuildSecurityGroup",
    GroupDescription="Ghost Build Security Group.",
    VpcId=Ref(build_vpc)
)
t.add_resource(build_security_group)

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
                        {'Action': ['ecr:GetAuthorizationToken'],
                         'Resource': ['*'],
                         'Effect': 'Allow'},
                        {'Action': ['ecr:*'],
                         'Resource': [
                             Join("", ["arn:aws:ecr:",
                                       Ref(AWS_REGION),
                                       ":", Ref(AWS_ACCOUNT_ID),
                                       ":repository/",
                                       Ref(Repository)]
                                  ),
                         ],
                         'Effect': 'Allow'},
                        {
                            "Effect": "Allow",
                            "Action": [
                                "ec2:CreateNetworkInterface",
                                "ec2:DescribeDhcpOptions",
                                "ec2:DescribeNetworkInterfaces",
                                "ec2:DeleteNetworkInterface",
                                "ec2:DescribeSubnets",
                                "ec2:DescribeSecurityGroups",
                                "ec2:DescribeVpcs"
                            ],
                            "Resource": "*"
                        },
                        {
                            "Effect": "Allow",
                            "Action": [
                                "ec2:CreateNetworkInterfacePermission"
                            ],
                            "Resource": "*"
                        }
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
    EnvironmentVariables=[{'Name': 'AWS_ACCOUNT_ID', 'Value': Ref(AWS_ACCOUNT_ID)},
                          {'Name': 'IMAGE_REPO_NAME', 'Value': Ref(Repository)},
                          {'Name': 'IMAGE_TAG', 'Value': 'latest'},
                          {'Name': 'CLAIR_URL', 'Value': Ref(clair_url)}],
    PrivilegedMode=True
)

ImageSource = codebuild.Source(
    Location="https://github.com/jasonumiker/ghost-ecs-fargate-pipeline",
    Type="GITHUB",
    BuildSpec="ghost-container/buildspec.yml"
)

ImageProject = codebuild.Project(
    "ImageBuildProject",
    Artifacts=ImageArtifacts,
    Environment=ImageEnvironment,
    Name="ghost-clair-build",
    ServiceRole=Ref(ServiceRole),
    Source=ImageSource,
    VpcConfig=codebuild.VpcConfig(
        VpcId=Ref(build_vpc),
        Subnets=[Ref(build_subnet), Ref(build_subnet2)],
        SecurityGroupIds=[Ref(build_security_group)]
    ),
    DependsOn=CodeBuildServiceRolePolicy
)
t.add_resource(ImageProject)

# Output ghost repository URL
t.add_output(Output(
    "RepositoryURL",
    Description="The docker repository URL",
    Value=Join("", [
        Ref(AWS_ACCOUNT_ID),
        ".dkr.ecr.",
        Ref(AWS_REGION),
        ".amazonaws.com/",
        Ref(Repository)
    ]),
))

print(t.to_json())
