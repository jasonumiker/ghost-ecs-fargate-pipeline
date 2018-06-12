# Troposphere to create CloudFormation template for the ECS roles
# By Jason Umiker (jason.umiker@gmail.com)

from troposphere import Template, Ref, Output, GetAtt, iam

t = Template()
t.add_version('2010-09-09')

# Create the Instance Role
InstanceRole = t.add_resource(iam.Role(
    "ECSInstanceRole",
    AssumeRolePolicyDocument={
        'Statement': [{
            'Effect': 'Allow',
            'Principal': {'Service': ['ec2.amazonaws.com']},
            'Action': ["sts:AssumeRole"]
        }]},
))

InstanceProfile = t.add_resource(iam.InstanceProfile(
    "ECSInstanceProfile",
    Roles=[Ref(InstanceRole)]
))

# Create the Spot Fleet Role
SpotFleetRole = t.add_resource(iam.Role(
    "ECSSpotFleetRole",
    AssumeRolePolicyDocument={
        'Statement': [{
            'Effect': 'Allow',
            'Principal': {'Service': ['spotfleet.amazonaws.com']},
            'Action': ["sts:AssumeRole"]
        }]},
))

# Create the ECS Instance Policy
InstancePolicy = t.add_resource(iam.PolicyType(
    "ECSInstancePolicy",
    PolicyName="ECSInstancePolicy",
    PolicyDocument={'Version': '2012-10-17',
                    'Statement': [{'Action': ["ecs:CreateCluster",
                                              "ecs:DeregisterContainerInstance",
                                              "ecs:DiscoverPollEndpoint",
                                              "ecs:Poll",
                                              "ecs:RegisterContainerInstance",
                                              "ecs:StartTelemetrySession",
                                              "ecs:UpdateContainerInstancesState",
                                              "ecs:Submit*",
                                              "ecr:GetAuthorizationToken",
                                              "ecr:BatchCheckLayerAvailability",
                                              "ecr:GetDownloadUrlForLayer",
                                              "ecr:BatchGetImage",
                                              "logs:CreateLogStream",
                                              "logs:PutLogEvents"],
                                   'Resource': ['*'],
                                   'Effect': 'Allow'},
                                  ]},
    Roles=[Ref(InstanceRole)],
))

# Create the ECS Instance Policy
SpotFleetPolicy = t.add_resource(iam.PolicyType(
    "ECSSpotFleetPolicy",
    PolicyName="SpotFleetPolicy",
    PolicyDocument={'Version': '2012-10-17',
                    'Statement': [{'Action': ["ec2:DescribeImages",
                                              "ec2:DescribeSubnets",
                                              "ec2:RequestSpotInstances",
                                              "ec2:TerminateInstances",
                                              "ec2:DescribeInstanceStatus",
                                              "iam:PassRole"],
                                   'Resource': ['*'],
                                   'Effect': 'Allow'},
                                  {
                                      "Effect": "Allow",
                                      "Action": [
                                          "elasticloadbalancing:RegisterInstancesWithLoadBalancer"
                                      ],
                                      "Resource": [
                                          "arn:aws:elasticloadbalancing:*:*:loadbalancer/*"
                                      ]
                                  },
                                  {
                                      "Effect": "Allow",
                                      "Action": [
                                          "elasticloadbalancing:RegisterTargets"
                                      ],
                                      "Resource": [
                                          "*"
                                      ]
                                  }
                                  ]},
    Roles=[Ref(SpotFleetRole)],
))

# Output the Instance Role Arn
t.add_output(Output(
    "ECSInstanceRoleArn",
    Value=GetAtt(InstanceRole, "Arn"),
    Description="Instance Role Arn"
))

# Output the Spot Fleet Role Name
t.add_output(Output(
    "ECSSpotFleetRoleName",
    Value=Ref(SpotFleetRole),
    Description="Spot Fleet Role Name"
))

# Output the Instance Profile Name
t.add_output(Output(
    "ECSInstanceProfileName",
    Value=Ref(InstanceProfile),
    Description="Instance Profile Name"
))

print(t.to_json())