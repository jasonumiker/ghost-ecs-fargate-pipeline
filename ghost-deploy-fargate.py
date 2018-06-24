# Troposphere to create CloudFormation template of ghost ECS deployment
# By Jason Umiker (jason.umiker@gmail.com)

from troposphere import Parameter, Ref, Template, Output, GetAtt, ImportValue, Sub
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

dependency_stack_name = t.add_parameter(Parameter(
    'DependencyStackName',
    Type='String',
    Description='The name of the Dependency Stack to retrieve CloudFormation Exports',
))

# Create the Resources

ghost_task_definition = t.add_resource(TaskDefinition(
    'GhostTaskDefinition',
    RequiresCompatibilities=['FARGATE'],
    Cpu='512',
    Memory='1GB',
    NetworkMode='awsvpc',
    TaskRoleArn=ImportValue(Sub("${DependencyStackName}-TaskRoleArn")),
    ExecutionRoleArn=ImportValue(Sub("${DependencyStackName}-TaskExecutionRoleArn")),
    ContainerDefinitions=[
        ContainerDefinition(
            Name='ghost',
            Image=Ref(ghost_image),
            Essential=True,
            PortMappings=[PortMapping(ContainerPort=2368)],
            Environment=[
                Environment(
                    Name='url',
                    Value=ImportValue(Sub("${DependencyStackName}-ALBURL")),
                ),
                Environment(
                    Name='database__client',
                    Value='mysql2'
                ),
                Environment(
                    Name='database__connection__host',
                    Value=ImportValue(Sub("${DependencyStackName}-GhostDBHost")),
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
                Options={'awslogs-group': ImportValue(Sub("${DependencyStackName}-GhostLogGroupName")),
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
            TargetGroupArn=ImportValue(Sub("${DependencyStackName}-GhostTG"))
        )
    ],
    NetworkConfiguration=NetworkConfiguration(
        AwsvpcConfiguration=AwsvpcConfiguration(
            Subnets=[ImportValue(Sub("${DependencyStackName}-Subnet1")), ImportValue(Sub("${DependencyStackName}-Subnet2"))],
            SecurityGroups=[ImportValue(Sub("${DependencyStackName}-GhostSG"))],
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