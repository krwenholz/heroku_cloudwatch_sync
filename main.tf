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

data "archive_file" "zipped_lambda" {
  output_path = "heroku_sync_to_cloudwatch.zip"
  source_file = "${path.module}/src/heroku_sync_to_cloudwatch.py"
  type        = "zip"
}

resource "aws_lambda_function" "this" {
  description      = "Drains Heroku logs into this account."
  filename         = "heroku_sync_to_cloudwatch.zip"
  function_name    = "${var.function_name}"
  handler          = "heroku_sync_to_cloudwatch.lambda_handler"
  publish          = true
  role             = "${aws_iam_role.iam_role.arn}"
  runtime          = "python3.7"
  source_code_hash = "${data.archive_file.zipped_lambda.output_base64sha256}"
  timeout          = "120"
}

resource "aws_lambda_permission" "post_session_trigger" {
  statement_id  = "allowApiGatewayInvocation"
  action        = "lambda:InvokeFunction"
  function_name = "${aws_lambda_function.this.function_name}"
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.this.execution_arn}/*"
}

# API Gateway
# --------------------------------------------------------------------

resource "aws_api_gateway_rest_api" "this" {
  name = "${var.function_name}"
}

resource "aws_api_gateway_resource" "logs" {
  path_part   = "logs"
  parent_id   = "${aws_api_gateway_rest_api.this.root_resource_id}"
  rest_api_id = "${aws_api_gateway_rest_api.this.id}"
}

resource "aws_api_gateway_resource" "log_group" {
  path_part   = "{log_group}"
  parent_id   = "${aws_api_gateway_resource.logs.id}"
  rest_api_id = "${aws_api_gateway_rest_api.this.id}"
}

# https://www.olicole.net/blog/2017/07/terraforming-aws-a-serverless-website-backend-part-3/
resource "aws_api_gateway_resource" "log_stream" {
  path_part   = "{log_stream}"
  parent_id   = "${aws_api_gateway_resource.log_group.id}"
  rest_api_id = "${aws_api_gateway_rest_api.this.id}"
}

resource "aws_api_gateway_method" "post" {
  rest_api_id   = "${aws_api_gateway_rest_api.this.id}"
  resource_id   = "${aws_api_gateway_resource.log_stream.id}"
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "integration" {
  rest_api_id             = "${aws_api_gateway_rest_api.this.id}"
  resource_id             = "${aws_api_gateway_resource.log_stream.id}"
  http_method             = "${aws_api_gateway_method.post.http_method}"
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.region}:lambda:path/2015-03-31/functions/${aws_lambda_function.this.arn}/invocations"
}

resource "aws_api_gateway_deployment" "endpoint" {
  depends_on = ["aws_api_gateway_method.post",  "aws_api_gateway_integration.integration"]
  rest_api_id = "${aws_api_gateway_rest_api.this.id}"
  stage_name  = "default"
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
output "url" {
  value = "${aws_api_gateway_deployment.endpoint.invoke_url}/"
}
