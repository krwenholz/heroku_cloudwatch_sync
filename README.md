About
==========================

Adopted from [rwilcox](https://github.com/rwilcox/heroku_cloudwatch_sync) this is the
basic setup for a lambda that reads in your Heroku logs to CloudWatch.

Also some help from [CodeRepice-dev](https://github.com/CodeRecipe-dev/Heroku-log-AWS-cloudwatch).

Using this lambda script
=========================

Import and use the Terraform module like

```
module "logdrain" {
  source               = "git::https://github.com/krwenholz/heroku_cloudwatch_sync.git?ref=master"
  function_name        = "YOUR_LOG_DRAIN_FUNCTION_NAME_HERE"
  region               = "REGION_HERE_USED_FOR_OUTPUT_URL_ONLY"
}
```

Then grab the Lambda URL from the output and use this for your log drain.  The lambda
takes two path parameters at the end: these are the Cloudwatch Logs log group and log
stream to write events to. Decide on these.

```
heroku drains:add <YOUR_LOG_DRAIN_URL>
```

>  TODO(kyle): Create log groups based on parameters
>  TODO(kyle): Write to app specific log group https://gist.github.com/olegdulin/fd18906343d75142a487b9a9da9042e0
>  TODO(kyle): Will need to grab next token https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/logs.html#CloudWatchLogs.Client.put_log_events
