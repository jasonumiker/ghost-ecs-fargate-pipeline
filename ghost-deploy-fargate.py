# Troposphere to create CloudFormation template of ghost ECS deployment
# By Jason Umiker (jason.umiker@gmail.com)

from troposphere import Parameter, Ref, Template, Output, GetAtt
from troposphere.ecs import (
    Service, TaskDefinition, LoadBalancer,
    ContainerDefinition, NetworkConfiguration,
    AwsvpcConfiguration, PortMapping, Environment,
    LogConfiguration
)

t = Template()
t.add_version('2010-09-09')

# Get the required Parameters

cluster = t.add_parameter(Parameter(
    'Cluster',
    Type='String',
    Description='The ECS Cluster to deploy to.',
))

ghost_image = t.add_parameter(Parameter(
    'GhostImage',
    Type='String',
    Description='The Ghost container image to deploy.',
))

task_role_arn = t.add_parameter(Parameter(
    'TaskRoleARN',
    Type='String',
    Description='The ARN of the role for the task.',
))

execution_role_arn = t.add_parameter(Parameter(
    'ExecutionRoleARN',
    Type='String',
    Description='The ARN of the execution role for the task.',
))

ghost_lb_target_arn = t.add_parameter(Parameter(
    'GhostLBTargetARN',
    Type='String',
    Description='The ARN of the ALB Target Group for Ghost.',
))

ghost_vpc = t.add_parameter(Parameter(
    'GhostVPC',
    Type='AWS::EC2::VPC::Id',
    Description='A VPC subnet ID for the container.',
))

ghost_subnet = t.add_parameter(Parameter(
    'GhostSubnet',
    Type='AWS::EC2::Subnet::Id',
    Description='A VPC subnet ID for the container.',
))

ghost_subnet2 = t.add_parameter(Parameter(
    'GhostSubnet2',
    Type='AWS::EC2::Subnet::Id',
    Description='A 2nd VPC subnet ID for the container.',
))

ghost_loggroup = t.add_parameter(Parameter(
    'GhostLogGroup',
    Type='String',
    Description='The Name of the Log Group to log to.',
))

ghost_securitygroup = t.add_parameter(Parameter(
    'GhostSecurityGroup',
    Type='AWS::EC2::SecurityGroup::Id',
    Description='The ID of the Security Group for the Tasks.',
))

ghost_dbhost = t.add_parameter(Parameter(
    'GhostDBHost',
    Type='String',
    Description='The FQDN of the Database.',
))

ghost_url = t.add_parameter(Parameter(
    'GhostURL',
    Type='String',
    Description='The URL of the service (e.g. https://ghost.example.com).',
))

# Create the Resources

ghost_task_definition = t.add_resource(TaskDefinition(
    'GhostTaskDefinition',
    RequiresCompatibilities=['FARGATE'],
    Cpu='512',
    Memory='1GB',
    NetworkMode='awsvpc',
    TaskRoleArn=Ref(task_role_arn),
    ExecutionRoleArn=Ref(execution_role_arn),
    ContainerDefinitions=[
        ContainerDefinition(
            Name='ghost',
            Image=Ref(ghost_image),
            Essential=True,
            PortMappings=[PortMapping(ContainerPort=2368)],
            Environment=[
                Environment(
                    Name='url',
                    Value=Ref(ghost_url)
                ),
                Environment(
                    Name='database__client',
                    Value='mysql2'
                ),
                Environment(
                    Name='database__connection__host',
                    Value=Ref(ghost_dbhost)
                ),
                Environment(
                    Name='database__connection__user',
                    Value='ghost'
                ),
                Environment(
                    Name='database__connection__database',
                    Value='ghost'
                ),
                Environment(
                    Name='AWSREGION',
                    Value=Ref('AWS::Region')
                )
            ],
            LogConfiguration=LogConfiguration(
                LogDriver='awslogs',
                Options={'awslogs-group': Ref(ghost_loggroup),
                         'awslogs-region': Ref('AWS::Region'),
                         'awslogs-stream-prefix': 'ghost'}
            )
        )
    ]
))

ghost_service = t.add_resource(Service(
    'GhostService',
    Cluster=Ref(cluster),
    DesiredCount=1,
    TaskDefinition=Ref(ghost_task_definition),
    LaunchType='FARGATE',
    LoadBalancers=[
        LoadBalancer(
            ContainerName='ghost',
            ContainerPort=2368,
            TargetGroupArn=Ref(ghost_lb_target_arn)
        )
    ],
    NetworkConfiguration=NetworkConfiguration(
        AwsvpcConfiguration=AwsvpcConfiguration(
            Subnets=[Ref(ghost_subnet), Ref(ghost_subnet2)],
            SecurityGroups=[Ref(ghost_securitygroup)],
        )
    )
))

# Create the required Outputs

# Output the Fargate Service Name
t.add_output(Output(
    "GhostFargateServiceName",
    Value=GetAtt(ghost_service, "Name"),
    Description="Ghost Fargate Service Name"
))

print(t.to_json())