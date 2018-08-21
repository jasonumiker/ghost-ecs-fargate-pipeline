# Template to deploy VPC, ECS Cluster, Dependencies, Ghost to Fargate and set up a Ghost container CodePipeline
# By Jason Umiker (jason.umiker@gmail.com)

from troposphere import Template, Parameter, Ref, GetAtt, Join, Output, Condition, Equals, cloudformation, ecs, codecommit

t = Template()
t.add_version("2010-09-09")

# Get the required Parameters

keypair_name = t.add_parameter(Parameter(
    "KeypairName",
    Type="AWS::EC2::KeyPair::KeyName",
    Description="The name of your EC2 KeyPair for SSH.",
))

db_password = t.add_parameter(Parameter(
    "DBPassword",
    NoEcho=True,{
    "AWSTemplateFormatVersion": "2010-09-09",
    "Conditions": {
        "Cloud9Condition": {
            "Fn::Equals": [
                {
                    "Ref": "DeployCloud9"
                },
                "true"
            ]
        }
    },
    "Outputs": {
        "ALBURL": {
            "Description": "URL of the ALB",
            "Value": {
                "Fn::GetAtt": [
                    "DepdendenciesStack",
                    "Outputs.ALBURL"
                ]
            }
        }
    },
    "Parameters": {
        "DBPassword": {
            "Description": "The database admin account password",
            "NoEcho": true,
            "Type": "String"
        },
        "DeployCloud9": {
            "AllowedValues": [
                "true",
                "false"
            ],
            "Default": "true",
            "Description": "Whether to deploy Cloud9",
            "Type": "String"
        },
        "GhostImage": {
            "Default": "jasonumiker/ghost:latest",
            "Description": "The Ghost image to deploy",
            "Type": "String"
        },
        "KeyAdminARN": {
            "Description": "The ARN for the User/Role that can manage the RDS KMS key (e.g. arn:aws:iam::111122223333:root)",
            "Type": "String"
        },
        "KeypairName": {
            "Description": "The name of your EC2 KeyPair for SSH.",
            "Type": "AWS::EC2::KeyPair::KeyName"
        }
    },
    "Resources": {
        "ClairFargateStack": {
            "Properties": {
                "Parameters": {
                    "ClairDBPassword": {
                        "Ref": "DBPassword"
                    },
                    "ClairImage": "jasonumiker/clair:latest",
                    "ClairSubnet": {
                        "Fn::GetAtt": [
                            "VPCStack",
                            "Outputs.PrivateSubnet1AID"
                        ]
                    },
                    "ClairSubnet2": {
                        "Fn::GetAtt": [
                            "VPCStack",
                            "Outputs.PrivateSubnet2AID"
                        ]
                    },
                    "ClairVPC": {
                        "Fn::GetAtt": [
                            "VPCStack",
                            "Outputs.VPCID"
                        ]
                    },
                    "Cluster": "Ghost"
                },
                "TemplateURL": "https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/clair-deploy-fargate.template"
            },
            "Type": "AWS::CloudFormation::Stack"
        },
        "Cloud9Stack": {
            "Condition": "Cloud9Condition",
            "DependsOn": "InitCodeCommitStack",
            "Properties": {
                "Parameters": {
                    "CodeCommitRepoUrl": {
                        "Fn::GetAtt": [
                            "GhostRepo",
                            "CloneUrlHttp"
                        ]
                    },
                    "Subnet": {
                        "Fn::GetAtt": [
                            "VPCStack",
                            "Outputs.PublicSubnet1ID"
                        ]
                    }
                },
                "TemplateURL": "https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/cloud9.template"
            },
            "Type": "AWS::CloudFormation::Stack"
        },
        "DepdendenciesStack": {
            "DependsOn": "InitDBLambdaInit",
            "Properties": {
                "Parameters": {
                    "ALBSubnet": {
                        "Fn::GetAtt": [
                            "VPCStack",
                            "Outputs.PublicSubnet1ID"
                        ]
                    },
                    "ALBSubnet2": {
                        "Fn::GetAtt": [
                            "VPCStack",
                            "Outputs.PublicSubnet2ID"
                        ]
                    },
                    "CRS3Bucket": {
                        "Fn::GetAtt": [
                            "InitDBLambdaBuild",
                            "Outputs.OutputBucket"
                        ]
                    },
                    "DBMultiAZ": "False",
                    "DBPassword": {
                        "Ref": "DBPassword"
                    },
                    "DBSubnet": {
                        "Fn::GetAtt": [
                            "VPCStack",
                            "Outputs.PrivateSubnet1AID"
                        ]
                    },
                    "DBSubnet2": {
                        "Fn::GetAtt": [
                            "VPCStack",
                            "Outputs.PrivateSubnet2AID"
                        ]
                    },
                    "DBVPC": {
                        "Fn::GetAtt": [
                            "VPCStack",
                            "Outputs.VPCID"
                        ]
                    },
                    "KeyAdminARN": {
                        "Ref": "KeyAdminARN"
                    }
                },
                "TemplateURL": "https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/dependencies.template"
            },
            "Type": "AWS::CloudFormation::Stack"
        },
        "ECSCluster": {
            "Properties": {
                "ClusterName": "Ghost"
            },
            "Type": "AWS::ECS::Cluster"
        },
        "GhostContainerBuildStack": {
            "Properties": {
                "Parameters": {
                    "BuildSubnet": {
                        "Fn::GetAtt": [
                            "VPCStack",
                            "Outputs.PrivateSubnet1AID"
                        ]
                    },
                    "BuildSubnet2": {
                        "Fn::GetAtt": [
                            "VPCStack",
                            "Outputs.PrivateSubnet2AID"
                        ]
                    },
                    "BuildVPC": {
                        "Fn::GetAtt": [
                            "VPCStack",
                            "Outputs.VPCID"
                        ]
                    },
                    "ClairURL": {
                        "Fn::GetAtt": [
                            "ClairFargateStack",
                            "Outputs.ClairURL"
                        ]
                    }
                },
                "TemplateURL": "https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/ghost-container-build.template"
            },
            "Type": "AWS::CloudFormation::Stack"
        },
        "GhostContainerPipelineStack": {
            "Properties": {
                "Parameters": {
                    "CodeBuildProject": "ghost-clair-build",
                    "CodeCommitRepo": "ghost-ecs-fargate-pipeline",
                    "DependencyStackName": {
                        "Fn::GetAtt": [
                            "DepdendenciesStack",
                            "Outputs.StackName"
                        ]
                    },
                    "ECSClusterName": "Ghost"
                },
                "TemplateURL": "https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/ghost-container-build-pipeline.template"
            },
            "Type": "AWS::CloudFormation::Stack"
        },
        "GhostRepo": {
            "Properties": {
                "RepositoryName": "ghost-ecs-fargate-pipeline"
            },
            "Type": "AWS::CodeCommit::Repository"
        },
        "InitCodeCommitStack": {
            "DependsOn": "DepdendenciesStack",
            "Properties": {
                "Parameters": {
                    "CodeCommitRepoAddr": {
                        "Fn::GetAtt": [
                            "GhostRepo",
                            "CloneUrlHttp"
                        ]
                    }
                },
                "TemplateURL": "https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/init-codecommit.template"
            },
            "Type": "AWS::CloudFormation::Stack"
        },
        "InitDBLambdaBuild": {
            "Properties": {
                "TemplateURL": "https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/init-db-lambda-build.template"
            },
            "Type": "AWS::CloudFormation::Stack"
        },
        "InitDBLambdaInit": {
            "DependsOn": "InitDBLambdaBuild",
            "Properties": {
                "TemplateURL": "https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/init-db-lambda-init.template"
            },
            "Type": "AWS::CloudFormation::Stack"
        },
        "VPCStack": {
            "Properties": {
                "Parameters": {
                    "AvailabilityZones": {
                        "Fn::Join": [
                            "",
                            [
                                {
                                    "Ref": "AWS::Region"
                                },
                                "a,",
                                {
                                    "Ref": "AWS::Region"
                                },
                                "b"
                            ]
                        ]
                    },
                    "KeyPairName": {
                        "Ref": "KeypairName"
                    },
                    "NumberOfAZs": "2"
                },
                "TemplateURL": "https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/vpc.template"
            },
            "Type": "AWS::CloudFormation::Stack"
        }
    }
}
    Description="The database admin account password",
    Type="String",
))

