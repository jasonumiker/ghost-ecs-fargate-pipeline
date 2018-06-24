# Troposphere to create CloudFormation template for base dependencies
# By Jason Umiker (jason.umiker@gmail.com)

from troposphere import Template, Ref, Output, GetAtt, Export, Sub, \
    Parameter, Join, iam, logs, ec2, rds, elasticloadbalancingv2, \
    awslambda, cloudformation, kms


class CustomDBInit(cloudformation.AWSCustomObject):
    resource_type = "Custom::DBInit"
    props = {
        'ServiceToken': (str, True),
        'Password': (str, True)
    }


t = Template()
t.add_version('2010-09-09')

# Get the required Parameters

db_vpc = t.add_parameter(Parameter(
    'DBVPC',
    Type='AWS::EC2::VPC::Id',
    Description='A VPC subnet ID for the DB.',
))

db_subnet = t.add_parameter(Parameter(
    'DBSubnet',
    Type='AWS::EC2::Subnet::Id',
    Description='A VPC subnet ID for the DB.',
))

db_subnet2 = t.add_parameter(Parameter(
    'DBSubnet2',
    Type='AWS::EC2::Subnet::Id',
    Description='A 2nd VPC subnet ID for the DB.',
))

alb_subnet = t.add_parameter(Parameter(
    'ALBSubnet',
    Type='AWS::EC2::Subnet::Id',
    Description='A Public VPC subnet ID for the ALB.',
))

alb_subnet2 = t.add_parameter(Parameter(
    'ALBSubnet2',
    Type='AWS::EC2::Subnet::Id',
    Description='A 2nd Public VPC subnet ID for the ALB.',
))

dbpassword = t.add_parameter(Parameter(
    "DBPassword",
    NoEcho=True,
    Description="The database admin account password",
    Type="String",
    MinLength="1",
    MaxLength="41",
    AllowedPattern="[a-zA-Z0-9]*",
    ConstraintDescription="must contain only alphanumeric characters."
))

dbclass = t.add_parameter(Parameter(
    "DBClass",
    Default="db.t2.small",
    Description="Database instance class",
    Type="String",
    AllowedValues=[
        "db.t2.small", "db.t2.large", "db.t2.xlarge", "db.m4.large",
        "db.m4.xlarge", "db.m2.2xlarge"],
    ConstraintDescription="must select a valid database instance type.",
))

dballocatedstorage = t.add_parameter(Parameter(
    "DBAllocatedStorage",
    Default="5",
    Description="The size of the database (Gb)",
    Type="Number",
    MinValue="5",
    MaxValue="1024",
    ConstraintDescription="must be between 5 and 1024Gb.",
))

dbmultiaz = t.add_parameter(Parameter(
    "DBMultiAZ",
    Default="True",
    Description="Should the RDS be MultiAZ (True/False)",
    Type="String"
))

key_admin_arn = t.add_parameter(Parameter(
    "KeyAdminARN",
    Description="The ARN for the User/Role that can manage the RDS KMS key (e.g. arn:aws:iam::111122223333:root)",
    Type="String"
))

cr_s3_bucket = t.add_parameter(Parameter(
    "CRS3Bucket",
    Default="ghost-ecs-fargate",
    Description="The S3 Bucket that the init_db_lambda.zip for the Custom Resource is located in",
    Type="String"
))

# Create the Resources

# Create the Task Role
TaskRole = t.add_resource(iam.Role(
    "TaskRole",
    AssumeRolePolicyDocument={
        'Statement': [{
            'Effect': 'Allow',
            'Principal': {'Service': ['ecs-tasks.amazonaws.com']},
            'Action': ["sts:AssumeRole"]
        }]},
))

# Create the Task Execution Role
TaskExecutionRole = t.add_resource(iam.Role(
    "TaskExecutionRole",
    AssumeRolePolicyDocument={
        'Statement': [{
            'Effect': 'Allow',
            'Principal': {'Service': ['ecs-tasks.amazonaws.com']},
            'Action': ["sts:AssumeRole"]
        }]},
))

