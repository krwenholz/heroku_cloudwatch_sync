"""Handler for parsing Heroku logplex drain events (https://devcenter.heroku.com/articles/log-drains#https-drains).

Expects messages to be framed with the syslog TCP octet counting method (https://tools.ietf.org/html/rfc6587#section-3.4.1).
Designed as a Python3.7 lambda.
"""

import json
import logging
import time

from base64 import b64decode
from collections import defaultdict
from syslog import LOG_DEBUG, LOG_INFO, LOG_NOTICE, LOG_WARNING

import boto3


log = logging.getLogger("app.heroku.drain")


def respond(err, res=None):
    return {
        "statusCode": "400" if err else "200",
        "body": err.message if err else json.dumps(res),
        "headers": {"Content-Type": "application/json"},
    }


def lambda_handler(event, context):
    print("Received event: " + json.dumps(event))
    handle_lambda_proxy_event(event)
    return {"isBase64Encoded": False, "statusCode": 200, "headers": {"Content-Length": 0}}


def handle_lambda_proxy_event(event):
    print(event)
    body = event["body"]
    headers = event["headers"]
    logGroup = event["pathParameters"]["logGroup"]
    logStreamName = event["pathParameters"]["logStream"]

    if logGroup == "test":
        return respond(None, {"status": "right back at you"})

    # sanity-check source
    assert headers["X-Forwarded-Proto"] == "https"
    assert headers["Content-Type"] == "application/logplex-1"

    # for group_name, sevs in srcapp_msgs.items():
    #    cwl = boto3.client("logs")
    #    for severity, lines in sevs.items():
    #        if not lines:
    #            continue
    #        title = group_name
    #        timestamp = int(round(time.time() * 1000))  # TODO: parse lines to set time to recorded time
    #        # timestamp = evt["timestamp"] ....
    #        events = [{"timestamp": TIMESTAMP, "message": TODO} for foo in bar]
    #        send_to_cloudwatch(cwl, logGroup, logStreamName, timestamp, events)

    # sanity-check number of parsed messages
    assert int(headers["Logplex-Msg-Count"]) == chunk_count


def send_to_cloudwatch(cwl, logGroup, logGroupStream, timestamp, events):
    stream_info = cwl.describe_log_streams(logGroupName=logGroup, logStreamNamePrefix=logGroupStream)["logStreams"][0]
    if "uploadSequenceToken" not in stream_info:
        cwl.put_log_events(
            logGroupName=logGroup, logStreamName=logGroupStream, logEvents=[{"timestamp": timestamp, "message": text}]
        )
    else:
        cwl.put_log_events(
            logGroupName=logGroup,
            logStreamName=logGroupStream,
            logEvents=[events],
            sequenceToken=stream_info["uploadSequenceToken"],
        )
