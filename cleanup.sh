#!/usr/bin/env bash
# cleanup.sh — Tear down all AWS resources created by deploy.sh
# Usage: ./cleanup.sh

set -euo pipefail

AWS_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
CLUSTER="fsi-demo-cluster"
ECR_REPO="fsi-demo"
SG_NAME="fsi-demo-ecs-sg"
LOG_GROUP="/ecs/fsi-demo"
ECS_EXEC_ROLE="fsi-demo-ecs-execution-role"
APP_RUNNER_ROLE="AppRunnerECRAccessRole"

echo "==> Stopping all running tasks in cluster ${CLUSTER}..."
TASK_ARNS=$(aws ecs list-tasks \
  --cluster "${CLUSTER}" --region "${AWS_REGION}" \
  --query 'taskArns[]' --output text 2>/dev/null || true)
for ARN in $TASK_ARNS; do
  aws ecs stop-task --cluster "${CLUSTER}" --task "${ARN}" \
    --reason "cleanup.sh" --region "${AWS_REGION}" > /dev/null
  echo "    Stopped: ${ARN}"
done

echo "==> Deregistering task definitions..."
TD_ARNS=$(aws ecs list-task-definitions \
  --family-prefix "fsi-demo" --region "${AWS_REGION}" \
  --query 'taskDefinitionArns[]' --output text 2>/dev/null || true)
for ARN in $TD_ARNS; do
  aws ecs deregister-task-definition --task-definition "${ARN}" \
    --region "${AWS_REGION}" > /dev/null
  echo "    Deregistered: ${ARN}"
done

echo "==> Deleting ECS cluster..."
aws ecs delete-cluster --cluster "${CLUSTER}" --region "${AWS_REGION}" > /dev/null 2>&1 || echo "    (not found)"

echo "==> Deleting ECR repository..."
aws ecr delete-repository \
  --repository-name "${ECR_REPO}" --force \
  --region "${AWS_REGION}" > /dev/null 2>&1 || echo "    (not found)"

echo "==> Waiting for task ENIs to release, then deleting security group..."
SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=${SG_NAME}" \
  --region "${AWS_REGION}" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)

if [ -n "${SG_ID}" ] && [ "${SG_ID}" != "None" ]; then
  for i in $(seq 1 12); do
    ENI_COUNT=$(aws ec2 describe-network-interfaces \
      --filters "Name=group-id,Values=${SG_ID}" \
      --region "${AWS_REGION}" \
      --query 'length(NetworkInterfaces)' --output text)
    [ "${ENI_COUNT}" = "0" ] && break
    echo "    Waiting for ${ENI_COUNT} ENI(s) to release... (${i}/12)"
    sleep 5
  done
  aws ec2 delete-security-group \
    --group-id "${SG_ID}" --region "${AWS_REGION}" && echo "    Security group deleted"
else
  echo "    (not found)"
fi

echo "==> Deleting CloudWatch log group..."
aws logs delete-log-group \
  --log-group-name "${LOG_GROUP}" --region "${AWS_REGION}" 2>/dev/null || echo "    (not found)"

echo "==> Deleting IAM roles..."
for ROLE in "${ECS_EXEC_ROLE}" "${APP_RUNNER_ROLE}"; do
  POLICIES=$(aws iam list-attached-role-policies \
    --role-name "${ROLE}" \
    --query 'AttachedPolicies[*].PolicyArn' --output text 2>/dev/null || true)
  for POLICY_ARN in $POLICIES; do
    aws iam detach-role-policy --role-name "${ROLE}" --policy-arn "${POLICY_ARN}" 2>/dev/null || true
  done
  aws iam delete-role --role-name "${ROLE}" 2>/dev/null && \
    echo "    Deleted role: ${ROLE}" || echo "    (not found): ${ROLE}"
done

echo ""
echo "✓ Cleanup complete. No ongoing AWS charges."
