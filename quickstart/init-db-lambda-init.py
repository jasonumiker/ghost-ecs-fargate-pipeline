# Troposphere to create CloudFormation template to kick off CodeBuild for init-db-lambda
# By Jason Umiker (jason.umiker@gmail.com)

from troposphere import Ref, Template, Join, GetAtt
from troposphere import iam, awslambda, cloudformation

class CustomCodeBuildTrigger(cloudformation.AWSCustomObject):
    resource_type = "Custom::CodeBuildTrigger"
    props = {
        'ProjectName': (str, True)
    }

t = Template()

# Create Resources

# Lambda Execution Role
LambdaExecutionRole = t.add_resource(iam.Role(
    "LambdaExecutionRole",
    AssumeRolePolicyDocument={
        "Statement": [
            {
                'Effect': 'Allow',
                'Principal': {'Service': 'lambda.amazonaws.com'},
                "Action": "sts:AssumeRole"
            }
        ]
    }
))

# CodeBuild Service Policy
LambdaPolicy = t.add_resource(iam.PolicyType(
    "LambdaPolicy",
    PolicyName="LambdaPolicy",
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
                            "Sid": "CodeBuildPolicy",
                            "Effect": "Allow",
                            "Action": [
                                "codebuild:StartBuild"
                            ],
                            "Resource": [
                                "*"
                            ]
                        },
                    ]},
    Roles=[Ref(LambdaExecutionRole)],
))

# Create Lambda to trigger the CodeBuild
code = [
    "import os",
    "import boto3",
    "import logging",
    "import json",
    "import time",
    "from botocore.vendored import requests",
    "",
    "log = logging.getLogger()",
    "log.setLevel(logging.INFO)",
    "",
    "SUCCESS = \"SUCCESS\"",
    "FAILED = \"FAILED\"",
    "",
    "def handler(event, context):",
    "    build = {'projectName': event['ResourceProperties']['ProjectName']}",
    "    log.info(\"Event: \" + str(event))",
    "",
    "    if (event['RequestType'] == 'Delete'):",
    "        response = send(event,context, SUCCESS, {}, None)",
    "        return {'Response' : response}",
    "",
    "    else:",
    "        try:",
    "            client = boto3.client('codebuild')",
    "            codebuildresponse = client.start_build(**build)",
    "            log.info(\"CodeBuild Response: \" + str(codebuildresponse))",
    "            response = send(event,context, SUCCESS, {}, None)",
    "",
    "        except Exception as error:",
    "            log.info(\"CodeBuild Exception: \" + str(error))",
    "            response = send(event, context, FAILED, {}, None)",
    "            return {'Response' : response}",
    "",
    "def send(event, context, responseStatus, responseData, physicalResourceId):",
    "    responseUrl = event['ResponseURL']",
    "",
    "    log.info(\"ResponseURL: \" + responseUrl)",
    "",
    "    responseBody = {}",
    "    responseBody['Status'] = responseStatus",
    "    responseBody['Reason'] = 'See the details in CloudWatch Log Stream: ' + context.log_stream_name",
    "    responseBody['PhysicalResourceId'] = physicalResourceId or context.log_stream_name",
    "    responseBody['StackId'] = event['StackId']",
    "    responseBody['RequestId'] = event['RequestId']",
    "    responseBody['LogicalResourceId'] = event['LogicalResourceId']",
    "    responseBody['Data'] = responseData",
    "",
    "    json_responseBody = json.dumps(responseBody)",
    "",
    "    log.info(\"Response body: \" + str(json_responseBody))",
    "",
    "    headers = {",
    "        'content-type': '',",
    "        'content-length': str(len(json_responseBody))",
    "    }",
    "",
    "    try:",
    "        response = requests.put(responseUrl,",
    "                                data=json_responseBody,",
    "                                headers=headers)",
    "        log.info(\"Status code: \" + str(response.reason))",
    "        return SUCCESS",
    "        ",
    "    except Exception as e:",
    "        log.error(\"Error sending response: \" + str(e))",
    "        return FAILED",
]

CodeBuildInitFunction = t.add_resource(awslambda.Function(
    "CodeBuildInitFunction",
    Code=awslambda.Code(
        ZipFile=Join("\n", code)
    ),
    Handler="index.handler",
    Role=GetAtt("LambdaExecutionRole", "Arn"),
    Runtime="python3.6",
    MemorySize="128",
    Timeout="180",
    DependsOn=LambdaPolicy
))

CodeBuildInit = t.add_resource(CustomCodeBuildTrigger(
    "CodeBuildInit",
    ServiceToken=GetAtt(CodeBuildInitFunction, 'Arn'),
    ProjectName="init-db-lambda-build",
    DependsOn=CodeBuildInitFunction
))

print(t.to_json())