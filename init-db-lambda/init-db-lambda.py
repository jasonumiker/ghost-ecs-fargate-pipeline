import pymysql
import os
import boto3
import logging
import json
import time
from botocore.vendored import requests

log = logging.getLogger()
log.setLevel(logging.INFO)

SUCCESS = "SUCCESS"
FAILED = "FAILED"

# rds settings
rds_host = os.environ['dbhost']
name = os.environ['dbuser']
db_name = os.environ['dbname']
db_id = os.environ['dbid']
region = os.environ['awsregion']

def handler(event, context):
    password = event['ResourceProperties']['Password']
    event['ResourceProperties']['Password'] = ""
    log.info("Event: " + str(event))

    if (event['RequestType'] == 'Delete'):
        response = send(event,context, SUCCESS, {}, None)
        return {'Response' : response}

    else:
        try:
            client = boto3.client('rds', region_name=region)
            rdsresponse = client.modify_db_instance(
                EnableIAMDatabaseAuthentication=True,
                ApplyImmediately=True,
                DBInstanceIdentifier=db_id
            )
            log.info("RDS Modify Response: " + str(rdsresponse))
            db_resource_id=rdsresponse['DBInstance']['DbiResourceId']
            log.info("DB Resource ID: " + str(db_resource_id))
            #Give the change a minute to take on the RDS before creating the user
            time.sleep(90)

        except Exception as error:
            log.info("RDS Modify Exception: " + str(error))
            response = send(event, context, FAILED, {}, None)
            return {'Response' : response}

        try:
            conn = pymysql.connect(host=rds_host, port=3306, user=name, passwd=password, db=db_name)
            cur = conn.cursor()
            cur.execute("CREATE USER IF NOT EXISTS 'ghost' IDENTIFIED WITH AWSAuthenticationPlugin as 'RDS'")
            conn.commit()
            cur.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, RELOAD, PROCESS, REFERENCES, INDEX, ALTER, "
                "SHOW DATABASES, CREATE TEMPORARY TABLES, LOCK TABLES, EXECUTE, REPLICATION SLAVE, "
                "REPLICATION CLIENT, CREATE VIEW, SHOW VIEW, CREATE ROUTINE, ALTER ROUTINE, CREATE USER, EVENT, "
                "TRIGGER ON *.* TO 'ghost'@'%' WITH GRANT OPTION")
            conn.commit()
            cur.close()
            conn.close()
            response = send(event,context, SUCCESS, {"db_resource_id": db_resource_id}, None)
            return {'Response' : response}

        except pymysql.InternalError as error:
            log.info("mysql error: " + str(error))
            response = send(event, context, FAILED, {}, None)
            return {'Response' : response}


def send(event, context, responseStatus, responseData, physicalResourceId):
    responseUrl = event['ResponseURL']

    log.info("ResponseURL: " + responseUrl)

    responseBody = {}
    responseBody['Status'] = responseStatus
    responseBody['Reason'] = 'See the details in CloudWatch Log Stream: ' + context.log_stream_name
    responseBody['PhysicalResourceId'] = physicalResourceId or context.log_stream_name
    responseBody['StackId'] = event['StackId']
    responseBody['RequestId'] = event['RequestId']
    responseBody['LogicalResourceId'] = event['LogicalResourceId']
    responseBody['Data'] = responseData

    json_responseBody = json.dumps(responseBody)

    log.info("Response body: " + str(json_responseBody))

    headers = {
        'content-type': '',
        'content-length': str(len(json_responseBody))
    }

    try:
        response = requests.put(responseUrl,
                                data=json_responseBody,
                                headers=headers)
        log.info("Status code: " + str(response.reason))
        return SUCCESS
    except Exception as e:
        log.error("send(..) failed executing requests.put(..): " + str(e))
        return FAILED