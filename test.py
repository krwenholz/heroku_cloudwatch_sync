import requests
import os

test_data = """83 <40>1 2012-11-30T06:45:29+00:00 host app web.3 - State changed from starting to up
119 <40>1 2012-11-30T06:45:26+00:00 host app web.3 - Starting process with command `bundle exec rackup config.ru -p 24405`"""

request = requests.post(
    "https://{}.execute-api.us-west-2.amazonaws.com/production/logs".format(os.environ["API_ID"]),
    data=test_data,
    headers={"X-Forwarded-Proto": "https", "Content-Type": "application/logplex-1", "Logplex-Msg-Count": "2"},
)

print(request.status_code, request.reason)
print(request.text[:300])
