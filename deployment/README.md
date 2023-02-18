# Deployment

## Dependencies

- [gcloud CLI](https://cloud.google.com/sdk/gcloud)
- [terraform](https://github.com/hashicorp/terraform)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [helmfile](https://github.com/helmfile/helmfile)

## 1. Create GCS Bucket and terraform variables file

```bash
PROJECT_ID=[GCP_PROJECT_ID]
REGION=[GCP_REGION] # e.g. asia-northeast1
ZONE=[GCP_ZONE]     # e.g. asia-northeast1-a
BUCKET_NAME=[GCS_BUCKET_NAME]
CLUSTER_NAME=meltria

gsutil mb -l ${REGION} gs://${BUCKET_NAME}

cat <<EOF > terraform/sockshop.tfvars
project_id   = "${PROJECT_ID}"
region       = "${REGION}"
bucket_name  = "${BUCKET_NAME}"
cluster_name = "${CLUSTER_NAME}"
cluster_zone = "${ZONE}"

cluster_workload_node_count = 7
cluster_workload_node_type = "e2-standard-2"
cluster_control_node_type = "e2-standard-2"
cluster_monitoring_node_type = "e2-highmem-2"
cluster_load_node_type = "e2-small"
EOF
```

## 2. Create GKE Cluster

```bash
gcloud auth application-default login

cd terraform
terraform init -backend-config="bucket=${BUCKET_NAME}" -backend-config="prefix=terraform/state"
terraform apply -var-file=sockshop.tfvars

# Get kubernetes cluster credentials
gcloud container clusters get-credentials --zone ${ZONE} ${CLUSTER_NAME}
gcloud projects add-iam-policy-binding ${PROJECT_ID} --member serviceAccount:${CLUSTER_NAME}@${PROJECT_ID}.iam.gserviceaccount.com --role roles/storage.objectAdmin
```

## 3. Apply manifests

```bash
kubectl apply -k ../manifests/train-ticket-base
kubectl annotate serviceaccount --namespace litmus argo-chaos iam.gke.io/gcp-service-account=${CLUSTER_NAME}@${PROJECT_ID}-sa.iam.gserviceaccount.com

(cd ../manifests/train-ticket-base && helmfile sync)
```

## 4. Setup alerts notification to slack with alertmanager

```bash
cat > /tmp/meltria_alerts_slack_webhook_url.env
slack-hook-url=XXXXXXXXX/YYYYYYYYYYY/ZZZZZZZZZZZZZZZZZZZZZZZZ

kubectl create secret generic -n monitoring --save-config slack-hook-url --from-env-file /tmp/meltria_alerts_slack_webhook_url.env
kubectl rollout restart deployment -n monitoring alertmanager
```
