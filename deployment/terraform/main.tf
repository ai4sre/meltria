terraform {
  backend "gcs" {
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
}

# ----------------------------------------
# Network
# ----------------------------------------

resource "google_compute_network" "meltria" {
  name                    = var.cluster_name
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "meltria" {
  name          = "${var.cluster_name}-cluster-network"
  ip_cidr_range = "10.146.0.0/20"
  region        = var.region
  network       = google_compute_network.meltria.id

  private_ip_google_access = true

  secondary_ip_range = [
    {
      range_name    = "pods-range"
      ip_cidr_range = "10.20.0.0/14"
    },
    {
      range_name    = "services-range"
      ip_cidr_range = "10.24.0.0/20"
    },
  ]
}

# ----------------------------------------
# Service Account for GKE Cluster
# ----------------------------------------

resource "google_service_account" "cluster_sa" {
  account_id   = "${var.cluster_name}-sa"
  display_name = "Service Account for Meltria Cluster"
}

resource "google_service_account_iam_binding" "cluster_identity" {
  service_account_id = google_service_account.cluster_sa.name

  role = "roles/iam.workloadIdentityUser"
  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[litmus/argo-chaos]"
  ]
}

# Attach role for storage object admin to given bucket.
# This role is used to store the datasets generated by the Meltria workflow.
resource "google_storage_bucket_iam_binding" "binding" {
  bucket = var.bucket_name
  role   = "roles/storage.objectAdmin"
  members = [
    "serviceAccount:${google_service_account.cluster_sa.email}",
  ]
}

# ----------------------------------------
# GKE Cluster
# ----------------------------------------

data "google_container_engine_versions" "cluter_version" {
  provider       = google-beta
  project        = var.project_id
  location       = var.cluster_zone
  version_prefix = "1.23."
}


# GKE Cluster
resource "google_container_cluster" "cluster" {
  name     = var.cluster_name
  location = var.cluster_zone

  networking_mode = "VPC_NATIVE"
  network         = google_compute_network.meltria.id
  subnetwork      = google_compute_subnetwork.meltria.id
  ip_allocation_policy {
    cluster_secondary_range_name  = "pods-range"
    services_secondary_range_name = "services-range"
  }

  logging_service    = "none"
  monitoring_service = "none"

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  min_master_version       = data.google_container_engine_versions.cluter_version.latest_master_version
  remove_default_node_pool = true
  initial_node_count       = 1
}

locals {
  oauth_scopes = [
    "https://www.googleapis.com/auth/compute",
    "https://www.googleapis.com/auth/devstorage.read_only",
    "https://www.googleapis.com/auth/logging.write",
    "https://www.googleapis.com/auth/monitoring",
  ]
}

resource "google_container_node_pool" "default_pool" {
  name       = "default-pool"
  location   = var.cluster_zone
  cluster    = google_container_cluster.cluster.name
  node_count = var.cluster_workload_node_count

  node_config {
    machine_type = "e2-standard-2"
    image_type   = "COS_CONTAINERD"

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    oauth_scopes = local.oauth_scopes
  }
}


resource "google_container_node_pool" "control_pool" {
  name       = "control-pool"
  location   = var.cluster_zone
  cluster    = google_container_cluster.cluster.name
  node_count = 1

  node_config {
    machine_type = "e2-medium"
    image_type   = "COS_CONTAINERD"

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    oauth_scopes = local.oauth_scopes
  }
}


resource "google_container_node_pool" "load_pool" {
  name       = "load-pool"
  location   = var.cluster_zone
  cluster    = google_container_cluster.cluster.name
  node_count = 1

  node_config {
    machine_type = "e2-small"
    image_type   = "COS_CONTAINERD"

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    oauth_scopes = local.oauth_scopes
  }
}

resource "google_container_node_pool" "monitoring_pool" {
  name       = "monitoring-pool"
  location   = var.cluster_zone
  cluster    = google_container_cluster.cluster.name
  node_count = 1

  node_config {
    machine_type = "e2-highmem-2"
    image_type   = "COS_CONTAINERD"

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    oauth_scopes = local.oauth_scopes
  }
}