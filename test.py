from datetime import datetime
import os
import uuid
import requests

# Fake timezones, so just adjust for your offset
test_data = """117 <40>1 {}+00:00 host app web.3 - State changed from starting to {}
119 <40>1 {}+00:00 host app web.3 - Starting process with command `bundle exec rackup config.ru -p 24405`""".format(
    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), uuid.uuid4(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")
)

request = requests.post(
    os.environ["API_URL"],
    data=test_data,
    headers={"X-Forwarded-Proto": "https", "Content-Type": "application/logplex-1", "Logplex-Msg-Count": "2"},
)

print(request.status_code, request.reason)
print(request.text[:300])
