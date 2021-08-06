# Kubernetes manifests

## How to Setup

### Setup GKE Cluster

1. Create GKE cluster.

```shell-session
$ export PROJECT_ID=$(gcloud config list --format 'value(core.project)') 
$ gcloud container clusters create sock-shop-01 \
	--region asia-northeast1-a \
	--release-channel regular \
	--cluster-version 1.19.10-gke.1700 \
	--image-type=cos \
	--machine-type e2-medium \
	--num-nodes 4 \
	--workload-pool="${PROJECT_ID}.svc.id.goog" \
	--workload-metadata=GKE_METADATA \
	--no-enable-stackdriver-kubernetes
```

2. Create additional GKE node-pools.

```shell-session
$ gcloud container node-pools create control-pool \
	--cluster sock-shop-01 \
	--machine-type e2-medium \
	--image-type=cos \
	--num-nodes=1 \
	--workload-metadata=GKE_METADATA

$ gcloud container node-pools create analytics-pool \
	--cluster sock-shop-01 \
	--machine-type n2-highcpu-2 \
	--image-type=cos \
	--num-nodes=1 \
	--workload-metadata=GKE_METADATA
```

3. Setup for Workload Identity.

```shell-session
$ export CLUSTER_NAME='sock-shop-01'
$ gcloud iam service-accounts create $CLUSTER_NAME
```

```shell-session
$ gcloud projects add-iam-policy-binding $PROJECT_ID --member serviceAccount:$CLUSTER_NAME@$PROJECT_ID.iam.gserviceaccount.com --role roles/storage.objectAdmin
```

```shell-session
$ gcloud iam service-accounts add-iam-policy-binding --role roles/iam.workloadIdentityUser --member "serviceAccount:$PROJECT_ID.svc.id.goog[litmus/argo-chaos]" $CLUSTER_NAME@$PROJECT_ID.iam.gserviceaccount.com
```

```shell-session
$ kubectl annotate serviceaccount --namespace litmus argo-chaos iam.gke.io/gcp-service-account=$CLUSTER_NAME@$PROJECT_ID.iam.gserviceaccount.com
```

4. Create GCS buckets (TBD)

### Deploy Sock Shop Application and Monitoring Stacks

```shell-session
$ helm plugin install https://github.com/databus23/helm-diff          
$ helmfile apply
$ kubectl apply -k .
```

## Browse Grafana Dashboards

1. Forward local port to grafana service port.

```shell-session
$ kubectl port-forward svc/grafana -n monitoring --address 0.0.0.0 3000:80
```

2. Add the following entry to `/etc/hosts` file.

```
127.0.0.1 grafana.monitoring.svc.cluster.local
```

3. Open <http://grafana.monitoring.svc.cluster.local:3000>.
