"""Handler for parsing Heroku logplex drain events (https://devcenter.heroku.com/articles/log-drains#https-drains).

Expects messages to be framed with the syslog TCP octet counting method (https://tools.ietf.org/html/rfc6587#section-3.4.1).
Designed as a Python3.7 lambda.
"""

import json
import time
import boto3
import logging

#  TODO(kyle): Remove use of this
import iso8601

# import requests
from base64 import b64decode

#  TODO(kyle): Remove use of this
from pyparsing import Word, Suppress, nums, Optional, Regex, pyparsing_common, alphanums
from syslog import LOG_DEBUG, LOG_WARNING, LOG_INFO, LOG_NOTICE
from collections import defaultdict

#  TODO(kyle): Add basic check for password and username


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
    body = event["body"]
    headers = event["headers"]
    logGroup = event["pathParameters"]["logGroup"]
    logStreamName = event["pathParameters"]["logStream"]

    if logGroup == "test":
        return respond(None, {"status": "right back at you"})

    # sanity-check source
    assert headers["X-Forwarded-Proto"] == "https"
    assert headers["Content-Type"] == "application/logplex-1"

    # split into chunks
    def get_chunk(payload):
        msg_len, syslog_msg_payload = payload.split(" ", maxsplit=1)
        msg_len = int(msg_len)

        # only grab msg_len bytes of syslog_msg
        syslog_msg = syslog_msg_payload[0:msg_len]
        next_payload = syslog_msg_payload[msg_len:]

        yield syslog_msg

        if next_payload:
            yield from get_chunk(next_payload)

    # group messages by source,app
    # format for slack
    srcapp_msgs = defaultdict(dict)
    chunk_count = 0
    for chunk in get_chunk(body):
        chunk_count += 1
        evt = parser.parse(chunk)

        # if not filter_slack_msg(evt):
        #    # skip stuff filtered out
        #    continue

        # add to group
        sev = evt["severity"]
        group_name = f"SEV:{sev} {evt['source']} {evt['appname']}"
        if sev not in srcapp_msgs[group_name]:
            srcapp_msgs[group_name][sev] = list()
        body = evt["message"]
        srcapp_msgs[group_name][sev].append(str(evt["timestamp"]) + ": " + evt["message"])

    for group_name, sevs in srcapp_msgs.items():
        cwl = boto3.client("logs")
        for severity, lines in sevs.items():
            if not lines:
                continue
            title = group_name
            # format the syslog event as a slack message attachment
            # slack_att = slack_format_attachment(log_msg=None, log_rec=evt)
            # text = "\n" + "\n".join(lines)
            # slack(text=text, title=title, attachments=[slack_att], channel=channel, severity=severity)
            timestamp = int(round(time.time() * 1000))  # TODO: parse lines to set time to recorded time
            # timestamp = evt["timestamp"] ....
            for text in lines:
                send_to_cloudwatch(cwl, logGroup, logStreamName, timestamp, text)

    # sanity-check number of parsed messages
    assert int(headers["Logplex-Msg-Count"]) == chunk_count

    return ""


def send_to_cloudwatch(cwl, logGroup, logGroupStream, timestamp, text):
    stream_info = cwl.describe_log_streams(logGroupName=logGroup, logStreamNamePrefix=logGroupStream)["logStreams"][0]
    if "uploadSequenceToken" not in stream_info:
        cwl.put_log_events(
            logGroupName=logGroup, logStreamName=logGroupStream, logEvents=[{"timestamp": timestamp, "message": text}]
        )
    else:
        cwl.put_log_events(
            logGroupName=logGroup,
            logStreamName=logGroupStream,
            logEvents=[{"timestamp": timestamp, "message": text}],
            sequenceToken=stream_info["uploadSequenceToken"],
        )
