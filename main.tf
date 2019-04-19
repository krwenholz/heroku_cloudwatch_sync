# Config
##############################################
variable function_name {
  default = "heroku_log_drain"
}

variable region {
  default = "us-west-2"
}

# Lambda
# --------------------------------------------------------------------

resource "aws_lambda_function" "this" {
  description      = "Drains Heroku logs into this account."
  filename         = "src/heroku_sync_to_cloudwatch.py"
  function_name    = "${var.function_name}"
  handler          = "update_host_alarms.lambda_handler"
  publish          = true
  role             = "${aws_iam_role.iam_role.arn}"
  runtime          = "python3.7"
  source_code_hash = "${md5(file("src/heroku_sync_to_cloudwatch.py"))}"
  timeout          = "120"
}

# API Gateway
# --------------------------------------------------------------------

resource "aws_api_gateway_rest_api" "api" {
  name = "${var.function_name}"
}

resource "aws_api_gateway_resource" "resource" {
  path_part   = "resource"
  parent_id   = "${aws_api_gateway_rest_api.api.root_resource_id}"
  rest_api_id = "${aws_api_gateway_rest_api.api.id}"
}

resource "aws_api_gateway_method" "method" {
  rest_api_id   = "${aws_api_gateway_rest_api.api.id}"
  resource_id   = "${aws_api_gateway_resource.resource.id}"
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "integration" {
  rest_api_id             = "${aws_api_gateway_rest_api.api.id}"
  resource_id             = "${aws_api_gateway_resource.resource.id}"
  http_method             = "${aws_api_gateway_method.method.http_method}"
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.region}:lambda:path/2015-03-31/functions/${aws_lambda_function.this.arn}/invocations"
}

# IAM
# --------------------------------------------------------------------

data "aws_iam_policy_document" "assume_role_policy" {
  statement {
    actions = ["sts:AssumeRole"]
    sid     = "1"

    principals {
      identifiers = ["lambda.amazonaws.com"]
      type        = "Service"
    }
  }
}

data "aws_iam_policy_document" "lambda_policy_document" {
  statement {
    resources = ["*"]
    sid       = "1"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:DescribeLogStreams",
      "logs:PutLogEvents",
    ]
  }
}

resource "aws_iam_policy" "lambda_policy" {
  name = "${var.function_name}-lambda_policy"

  policy = "${data.aws_iam_policy_document.lambda_policy_document.json}"
}

resource "aws_iam_role" "iam_role" {
  name = "${var.function_name}-lambda_role"

  assume_role_policy = "${data.aws_iam_policy_document.assume_role_policy.json}"
}

resource "aws_iam_role_policy_attachment" "lambda_role_policy_attachment" {
  policy_arn = "${aws_iam_policy.lambda_policy.arn}"
  role       = "${aws_iam_role.iam_role.name}"
}

# Outputs
##############################################
output "function_url" {
  value = "https://${var.function_name}.execute-api.${var.region}.amazonaws.com"
}