ghost_image = t.add_parameter(Parameter(
    "GhostImage",
    Type="String",
    Description="The Ghost image to deploy",
    Default="jasonumiker/ghost:latest"
))

key_admin_ARN = t.add_parameter(Parameter(
    "KeyAdminARN",
    Type="String",
    Description="The ARN for the User/Role that can manage the RDS KMS key (e.g. arn:aws:iam::111122223333:root)",
))

deploy_cloud9 = t.add_parameter(Parameter(
    "DeployCloud9",
    Type="String",
    Description="Whether to deploy Cloud9",
    AllowedValues=["true","false"],
    Default="true"
))

cloud9_condition = t.add_condition("Cloud9Condition", Equals(Ref(deploy_cloud9), "true"))


# Create the ECS Cluster
ECSCluster = t.add_resource(ecs.Cluster(
    "ECSCluster",
    ClusterName="Ghost"
))

# Create the CodeCommit Repo
GhostRepo = t.add_resource(codecommit.Repository(
    "GhostRepo",
    RepositoryName="ghost-ecs-fargate-pipeline"
))

# Create each required stack

init_db_lambda_build = t.add_resource(cloudformation.Stack(
    "InitDBLambdaBuild",
    TemplateURL="https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/init-db-lambda-build.template",
))

init_db_lambda_init = t.add_resource(cloudformation.Stack(
    "InitDBLambdaInit",
    TemplateURL="https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/init-db-lambda-init.template",
    DependsOn="InitDBLambdaBuild"
))