# Create the Lambda Execution Role for Custom Resource
LambdaExecutionRole = t.add_resource(iam.Role(
    "LambdaExecutionRole",
    AssumeRolePolicyDocument={
        'Statement': [{
            'Effect': 'Allow',
            'Principal': {'Service': ['lambda.amazonaws.com']},
            'Action': ["sts:AssumeRole"]
        }]},
))

# Create the Fargate Execution Policy (access to ECR and CW Logs)
FargateExecutionPolicy = t.add_resource(iam.PolicyType(
    "FargateExecutionPolicy",
    PolicyName="fargate-execution",
    PolicyDocument={'Version': '2012-10-17',
                    'Statement': [{'Action': ['ecr:GetAuthorizationToken',
                                              'ecr:BatchCheckLayerAvailability',
                                              'ecr:GetDownloadUrlForLayer',
                                              'ecr:BatchGetImage', 'logs:CreateLogStream',
                                              'logs:PutLogEvents'],
                                   'Resource': ['*'],
                                   'Effect': 'Allow'},
                                  ]},
    Roles=[Ref(TaskExecutionRole)],
))

# Create CloudWatch Log Group
GhostLogGroup = t.add_resource(logs.LogGroup(
    "GhostLogGroup",
))

# Create Security group that allows traffic into the ALB
alb_security_group = ec2.SecurityGroup(
    "ALBSecurityGroup",
    GroupDescription="Ghost ALB Security Group",
    VpcId=Ref(db_vpc),
    SecurityGroupIngress=[
        ec2.SecurityGroupRule(
            IpProtocol="tcp",
            FromPort="80",
            ToPort="80",
            CidrIp="0.0.0.0/0",
        ),
        ec2.SecurityGroupRule(
            IpProtocol="tcp",
            FromPort="443",
            ToPort="443",
            CidrIp="0.0.0.0/0",
        ),
    ]
)
t.add_resource(alb_security_group)

# Create Security group for the host/ENI/Fargate that allows 2368
ghost_host_security_group = ec2.SecurityGroup(
    "GhostHostSecurityGroup",
    GroupDescription="Ghost ECS Security Group.",
    VpcId=Ref(db_vpc),
    SecurityGroupIngress=[
        ec2.SecurityGroupRule(
            IpProtocol="tcp",
            FromPort="2368",
            ToPort="2368",
            SourceSecurityGroupId=(GetAtt(alb_security_group, 'GroupId'))
        ),
    ]
)
t.add_resource(ghost_host_security_group)

# Create the DB Subnet Group
dbsubnetgroup = t.add_resource(rds.DBSubnetGroup(
    "DBSubnetGroup",
    DBSubnetGroupDescription="Subnets available for the RDS DB Instance",
    SubnetIds=[Ref(db_subnet), Ref(db_subnet2)],
))

# Create the DB's Security group which only allows access to memebers of the Ghost Host SG
dbsecuritygroup = t.add_resource(ec2.SecurityGroup(
    "DBSecurityGroup",
    GroupDescription="Security group for RDS DB Instance.",
    VpcId=Ref(db_vpc),
    SecurityGroupIngress=[
        ec2.SecurityGroupRule(
            IpProtocol="tcp",
            FromPort="3306",
            ToPort="3306",
            SourceSecurityGroupId=(GetAtt(ghost_host_security_group, 'GroupId'))
        ),
    ]
))

# Create the KMS key for RDS encryption
rdskmskey = t.add_resource(kms.Key(
    "rdskmskey",
    Description="Key for encrypting the RDS",
    KeyPolicy={
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "Allow full administration of the key by the root account",
                "Effect": "Allow",
                "Principal": {
                    "AWS": Ref(key_admin_arn),
                },
                "Action": [
                    "kms:*"
                ],
                "Resource": "*"
            },
            {
                "Sid": "Allow access through RDS for all principals in the account that are authorized to use RDS",
                "Effect": "Allow",
                "Principal": {"AWS": "*"},
                "Condition": {
                    "StringEquals": {
                        "kms:CallerAccount": Ref('AWS::AccountId'),
                        "kms:ViaService": Join("", ["rds.", Ref('AWS::Region'), ".amazonaws.com"])
                    }
                },
                "Action": [
                    "kms:Encrypt",
                    "kms:Decrypt",
                    "kms:ReEncrypt*",
                    "kms:GenerateDataKey*",
                    "kms:CreateGrant",
                    "kms:DescribeKey"
                ],
                "Resource": "*"
            },
        ]
    }
))

