#!/usr/bin/env bash
# deploy.sh — Deploy fsi-demo to AWS ECS Fargate
# Prerequisites: Docker running, AWS credentials in environment variables
# Usage: ./deploy.sh

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
AWS_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="fsi-demo"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"
CLUSTER="fsi-demo-cluster"
TASK_FAMILY="fsi-demo"
ECS_EXEC_ROLE="fsi-demo-ecs-execution-role"
APP_RUNNER_ROLE="AppRunnerECRAccessRole"
SG_NAME="fsi-demo-ecs-sg"
LOG_GROUP="/ecs/fsi-demo"

echo "==> Account: ${ACCOUNT_ID}  Region: ${AWS_REGION}"

# ── 1. ECR repository ─────────────────────────────────────────────────────────
echo "==> Creating ECR repository..."
aws ecr create-repository \
  --repository-name "${ECR_REPO}" \
  --region "${AWS_REGION}" \
  --image-scanning-configuration scanOnPush=true 2>/dev/null || echo "    (already exists)"

# ── 2. Build & push image ─────────────────────────────────────────────────────
echo "==> Logging in to ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | \
  docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "==> Building Docker image..."
docker build -t "${ECR_REPO}" "$(dirname "$0")"

echo "==> Pushing to ECR..."
docker tag "${ECR_REPO}:latest" "${ECR_URI}:latest"
docker push "${ECR_URI}:latest"

# ── 3. IAM roles ──────────────────────────────────────────────────────────────
echo "==> Creating ECS task execution role..."
TRUST_ECS='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
aws iam create-role \
  --role-name "${ECS_EXEC_ROLE}" \
  --assume-role-policy-document "${TRUST_ECS}" \
  --description "ECS task execution role for fsi-demo" 2>/dev/null || echo "    (already exists)"
aws iam attach-role-policy \
  --role-name "${ECS_EXEC_ROLE}" \
  --policy-arn "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy" 2>/dev/null || true

# ── 4. CloudWatch log group ───────────────────────────────────────────────────
echo "==> Creating CloudWatch log group..."
aws logs create-log-group --log-group-name "${LOG_GROUP}" --region "${AWS_REGION}" 2>/dev/null || echo "    (already exists)"

# ── 5. ECS cluster ────────────────────────────────────────────────────────────
echo "==> Creating ECS cluster..."
aws ecs create-cluster --cluster-name "${CLUSTER}" --region "${AWS_REGION}" > /dev/null

# ── 6. Task definition (ARM64 for Apple Silicon images) ───────────────────────
echo "==> Registering task definition..."
TASK_DEF=$(cat <<JSON
{
  "family": "${TASK_FAMILY}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/${ECS_EXEC_ROLE}",
  "runtimePlatform": {"operatingSystemFamily": "LINUX", "cpuArchitecture": "ARM64"},
  "containerDefinitions": [{
    "name": "${TASK_FAMILY}",
    "image": "${ECR_URI}:latest",
    "portMappings": [{"containerPort": 8080, "protocol": "tcp"}],
    "essential": true,
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "${LOG_GROUP}",
        "awslogs-region": "${AWS_REGION}",
        "awslogs-stream-prefix": "ecs"
      }
    }
  }]
}
JSON
)
TASK_DEF_ARN=$(aws ecs register-task-definition \
  --region "${AWS_REGION}" \
  --cli-input-json "${TASK_DEF}" \
  --query 'taskDefinition.taskDefinitionArn' --output text)
echo "    Task definition: ${TASK_DEF_ARN}"

# ── 7. Security group ─────────────────────────────────────────────────────────
echo "==> Creating security group..."
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query "Vpcs[0].VpcId" --output text --region "${AWS_REGION}")

SG_ID=$(aws ec2 create-security-group \
  --group-name "${SG_NAME}" \
  --description "Allow port 8080 for fsi-demo ECS task" \
  --vpc-id "${VPC_ID}" \
  --region "${AWS_REGION}" \
  --query 'GroupId' --output text 2>/dev/null) || \
  SG_ID=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=${SG_NAME}" \
    --query 'SecurityGroups[0].GroupId' --output text --region "${AWS_REGION}")

aws ec2 authorize-security-group-ingress \
  --group-id "${SG_ID}" \
  --protocol tcp --port 8080 --cidr 0.0.0.0/0 \
  --region "${AWS_REGION}" 2>/dev/null || true
echo "    Security group: ${SG_ID}"

# ── 8. Run the Fargate task ───────────────────────────────────────────────────
echo "==> Launching Fargate task..."
SUBNETS=$(aws ec2 describe-subnets \
  --filters "Name=defaultForAz,Values=true" \
  --query 'Subnets[*].SubnetId' --output text --region "${AWS_REGION}")

# Try each subnet until one succeeds (capacity may vary by AZ)
TASK_ARN=""
for SUBNET in $SUBNETS; do
  RESULT=$(aws ecs run-task \
    --cluster "${CLUSTER}" \
    --task-definition "${TASK_DEF_ARN}" \
    --launch-type FARGATE \
    --region "${AWS_REGION}" \
    --network-configuration "awsvpcConfiguration={subnets=[${SUBNET}],securityGroups=[${SG_ID}],assignPublicIp=ENABLED}" \
    --output json 2>/dev/null)
  TASK_ARN=$(echo "${RESULT}" | python3 -c "import sys,json; t=json.load(sys.stdin)['tasks']; print(t[0]['taskArn'] if t else '')" 2>/dev/null || true)
  if [ -n "${TASK_ARN}" ]; then
    echo "    Launched in subnet ${SUBNET}"
    break
  fi
done

if [ -z "${TASK_ARN}" ]; then
  echo "ERROR: Could not launch task in any subnet. Check capacity in ${AWS_REGION}."
  exit 1
fi

# ── 9. Wait for RUNNING and print the URL ─────────────────────────────────────
echo "==> Waiting for task to reach RUNNING state..."
for i in $(seq 1 20); do
  STATUS=$(aws ecs describe-tasks \
    --cluster "${CLUSTER}" --tasks "${TASK_ARN}" \
    --region "${AWS_REGION}" \
    --query 'tasks[0].lastStatus' --output text)
  echo "    ${i}/20: ${STATUS}"
  [ "${STATUS}" = "RUNNING" ] && break
  if [ "${STATUS}" = "STOPPED" ] || [ "${STATUS}" = "DEPROVISIONING" ]; then
    REASON=$(aws ecs describe-tasks --cluster "${CLUSTER}" --tasks "${TASK_ARN}" \
      --region "${AWS_REGION}" --query 'tasks[0].stoppedReason' --output text)
    echo "ERROR: Task stopped: ${REASON}"
    exit 1
  fi
  sleep 5
done

ENI_ID=$(aws ecs describe-tasks \
  --cluster "${CLUSTER}" --tasks "${TASK_ARN}" --region "${AWS_REGION}" \
  --query 'tasks[0].attachments[?type==`ElasticNetworkInterface`].details[?name==`networkInterfaceId`].value' \
  --output text)

PUBLIC_IP=$(aws ec2 describe-network-interfaces \
  --network-interface-ids "${ENI_ID}" --region "${AWS_REGION}" \
  --query 'NetworkInterfaces[0].Association.PublicIp' --output text)

echo ""
echo "✓ Deployed! Open in your browser:"
echo "  http://${PUBLIC_IP}:8080"
echo ""
echo "  Task ARN : ${TASK_ARN}"
echo "  Cluster  : ${CLUSTER}"
echo "  Region   : ${AWS_REGION}"
echo ""
echo "Run ./cleanup.sh when done."
