apiVersion: "argoproj.io/v1alpha1"
kind:       "Workflow"
metadata: generateName: "argowf-analytics-"
spec: {
	entrypoint:         "argowf-analytics"
	serviceAccountName: "argo-chaos"
	nodeSelector: "cloud.google.com/gke-nodepool": "analytics-pool"
	arguments: parameters: [{
		name: "gcsBucket"
		value: "microservices-demo-artifacts"
	}, {
		name: "gcsBlobPrefix"
		value: "metrics/" // eg. metrics/2021/6/23/argowf-chaos-4bj5c/
	}, {
		name: "repeatNum"
		value: 1
	}, {
		name: "tsdrMethod"
		value: "tsifter"
	}]
	parallelism: 1
	templates: [{
		name: "argowf-analytics"
		steps: [ [ {
			name: "list-files"
			template: "list-metrics-files"
			arguments: parameters: [{
				name: "bucketName"
				value: "{{workflow.parameters.gcsBucket}}"
			}, {
				name: "blobPrefix"
				value: "{{workflow.parameters.gcsBlobPrefix}}"
			}]
		} ], [ {
			name: "repeat-tsdr"
			template: "repeat-tsdr"
			arguments: parameters: [{
				name: "tsdrMethod"
				value: "{{workflow.parameters.tsdrMethod}}"
			}, {
				name: "filePath"
				value: "{{item}}"
			}, {
				name: "repeatNum"
				value: "{{workflow.parameters.repeatNum}}"
			}]
			withParam: "{{steps.list-files.outputs.result}}"
		}] ]
	}, {
		name: "list-metrics-files"
		inputs: parameters: [{
			name: "bucketName"
		}, {
			name: "blobPrefix"
		}]
		container: {
			image: "ghcr.io/ai4sre/artifacts-tools:latest"
			imagePullPolicy: "Always"
			command: ["/usr/src/app/list_metrics_files.py"]
			args: [
				"--gcs-bucket-name", "{{inputs.parameters.bucketName}}",
				"--gcs-blob-prefix", "{{inputs.parameters.blobPrefix}}",
			]
		}
	}, {
		name: "repeat-tsdr"
		inputs: {
			parameters: [{
				name: "tsdrMethod"
			}, {
				name: "filePath"
			}, {
				name: "repeatNum"
			}]
		}
		steps: [ [ {
			name: "repeat-tsdr-step"
			template: "run-tsdr"
			arguments: parameters: [{
				name: "tsdrMethod"
				value: "{{inputs.parameters.tsdrMethod}}"
			}, {
				name: "filePath"
				value: "{{inputs.parameters.filePath}}"
			}, {
				name: "jobN"
				value: "{{item}}"
			}]
			withSequence: count: "{{inputs.parameters.repeatNum}}"
		}] ]
	}, {
		// Note the following duplicate code in argowf.cue. 
		name: "run-tsdr"
		inputs: {
			parameters: [{
				name: "tsdrMethod"
			}, {
				name: "filePath"
			}, {
				name: "jobN"
			}]
			artifacts: [ {
				name: "download-metrics-file"
				path: "/tmp/metrics.json"
				gcs: {
					bucket: "{{ workflow.parameters.gcsBucket }}"
					key: "{{inputs.parameters.filePath}}"
				}
			} ]
		}
		#result_file_name: """
		{{inputs.parameters.tsdrMethod}}-{{workflow.creationTimestamp.Y}}-{{workflow.creationTimestamp.m}}-{{workflow.creationTimestamp.d}}-{{workflow.name}}.json
		"""
		container: {
			image: "ghcr.io/ai4sre/tsdr-tools:latest"
			imagePullPolicy: "Always"
			command: ["/usr/src/app/tsdr.py"]
			args: [ "--method", "{{inputs.parameters.tsdrMethod}}",
					"--max-workers", "2",
					"--include-raw-data",
					"--out", "/tmp/\(#result_file_name)", 
					"/tmp/metrics.json"]
		}
		outputs: artifacts: [{
			name: "tsdr-outputs"
			path: "/tmp/\(#result_file_name)"
			gcs: {
				bucket: "{{workflow.parameters.gcsBucket}}"
				// see https://github.com/argoproj/argo-workflows/blob/510b4a816dbb2d33f37510db1fd92b841c4d14d3/docs/workflow-controller-configmap.yaml#L93-L106
				key: """
				results/{{=sprig.trimSuffix('.tgz', inputs.parameters.filePath)}}/\( #result_file_name + ".tgz" )
				"""
			}
		}]
	}]
}
