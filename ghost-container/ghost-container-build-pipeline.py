# Template to create CodePipeline for Ghost
# By Jason Umiker (jason.umiker@gmail.com)

from troposphere import Parameter, Ref, Template, GetAtt, Join
from troposphere.codepipeline import (
    Pipeline, Stages, Actions, ActionTypeId, OutputArtifacts, InputArtifacts,
    ArtifactStore)
from troposphere import iam, s3, events

t = Template()

# Get the required Parameters

CodeCommitRepo = t.add_parameter(Parameter(
    "CodeCommitRepo",
    Description="The name of the CodeCommit Repo to pull from",
    Default='ghost-ecs-fargate-pipeline',
    Type="String"
))

CodeBuildProject = t.add_parameter(Parameter(
    "CodeBuildProject",
    Description="The name of the CodeBuild Project to use for the Build Phase",
    Default='ghost-clair-build',
    Type="String"
))

ECSClusterName = t.add_parameter(Parameter(
    "ECSClusterName",
    Description="The name of the ECS Cluster to pass to the deployment stack",
    Default='Ghost',
    Type="String"
))

DependencyStackName = t.add_parameter(Parameter(
    "DependencyStackName",
    Description="The name of the Dependency Stack",
    Type="String"
))

# Create the required Resources

# Create the S3 Bucket to store Artifacts
CodePipelineBucket = t.add_resource(
    s3.Bucket(
        "GhostPipelineBucket"
    )
)

# Create the CodePipeline IAM Role
CodePipelineServiceRole = t.add_resource(iam.Role(
    "CodePipelineServiceRole",
    AssumeRolePolicyDocument={
        'Statement': [{
            'Effect': 'Allow',
            'Principal': {'Service': ['codepipeline.amazonaws.com']},
            'Action': ["sts:AssumeRole"]
        }]},
))

# Create the Inline policy for the CodePipline Role
CodePipelineServicePolicy = t.add_resource(iam.PolicyType(
    "CodePipelineServicePolicy",
    PolicyName="CodePipelineServicePolicy",
    PolicyDocument={
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "iam:PassRole",
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "codebuild:StartBuild",
                    "codebuild:BatchGetBuilds"
                ],
                "Resource": [
                    Join("", ["arn:aws:codebuild:", Ref('AWS::Region'), ":", Ref('AWS::AccountId'), ":project/", Ref(CodeBuildProject)])
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "codecommit:UploadArchive",
                    "codecommit:GetCommit",
                    "codecommit:GetUploadArchiveStatus",
                    "codecommit:GetBranch",
                    "codecommit:CancelUploadArchive"
                ],
                "Resource": [
                    Join("", ["arn:aws:codecommit:", Ref('AWS::Region'), ":", Ref('AWS::AccountId'), ":", Ref(CodeCommitRepo)])
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "s3:ListBucket"
                ],
                "Resource": [
                    Join("", ["arn:aws:s3:::", Ref(CodePipelineBucket)]),
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "s3:PutObject",
                    "s3:GetObject"
                ],
                "Resource": [
                    Join("", ["arn:aws:s3:::", Ref(CodePipelineBucket), "/*"]),
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "cloudformation:CreateStack",
                    "cloudformation:DeleteStack",
                    "cloudformation:DescribeStacks",
                    "cloudformation:UpdateStack",
                    "cloudformation:CreateChangeSet",
                    "cloudformation:DeleteChangeSet",
                    "cloudformation:DescribeChangeSet",
                    "cloudformation:ExecuteChangeSet",
                    "cloudformation:SetStackPolicy",
                    "cloudformation:ValidateTemplate",
                ],
                "Resource": "*"
            }
        ]
    },
    Roles = [Ref(CodePipelineServiceRole)],
))

# Create the CloudFormation IAM Role
CloudFormationServiceRole = t.add_resource(iam.Role(
    "CloudFormationServiceRole",
    AssumeRolePolicyDocument={
        'Statement': [{
            'Effect': 'Allow',
            'Principal': {'Service': ['cloudformation.amazonaws.com']},
            'Action': ["sts:AssumeRole"]
        }]},
))

# Create the Inline policy for the CodePipline Role
CloudFormationServicePolicy = t.add_resource(iam.PolicyType(
    "CloudFormationServicePolicy",
    PolicyName="CloudFormationServicePolicy",
    PolicyDocument={
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "iam:PassRole",
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "ecs:*"
                ],
                "Resource": "*"
            },
        ]
    },
    Roles = [Ref(CloudFormationServiceRole)],
))

# Create the CloudWatch Events IAM Role
CloudWatchEventsRole = t.add_resource(iam.Role(
    "CloudWatchEventsRole",
    AssumeRolePolicyDocument={
        'Statement': [{
            'Effect': 'Allow',
            'Principal': {'Service': ['events.amazonaws.com']},
            'Action': ["sts:AssumeRole"]
        }]},
))

