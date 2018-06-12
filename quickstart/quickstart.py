# Template to deploy VPC, ECS Cluster, Dependencies, Ghost to Fargate and set up a Ghost container CodePipeline
# By Jason Umiker (jason.umiker@gmail.com)

from troposphere import Template, Parameter, Ref, GetAtt, Join, Output, cloudformation, ecs, codecommit

t = Template()
t.add_version('2010-09-09')

# Get the required Parameters

keypair_name = t.add_parameter(Parameter(
    'KeypairName',
    Type='AWS::EC2::KeyPair::KeyName',
    Description='The name of your EC2 KeyPair for SSH.',
))

db_password = t.add_parameter(Parameter(
    'DBPassword',
    NoEcho=True,
    Description="The database admin account password",
    Type="String",
))

ghost_image = t.add_parameter(Parameter(
    'GhostImage',
    Type='String',
    Description='The Ghost image to deploy',
    Default='jasonumiker/ghost:latest'
))

key_admin_ARN = t.add_parameter(Parameter(
    'KeyAdminARN',
    Type='String',
    Description='The ARN for the User/Role that can manage the RDS KMS key (e.g. arn:aws:iam::111122223333:root)',
))

cr_s3_bucket = t.add_parameter(Parameter(
    "CRS3Bucket",
    Default="ghost-ecs-fargate-pipeline",
    Description="The S3 Bucket that the init_db_lambda.zip for the Custom Resource is located in",
    Type="String"
))

# Create the ECS Cluster
ECSCluster = t.add_resource(ecs.Cluster(
    "ECSCluster",
    ClusterName='Ghost'
))

# Create the CodeCommit Repo
GhostRepo = t.add_resource(codecommit.Repository(
    "GhostRepo",
    RepositoryName='ghost-ecs-fargate-pipeline'
))

# Create each required stack

vpc_stack = t.add_resource(cloudformation.Stack(
    "VPCStack",
    Parameters={
        'AvailabilityZones': Join("", [Ref('AWS::Region'), "a,", Ref('AWS::Region'), "b"]),
        'NumberOfAZs': '2',
        'KeyPairName': Ref(keypair_name),
    },
    TemplateURL="https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/vpc.template",
))

ecs_roles_stack = t.add_resource(cloudformation.Stack(
    "ECSRolesStack",
    TemplateURL="https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/ecs-roles.template",
))

dependencies_stack = t.add_resource(cloudformation.Stack(
    "DepdendenciesStack",
    Parameters={
        'DBVPC': GetAtt(vpc_stack, "Outputs.VPCID"),
        'DBSubnet': GetAtt(vpc_stack, "Outputs.PrivateSubnet1AID"),
        'DBSubnet2': GetAtt(vpc_stack, "Outputs.PrivateSubnet2AID"),
        'ALBSubnet': GetAtt(vpc_stack, "Outputs.PublicSubnet1ID"),
        'ALBSubnet2': GetAtt(vpc_stack, "Outputs.PublicSubnet2ID"),
        'DBPassword': Ref(db_password),
        'DBMultiAZ': 'False',
        'KeyAdminARN': Ref(key_admin_ARN),
        'CRS3Bucket' : Ref(cr_s3_bucket)
    },
    TemplateURL="https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/dependencies.template",
))

ghost_fargate_stack = t.add_resource(cloudformation.Stack(
    "GhostFargateStack",
    Parameters={
        'Cluster': "Ghost",
        'GhostImage': Ref(ghost_image),
        'TaskRoleARN': GetAtt(dependencies_stack, "Outputs.TaskRoleArn"),
        'ExecutionRoleARN': GetAtt(dependencies_stack, "Outputs.TaskExecutionRoleArn"),
        'GhostLBTargetARN': GetAtt(dependencies_stack, "Outputs.GhostTG"),
        'GhostVPC': GetAtt(vpc_stack, "Outputs.VPCID"),
        'GhostSubnet': GetAtt(vpc_stack, "Outputs.PrivateSubnet1AID"),
        'GhostSubnet2': GetAtt(vpc_stack, "Outputs.PrivateSubnet2AID"),
        'GhostLogGroup': GetAtt(dependencies_stack, "Outputs.GhostLogGroupName"),
        'GhostSecurityGroup': GetAtt(dependencies_stack, "Outputs.GhostSG"),
        'GhostDBHost': GetAtt(dependencies_stack, "Outputs.GhostDBHost"),
        'GhostURL': GetAtt(dependencies_stack, "Outputs.ALBURL"),
    },
    TemplateURL="https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/ghost-deploy-fargate.template",
    DependsOn='DepdendenciesStack'
))

clair_fargate_stack = t.add_resource(cloudformation.Stack(
    "ClairFargateStack",
    Parameters={
        'Cluster': "Ghost",
        'ClairSubnet': GetAtt(vpc_stack, "Outputs.PrivateSubnet1AID"),
        'ClairSubnet2': GetAtt(vpc_stack, "Outputs.PrivateSubnet2AID"),
        'ClairVPC': GetAtt(vpc_stack, "Outputs.VPCID"),
        'ClairImage': "jasonumiker/clair:latest"
    },
    TemplateURL="https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/clair-deploy-fargate.template",
))

ghost_container_build_stack = t.add_resource(cloudformation.Stack(
    "GhostContainerBuildStack",
    Parameters={
        'BuildSubnet': GetAtt(vpc_stack, "Outputs.PrivateSubnet1AID"),
        'BuildSubnet2': GetAtt(vpc_stack, "Outputs.PrivateSubnet2AID"),
        'BuildVPC': GetAtt(vpc_stack, "Outputs.VPCID"),
        'ClairURL': GetAtt(clair_fargate_stack, "Outputs.ClairURL"),
    },
    TemplateURL="https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/ghost-container-build-clair.template",
))

ghost_container_pipeline_stack = t.add_resource(cloudformation.Stack(
    "GhostContainerPipelineStack",
    Parameters={
        'CodeCommitRepo': "ghost-ecs-fargate-pipeline",
        'CodeBuildProject': "ghost-clair-build",
        'ECSClusterName': "Ghost",
        'ECSServiceName': GetAtt(ghost_fargate_stack, "Outputs.GhostFargateServiceName"),
    },
    TemplateURL="https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/ghost-container-build-clair-pipeline.template",
))

ghost_init_codecommit_stack = t.add_resource(cloudformation.Stack(
    "GhostInitCodeCommitStack",
    Parameters={'CodeCommitRepoAddr': GetAtt(GhostRepo, "CloneUrlHttp")},
    TemplateURL="https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/ghost-container-build-clair-pipeline.template",
))

# Output the ALB URL
t.add_output(Output(
    "ALBURL",
    Description="URL of the ALB",
    Value=GetAtt(dependencies_stack, "Outputs.ALBURL")
))

print(t.to_json())