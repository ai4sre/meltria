variable "project_id" {
  type        = string
  description = "The project id under which the Meltria resource will be created."
}

variable "region" {
  type        = string
  description = "The region where the Meltria resource will be created. (e.g. asia-northeast1)"
}

variable "cluster_name" {
  type        = string
  description = "The prefix of the resource name to be created."
}

variable "cluster_zone" {
  type        = string
  description = "The zone where the GKE cluster will be created."
}

variable "cluster_workload_node_count" {
  type        = number
  description = "The number of nodes in the workload pool of the GKE cluster."
  default     = 7
}

variable "bucket_name" {
  type        = string
  description = "Specify the name of the pre-created bucket. This bucket will be used to store Terraform state and generated datasets."
}