# Create the MySQL RDS
ghost_db = t.add_resource(rds.DBInstance(
    "GhostDB",
    DBName='ghost',
    AllocatedStorage=Ref(dballocatedstorage),
    DBInstanceClass=Ref(dbclass),
    Engine='MySQL',
    EngineVersion='5.7.21',
    MasterUsername='root',
    MasterUserPassword=Ref(dbpassword),
    DBSubnetGroupName=Ref(dbsubnetgroup),
    VPCSecurityGroups=[Ref(dbsecuritygroup)],
    MultiAZ=Ref(dbmultiaz),
    StorageType='gp2',
    StorageEncrypted='True',
    KmsKeyId=Ref(rdskmskey)
))

# Add database credential access to the Task Role
DBAccessPolicy = t.add_resource(iam.PolicyType(
    "DBAccessPolicy",
    PolicyName="DBAccessPolicy",
    PolicyDocument={
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "rds-db:connect"
                ],
                "Resource": [
                    Join("", ["arn:aws:rds-db:", Ref('AWS::Region'), ":", Ref('AWS::AccountId'), ":dbuser:", GetAtt("DBInit", "db_resource_id"), "/ghost"])
                ]
            }
        ]
    },
    Roles=[Ref(TaskRole)],
))

# Create the Lambda Execution Policy
LambdaExecutionPolicy = t.add_resource(iam.PolicyType(
    "LambdaExecutionPolicy",
    PolicyName="lambda-execution",
    PolicyDocument={'Version': '2012-10-17',
                    'Statement': [{'Action': ['logs:CreateLogGroup',
                                              'logs:CreateLogStream',
                                              'logs:PutLogEvents',
                                              'ec2:CreateNetworkInterface',
                                              'ec2:DescribeNetworkInterfaces',
                                              'ec2:DeleteNetworkInterface',
                                              ],
                                   'Resource': ['*'],
                                   'Effect': 'Allow'},
                                  {'Action': ['rds:ModifyDBInstance'],
                                   'Resource': Join("", ["arn:aws:rds:", Ref('AWS::Region'), ":", Ref('AWS::AccountId'),
                                                         ":db:", Ref(ghost_db)]),
                                   'Effect': 'Allow'},
                                  ]},
    Roles=[Ref(LambdaExecutionRole)],
))

# Create the Lambda Function for the Custom Resource to set up the DB
DBInitFunction = t.add_resource(awslambda.Function(
    "InitDBFunction",
    Code=awslambda.Code(
        S3Bucket=Ref(cr_s3_bucket),
        S3Key="init-db-lambda.zip"
    ),
    Handler="init-db-lambda.handler",
    Role=GetAtt("LambdaExecutionRole", "Arn"),
    Runtime="python2.7",
    MemorySize="128",
    Timeout="180",
    Environment=awslambda.Environment(
        Variables={
            'dbuser': 'root',
            'awsregion': Ref("AWS::Region"),
            'dbname': 'ghost',
            'dbhost': GetAtt(ghost_db, 'Endpoint.Address'),
            'dbid': Ref(ghost_db)
        }
    ),
    VpcConfig=awslambda.VPCConfig(
        SecurityGroupIds=[Ref(ghost_host_security_group)],
        SubnetIds=[Ref(db_subnet), Ref(db_subnet2)]
    ),
    DependsOn=LambdaExecutionPolicy
))

# Add the application ELB
GhostALB = t.add_resource(elasticloadbalancingv2.LoadBalancer(
    "GhostALB",
    Scheme="internet-facing",
    Subnets=[Ref(alb_subnet), Ref(alb_subnet2)],
    SecurityGroups=[Ref(alb_security_group)]
))

