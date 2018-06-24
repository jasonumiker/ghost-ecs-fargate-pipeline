# Template to deploy Cloud9 IDE
# By Jason Umiker (jason.umiker@gmail.com)

from troposphere import Template, Parameter, Ref, cloud9

t = Template()
t.add_version('2010-09-09')

# Get the required Parameters

Subnet = t.add_parameter(Parameter(
    'Subnet',
    Type='AWS::EC2::Subnet::Id',
    Description='The subnet ID',
))

CodeCommitRepoUrl = t.add_parameter(Parameter(
    'CodeCommitRepoUrl',
    Type='String',
    Description='The CodeCommit Repo Clone URL',
))

InstanceType = t.add_parameter(Parameter(
    'InstanceType',
    Type='String',
    Default='t2.micro',
    Description='The Instance Type'
))

Cloud9Name = t.add_parameter(Parameter(
    'Cloud9Name',
    Type='String',
    Default='Ghost',
    Description='The Name of the Cloud9'
))

# Create the required Resources

ghost_cloud9 = t.add_resource(cloud9.EnvironmentEC2(
    "GhostCloud9",
    Repositories=[cloud9.Repository(
        PathComponent='/ghost-ecs-fargate-pipeline',
        RepositoryUrl=Ref(CodeCommitRepoUrl)
    )],
    InstanceType=Ref(InstanceType),
    Name=Ref(Cloud9Name),
    SubnetId=Ref(Subnet)
))

print(t.to_json())