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

cat <<EOF > terraform/terraform.tfvars
project_id   = "${PROJECT_ID}"
region       = "${REGION}"
bucket_name  = "${BUCKET_NAME}"
cluster_name = "${CLUSTER_NAME}"
cluster_zone = "${ZONE}"

cluster_workload_node_count = 7
EOF
```

## 2. Create GKE Cluster

```bash
gcloud auth application-default login

cd terraform
terraform init -backend-config="bucket=${BUCKET_NAME}" -backend-config="prefix=terraform/state"
terraform apply

# Get kubernetes cluster credentials
gcloud container clusters get-credentials --zone ${ZONE} ${CLUSTER_NAME}
```