vpc_stack = t.add_resource(cloudformation.Stack(
    "VPCStack",
    Parameters={
        "AvailabilityZones": Join("", [Ref("AWS::Region"), "a,", Ref("AWS::Region"), "b"]),
        "NumberOfAZs": "2",
        "KeyPairName": Ref(keypair_name),
    },
    TemplateURL="https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/vpc.template",
))

dependencies_stack = t.add_resource(cloudformation.Stack(
    "DepdendenciesStack",
    Parameters={
        "DBVPC": GetAtt(vpc_stack, "Outputs.VPCID"),
        "DBSubnet": GetAtt(vpc_stack, "Outputs.PrivateSubnet1AID"),
        "DBSubnet2": GetAtt(vpc_stack, "Outputs.PrivateSubnet2AID"),
        "ALBSubnet": GetAtt(vpc_stack, "Outputs.PublicSubnet1ID"),
        "ALBSubnet2": GetAtt(vpc_stack, "Outputs.PublicSubnet2ID"),
        "DBPassword": Ref(db_password),
        "DBMultiAZ": "False",
        "KeyAdminARN": Ref(key_admin_ARN),
        "CRS3Bucket" : GetAtt(init_db_lambda_build, "Outputs.OutputBucket"),
    },
    TemplateURL="https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/dependencies.template",
    DependsOn="InitDBLambdaInit"
))

clair_fargate_stack = t.add_resource(cloudformation.Stack(
    "ClairFargateStack",
    Parameters={
        "Cluster": "Ghost",
        "ClairSubnet": GetAtt(vpc_stack, "Outputs.PrivateSubnet1AID"),
        "ClairSubnet2": GetAtt(vpc_stack, "Outputs.PrivateSubnet2AID"),
        "ClairVPC": GetAtt(vpc_stack, "Outputs.VPCID"),
        "ClairImage": "jasonumiker/clair:latest",
        "ClairDBPassword": Ref(db_password)
    },
    TemplateURL="https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/clair-deploy-fargate.template",
))

ghost_container_build_stack = t.add_resource(cloudformation.Stack(
    "GhostContainerBuildStack",
    Parameters={
        "BuildSubnet": GetAtt(vpc_stack, "Outputs.PrivateSubnet1AID"),
        "BuildSubnet2": GetAtt(vpc_stack, "Outputs.PrivateSubnet2AID"),
        "BuildVPC": GetAtt(vpc_stack, "Outputs.VPCID"),
        "ClairURL": GetAtt(clair_fargate_stack, "Outputs.ClairURL"),
    },
    TemplateURL="https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/ghost-container-build.template",
))

ghost_container_pipeline_stack = t.add_resource(cloudformation.Stack(
    "GhostContainerPipelineStack",
    Parameters={
        "CodeCommitRepo": "ghost-ecs-fargate-pipeline",
        "CodeBuildProject": "ghost-clair-build",
        "ECSClusterName": "Ghost",
        "DependencyStackName": GetAtt(dependencies_stack, "Outputs.StackName"),
    },
    TemplateURL="https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/ghost-container-build-pipeline.template",
))

init_codecommit_stack = t.add_resource(cloudformation.Stack(
    "InitCodeCommitStack",
    Parameters={"CodeCommitRepoAddr": GetAtt(GhostRepo, "CloneUrlHttp")},
    TemplateURL="https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/init-codecommit.template",
    DependsOn="DepdendenciesStack"
))

cloud9_stack = t.add_resource(cloudformation.Stack(
    "Cloud9Stack",
    Parameters={
        "Subnet": GetAtt(vpc_stack, "Outputs.PublicSubnet1ID"),
        "CodeCommitRepoUrl": GetAtt(GhostRepo, "CloneUrlHttp")
    },
    TemplateURL="https://s3.amazonaws.com/ghost-ecs-fargate-pipeline/cloud9.template",
    DependsOn="InitCodeCommitStack",
    Condition=cloud9_condition
))

# Output the ALB URL
t.add_output(Output(
    "ALBURL",
    Description="URL of the ALB",
    Value=GetAtt(dependencies_stack, "Outputs.ALBURL")
))

print(t.to_json())