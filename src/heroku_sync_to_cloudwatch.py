"""Sample handler for parsing Heroku logplex drain events (https://devcenter.heroku.com/articles/log-drains#https-drains).
Expects messages to be framed with the syslog TCP octet counting method (https://tools.ietf.org/html/rfc6587#section-3.4.1).
This is designed to be run as a Python3.6 lambda.
"""

from botocore.exceptions import ClientError
from collections import defaultdict
from pyparsing import Word, Suppress, nums, Optional, Regex, pyparsing_common, alphanums
import boto3
import iso8601
import json
import requests


cloudwatch = boto3.client("logs")


class Parser(object):
    def __init__(self):
        ints = Word(nums)

        priority = Suppress("<") + ints + Suppress(">")
        version = ints
        timestamp = pyparsing_common.iso8601_datetime
        hostname = Word(alphanums + "_" + "-" + ".")
        source = Word(alphanums + "_" + "-" + ".")
        app = (
            Word(alphanums + "(" + ")" + "/" + "-" + "_" + ".")
            + Optional(Suppress("[") + ints + Suppress("]"))
            + Suppress("-")
        )
        message = Regex(".*")
        self.__pattern = priority + version + timestamp + hostname + source + app + message

    def parse(self, line):
        parsed = self.__pattern.parseString(line)

        # https://tools.ietf.org/html/rfc5424#section-6
        # get priority/severity
        priority = int(parsed[0])
        severity = priority & 0x07
        facility = priority >> 3

        payload = {}
        payload["priority"] = priority
        payload["severity"] = severity
        payload["facility"] = facility
        payload["version"] = parsed[1]
        payload["timestamp"] = iso8601.parse_date(parsed[2])
        payload["hostname"] = parsed[3]
        payload["source"] = parsed[4]
        payload["app"] = parsed[5]
        payload["message"] = parsed[6]

        return payload


parser = Parser()


def lambda_handler(event, context):
    handle_lambda_proxy_event(event)
    return {"isBase64Encoded": False, "statusCode": 200, "headers": {"Content-Length": 0}}


# split into chunks
def get_chunk(payload: bytes):
    # payload = payload.lstrip()
    msg_len, syslog_msg_payload = payload.split(b" ", maxsplit=1)
    if msg_len == "":
        raise Exception(f"failed to parse heroku logplex payload: '{payload}'")
    try:
        msg_len = int(msg_len)
    except Exception as ex:
        raise Exception(f"failed to parse {msg_len} as int, payload: {payload}") from ex

    # only grab msg_len bytes of syslog_msg
    syslog_msg = syslog_msg_payload[0:msg_len]
    next_payload = syslog_msg_payload[msg_len:]

    yield syslog_msg.decode("utf-8")

    if next_payload:
        yield from get_chunk(next_payload)


def handle_lambda_proxy_event(event):
    body = event["body"]
    headers = event["headers"]

    print("Received messages", headers["Logplex-Msg-Count"])

    # sanity-check source
    assert body
    assert headers
    assert headers["X-Forwarded-Proto"] == "https"
    assert headers["Content-Type"] == "application/logplex-1"

    # group app_messages by source,app
    app_messages = defaultdict(dict)
    chunk_count = 0
    for chunk in get_chunk(bytes(body, "utf-8")):
        chunk_count += 1
        event = parser.parse(chunk)
        if event["source"] not in app_messages[event["app"]]:
            app_messages[event["app"]][event["source"]] = list()
        app_messages[event["app"]][event["source"]].append(
            {"timestamp": int(round(event["timestamp"].timestamp() * 1000)), "message": event["message"]}
        )

    for app, sources in app_messages.items():
        for source, messages in sources.items():
            if not messages:
                continue
            send_to_cloudwatch(cloudwatch, app, source, sorted(messages, key=lambda x: x["timestamp"]))

    # sanity-check number of parsed messages
    assert int(headers["Logplex-Msg-Count"]) == chunk_count

    return ""


def send_to_cloudwatch(cloudwatch, logGroup, logStream, events):
    print("Draining logs", logGroup, logStream, str(len(events)))

    stream_info = cloudwatch.describe_log_streams(logGroupName=logGroup, logStreamNamePrefix=logStream)["logStreams"]

    if stream_info and "uploadSequenceToken" in stream_info[0]:
        cloudwatch.put_log_events(
            logGroupName=logGroup,
            logStreamName=logStream,
            logEvents=events,
            sequenceToken=stream_info[0]["uploadSequenceToken"],
        )
    else:
        try:
            cloudwatch.create_log_stream(logGroupName=logGroup, logStreamName=logStream)
        except ClientError as error:
            print("Error creating stream, maybe it exists", logStream, str(error))
        cloudwatch.put_log_events(logGroupName=logGroup, logStreamName=logStream, logEvents=events)