GhostTargetGroup = t.add_resource(elasticloadbalancingv2.TargetGroup(
    "GhostTargetGroup",
    HealthCheckIntervalSeconds="30",
    HealthCheckProtocol="HTTP",
    HealthCheckTimeoutSeconds="10",
    HealthyThresholdCount="4",
    Matcher=elasticloadbalancingv2.Matcher(
        HttpCode="200,301"),
    Port=2368,
    Protocol="HTTP",
    UnhealthyThresholdCount="3",
    TargetType="ip",
    VpcId=Ref(db_vpc)
))

Listener = t.add_resource(elasticloadbalancingv2.Listener(
    "Listener",
    Port="80",
    Protocol="HTTP",
    LoadBalancerArn=Ref(GhostALB),
    DefaultActions=[elasticloadbalancingv2.Action(
        Type="forward",
        TargetGroupArn=Ref(GhostTargetGroup)
    )]
))

dbinit = t.add_resource(CustomDBInit(
    "DBInit",
    ServiceToken=GetAtt(DBInitFunction, 'Arn'),
    Password=Ref(dbpassword),
    DBHost=GetAtt(ghost_db, "Endpoint.Address"),
    DependsOn=ghost_db
))

# Create the required Outputs

# Output the Task Role Arn
t.add_output(Output(
    "TaskRoleArn",
    Value=GetAtt(TaskRole, "Arn"),
    Description="Task Role Arn",
    Export=Export(Sub("${AWS::StackName}-TaskRoleArn"))
))

# Output the Task Execution Role Arn
t.add_output(Output(
    "TaskExecutionRoleArn",
    Value=GetAtt(TaskExecutionRole, "Arn"),
    Description="Task Execution Role Arn",
    Export = Export(Sub("${AWS::StackName}-TaskExecutionRoleArn"))
))

# Output the Log Group name
t.add_output(Output(
    "GhostLogGroupName",
    Value=Ref(GhostLogGroup),
    Description="Name of Ghost Log Group",
    Export=Export(Sub("${AWS::StackName}-GhostLogGroupName"))
))

# Output the host / fargate security group ID
t.add_output(Output(
    "GhostSG",
    Value=GetAtt(ghost_host_security_group, 'GroupId'),
    Description="ID of the Ghost Security Group",
    Export=Export(Sub("${AWS::StackName}-GhostSG"))
))

# Output the db hostname
t.add_output(Output(
    "GhostDBHost",
    Value=GetAtt(ghost_db, 'Endpoint.Address'),
    Description="FQDN of the Ghost DB.",
    Export=Export(Sub("${AWS::StackName}-GhostDBHost"))
))

# Output the Target Group ARN
t.add_output(Output(
    "GhostTG",
    Description="ARN of the Ghost Target Group",
    Value=Ref(GhostTargetGroup),
    Export=Export(Sub("${AWS::StackName}-GhostTG"))
))

# Output the ALB URL
t.add_output(Output(
    "ALBURL",
    Description="URL of the ALB",
    Value=Join("", ["http://", GetAtt(GhostALB, "DNSName")]),
    Export=Export(Sub("${AWS::StackName}-ALBURL"))
))

# Output the Target Group Name
t.add_output(Output(
    "ALBTGNAME",
    Description="Name of the ALB Target Group",
    Value=GetAtt(GhostTargetGroup, 'TargetGroupName'),
    Export=Export(Sub("${AWS::StackName}-ALBTGNAME"))
))

# Output Subnet 1
t.add_output(Output(
    "Subnet1",
    Description="ID of the first Subnet to use",
    Value=Ref(db_subnet),
    Export=Export(Sub("${AWS::StackName}-Subnet1"))
))

# Output Subnet 2
t.add_output(Output(
    "Subnet2",
    Description="ID of the first Subnet to use",
    Value=Ref(db_subnet2),
    Export=Export(Sub("${AWS::StackName}-Subnet2"))
))

# Output Stack Name
t.add_output(Output(
    "StackName",
    Description="Name of this Stack",
    Value=Ref("AWS::StackName"),
    Export=Export(Sub("${AWS::StackName}-StackName"))
))

print(t.to_json())
