FROM public.ecr.aws/lambda/python:3.12

WORKDIR ${LAMBDA_TASK_ROOT}

COPY jira_webhook/requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir

# Copy shared common utilities
COPY common/ common/

# Copy Lambda handler
COPY jira_webhook/ .

CMD ["main.handler"]