# Create the CodePipeline to link the Repo to the Build to ECS
pipeline = t.add_resource(Pipeline(
    "GhostPipeline",
    RoleArn=GetAtt('CodePipelineServiceRole', 'Arn'),
    Stages=[
        Stages(
            Name="Source",
            Actions=[
                Actions(
                    Name="Source",
                    ActionTypeId=ActionTypeId(
                        Category="Source",
                        Owner="AWS",
                        Version="1",
                        Provider="CodeCommit"
                    ),
                    OutputArtifacts=[
                        OutputArtifacts(
                            Name="SourceOutput"
                        )
                    ],
                    Configuration={
                        "PollForSourceChanges": "false",
                        "BranchName": "master",
                        "RepositoryName": Ref(CodeCommitRepo)
                    },
                    RunOrder="1"
                )
            ]
        ),
        Stages(
            Name="Build",
            Actions=[
                Actions(
                    Name="Build",
                    InputArtifacts=[
                        InputArtifacts(
                            Name="SourceOutput"
                        )
                    ],
                    ActionTypeId=ActionTypeId(
                        Category="Build",
                        Owner="AWS",
                        Version="1",
                        Provider="CodeBuild"
                    ),
                    OutputArtifacts=[
                        OutputArtifacts(
                            Name="BuildOutput"
                        )
                    ],
                    Configuration={
                        "ProjectName": Ref(CodeBuildProject),
                    },
                    RunOrder="1"
                )
            ]
        ),
        Stages(
            Name="Deploy",
            Actions=[
                Actions(
                    Name="Deploy",
                    InputArtifacts=[
                        InputArtifacts(
                            Name="BuildOutput"
                        )
                    ],
                    ActionTypeId=ActionTypeId(
                        Category="Deploy",
                        Owner="AWS",
                        Version="1",
                        Provider="CloudFormation"
                    ),
                    Configuration={
                        "ActionMode": "REPLACE_ON_FAILURE",
                        "Capabilities": "CAPABILITY_IAM",
                        "RoleArn": GetAtt('CloudFormationServiceRole', 'Arn'),

                        "ParameterOverrides": Join("", ["{","\"Cluster\"",":","\"",Ref(ECSClusterName),"\"",",",
                                                        "\"DependencyStackName\"",":","\"",Ref(DependencyStackName),"\"",",",
                                                        "\"GhostImage\"",":",
                                                        "{\"Fn::GetParam\" : [\"BuildOutput\",\"images.json\",\"imageUri\"]}","}"]),
                        "TemplatePath": "BuildOutput::ghost-deploy-fargate.template",
                        "StackName": "Ghost-Fargate"
                    },
                    RunOrder="1"
                )
            ]
        )
    ],
    ArtifactStore=ArtifactStore(
        Type="S3",
        Location=Ref(CodePipelineBucket)
    ),
    DependsOn=CloudFormationServicePolicy
))

# Create the Inline policy for the CodePipline Role
CloudWatchEventsPolicy = t.add_resource(iam.PolicyType(
    "CloudWatchEventsPolicy",
    PolicyName="CloudWatchEventsPolicy",
    PolicyDocument={"Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "codepipeline:StartPipelineExecution"
            ],
            "Resource": [
                Join("", ["arn:aws:codepipeline:", Ref('AWS::Region'), ":", Ref('AWS::AccountId'), ":", Ref(pipeline)])
            ]
        }
    ],
        "Version": "2012-10-17"},
    Roles=[Ref(CloudWatchEventsRole)],
))

# Create the CloudWatch Event to trigger the Pipeline on CodeCommit change
# Create the Event Target
codecommit_event_target = events.Target(
    "CodeCommitEventTarget",
    RoleArn=GetAtt('CloudWatchEventsRole', 'Arn'),
    Arn=Join("", ["arn:aws:codepipeline:", Ref('AWS::Region'), ":", Ref('AWS::AccountId'), ":", Ref(pipeline)]),
    Id='1'
)

# Create the Event Rule
cw_event_rule = t.add_resource(events.Rule(
    "CodeCommitRule",
    EventPattern={
        "source": [
            "aws.codecommit"
        ],
        "detail": {
            "referenceType": [
                "branch"
            ],
            "referenceName": [
                "master"
            ]
        },
        "detail-type": [
            "CodeCommit Repository State Change"
        ],
        "resources": [
            Join("", ["arn:aws:codecommit:", Ref('AWS::Region'), ":", Ref('AWS::AccountId'), ":", Ref(CodeCommitRepo)]),
        ]
    },
    Description="CodeCommit State Change CloudWatch Event",
    State="ENABLED",
    Targets=[codecommit_event_target]
))

print(t.to_json())
