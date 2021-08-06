import "encoding/yaml"
import "encoding/json"
import "strings"

#appLabels: ["user","user-db","shipping","carts","carts-db","orders","orders-db","catalogue","catalogue-db","payment","front-end"]

#promProbeInputs: {
	endpoint: "http://prometheus.monitoring.svc.cluster.local:9090"
	query: """
	sum(rate(request_duration_seconds_count{name='front-end',status_code=~'2..',route!='metrics'}[1m])) * 100
	"""
	comparator: {
		criteria: ">="
		value: "4000" // 4k qps
	}
}

#probe: [{
	name: "check-front-end-qps"
	type: "promProbe"
	"promProbe/inputs": #promProbeInputs
	mode: "SOT"
	runProperties: {
		probeTimeout: 5
		interval: 15 // prometheus scraping interval
		retry: 3
		stopOnFailure: true
	}
}]

#chaosTypeToExps: {
	"pod-cpu-hog": [{
		name: "pod-cpu-hog"
		spec: {
			components: env: [{
				name:  "TARGET_CONTAINER"
				value: "{{inputs.parameters.appLabel}}"
			}, {
				name:  "CPU_CORES"
				value: "2"
			}, {
				name:  "TOTAL_CHAOS_DURATION"
				value: "{{workflow.parameters.chaosDurationSec}}"
			}]
			probe: #probe
		}
	}]
	"pod-memory-hog": [{
		name: "pod-memory-hog"
		spec: {
			components: env: [{
				name:  "TARGET_CONTAINER"
				value: "{{inputs.parameters.appLabel}}"
			}, {
				name:  "MEMORY_CONSUMPTION"
				value: "500" // 500MB
			}, {
				name:  "TOTAL_CHAOS_DURATION"
				value: "{{workflow.parameters.chaosDurationSec}}"
			}]
			probe: #probe
		}
	}]
	"pod-network-loss": [{
		name: "pod-network-loss"
		spec: { 
			components: env: [{
				name:  "TARGET_CONTAINER"
				value: "{{inputs.parameters.appLabel}}"
			}, {
				name:  "NETWORK_INTERFACE"
				value: "eth0"
			}, {
				name: "NETWORK_PACKET_LOSS_PERCENTAGE"
				value: "5"
			}, {
				name:  "TOTAL_CHAOS_DURATION"
				value: "{{workflow.parameters.chaosDurationSec}}"
			}]
			probe: #probe
		}
	}]
	"pod-network-latency": [{
		name: "pod-network-latency"
		spec: {
			components: env: [{
				name:  "TARGET_CONTAINER"
				value: "{{inputs.parameters.appLabel}}"
			}, {
				name:  "NETWORK_INTERFACE"
				value: "eth0"
			}, {
				name: "NETWORK_LATENCY"
				value: "50" // ms
			}, {
				name:  "TOTAL_CHAOS_DURATION"
				value: "{{workflow.parameters.chaosDurationSec}}"
			}]
			probe: #probe
		}
	}]
}

apiVersion: "argoproj.io/v1alpha1"
kind:       "Workflow"
metadata: generateName: "argowf-chaos-"
spec: {
	entrypoint:         "argowf-chaos"
	serviceAccountName: "argo-chaos"
	nodeSelector: {
		"cloud.google.com/gke-nodepool": "control-pool"
	}
	arguments: parameters: [{
		name:  "appNamespace"
		value: "sock-shop"
	}, {
		name:  "adminModeNamespace"
		value: "litmus"
	}, {
		name:  "chaosServiceAccount"
		value: "litmus-admin"
	}, {
		name: "appLabels"
		value: json.Marshal(_cue_app_labels)
		_cue_app_labels: #appLabels
	}, {
		name:  "repeatNum"
		value: 1
	}, {
		name:  "chaosDurationSec"
		value: 300
	}, {
		name:  "chaosIntervalSec"
		value: 1800 // 30min
	}, {
		name: "chaosTypes"
		value: strings.Join([for type, _ in #chaosTypeToExps { "'" + type + "'" }], ",")
	}, {
		name: "gcsBucket"
		value: "microservices-demo-artifacts"
	}, {
		name: "litmusJobCleanupPolicy"
		value: "delete" // defaut value in litmus
	}]
	templates: [{
		name: "argowf-chaos"
		parallelism: 1
		steps: [ [ for type, _ in #chaosTypeToExps {
			name:     "run-chaos-\( type )"
			template: "repeat-chaos-\( type )"
			arguments: parameters: [{
				name:  "repeatNum"
				value: "{{workflow.parameters.repeatNum}}"
			}, {
				name:  "appLabel"
				value: "{{item}}"
			}]
			withParam: "{{workflow.parameters.appLabels}}"
			// append 'dummy' because of list in argo should be >=2
			// see https://github.com/argoproj/argo-workflows/issues/1633#issuecomment-645433742
			when: "'\( type )' in ({{workflow.parameters.chaosTypes}},'dummy')"
		},] ]
	}, for type, v in #chaosTypeToExps {
		name: "repeat-chaos-\( type )"
		inputs: parameters: [{
			name: "repeatNum"
		}, {
			name: "appLabel"
		}]
		parallelism: 1
		steps: [ [{
			name:     "inject-chaos-\( type )-and-get-metrics"
			template: "inject-chaos-\( type )-and-get-metrics"
			arguments: parameters: [{
				name:  "jobN"
				value: "{{item}}"
			}, {
				name:  "appLabel"
				value: "{{inputs.parameters.appLabel}}"
			}]
			withSequence: count: "{{inputs.parameters.repeatNum}}"
		}] ]
	}, for type, _ in #chaosTypeToExps {
		#chaosEngineName: "{{inputs.parameters.appLabel}}-\( type )-{{inputs.parameters.jobN}}"
		#chaosResultName: "\( #chaosEngineName )-\( type )"
		name: "inject-chaos-\( type )-and-get-metrics"
		inputs: parameters: [{
			name: "jobN"
		}, {
			name: "appLabel"
		}]
		steps: [ [{
			name: "reset-chaosengine"
			template: "revert-chaosengine"
			arguments: parameters: [{
				name: "chaosEngineName"
				value: #chaosEngineName
			}, {
				name:  "chaosResultName"
				value: #chaosResultName
			}]
		}], [{
			name:     "inject-chaos-\( type )"
			template: "inject-chaos-\( type )"
			arguments: parameters: [{
				name:  "chaosEngineName"
				value: #chaosEngineName
			}, {
				name:  "appLabel"
				value: "{{inputs.parameters.appLabel}}"
			}]
		}], [{
			name: "get-injection-finished-time"
			template: "get-injection-finished-time"
			arguments: parameters: [{
				name:  "chaosEngineName"
				value: #chaosEngineName
			}]
		}], [{
			name:     "get-metrics"
			template: "get-metrics-from-prometheus"
			arguments: parameters: [{
				name:  "jobN"
				value: "{{inputs.parameters.jobN}}"
			}, {
				name: "appLabel"
				value: "{{inputs.parameters.appLabel}}"
			}, {
				name: "chaosType"
				value: "\( type )"
			}, {
				name: "endTimestamp"
				value: "{{steps.get-injection-finished-time.outputs.result}}"
			}]
		}], [{
			name: "revert-chaosengine"
			template: "revert-chaosengine"
			arguments: parameters: [{
				name:  "chaosEngineName"
				value: #chaosEngineName
			}, {
				name:  "chaosResultName"
				value: #chaosResultName
			}]
		}], [{
			name: "run-tsdr-and-then-sleep"
			template: "run-tsdr-and-then-sleep"
			arguments: {
				parameters: [{
					name: "gcsMetricsFilePath"
					value: "{{steps.get-metrics.outputs.parameters.metrics-file-path}}"
				}]
				artifacts: [{
					name: "metricsFile"
					from: "{{steps.get-metrics.outputs.artifacts.metrics-artifacts-gcs}}"
				}]
			}
		}] ]
	}, {
		name: "run-tsdr-and-then-sleep"
		inputs: {
			parameters: [{
				name: "gcsMetricsFilePath"
			}]
			artifacts: [{
				name: "metricsFile"
			}]
		}
		steps: [ [{
			name: "run-tsdr"
			template: "run-tsdr-by-all-methods"
			arguments: {
				parameters: [{
					name: "gcsMetricsFilePath"
					value: "{{inputs.parameters.gcsMetricsFilePath}}"
				}]
				artifacts: [{
					name: "metricsFile"
					from: "{{inputs.artifacts.metricsFile}}"
				}]
			}
		}, {
			name:     "sleep"
			template: "sleep-n-sec"
			arguments: parameters: [{
				name:  "seconds"
				value: "{{workflow.parameters.chaosIntervalSec}}"
			}]
		} ] ]
	}, {
		name: "run-tsdr-by-all-methods"
		parallelism: 1
		inputs: {
			parameters: [{
				name: "gcsMetricsFilePath"
			}]
			artifacts: [{
				name: "metricsFile"
			}]
		}
		steps: [ [{
			name: "run-tsdr"
			template: "run-tsdr-by-method"
			arguments: {
				parameters: [{
					name: "tsdrMethod"
					value: "{{item}}"
				}, {
					name: "gcsMetricsFilePath"
					value: "{{inputs.parameters.gcsMetricsFilePath}}"
				}]
				artifacts: [{
					name: "metricsFile"
					from: "{{inputs.artifacts.metricsFile}}"
				}]
			}
			withItems: ["tsifter", "sieve"]
		}] ]
	}, {
		// return <injection started time> + <chaos duration>
		name: "get-injection-finished-time"
		inputs: parameters: [{
			name: "chaosEngineName"
		}]
		script: {
			image: "bitnami/kubectl"
			command: ["sh"]
			source: """
			ts=$(kubectl get chaosengine {{inputs.parameters.chaosEngineName}} -n litmus -o=jsonpath='{.metadata.creationTimestamp}')
			expr $(date -d $ts +'%s') + {{workflow.parameters.chaosDurationSec}}
			"""
		}
	}, {
		name: "get-metrics-from-prometheus"
		inputs: parameters: [{
			name: "jobN"
		}, {
			name: "appLabel"
		}, {
			name: "chaosType"
		}, {
			name: "endTimestamp"
		}]
		#metricsPath: "/tmp/{{workflow.creationTimestamp.Y}}-{{workflow.creationTimestamp.m}}-{{workflow.creationTimestamp.d}}-{{workflow.name}}-{{inputs.parameters.appLabel}}_{{inputs.parameters.chaosType}}_{{inputs.parameters.jobN}}.json",
		container: {
			image: "ghcr.io/ai4sre/metrics-tools:latest"
			imagePullPolicy: "Always"
			args: [
				"--prometheus-url",
				"http://prometheus.monitoring.svc.cluster.local:9090",
				"--grafana-url",
				"http://grafana.monitoring.svc.cluster.local:3000",
				"--end", "{{inputs.parameters.endTimestamp}}",
				"--chaos-injected-component", "{{inputs.parameters.appLabel}}",
				"--injected-chaos-type", "{{inputs.parameters.chaosType}}",
				"--out", #metricsPath,
			]
		}
		outputs: {
			#gcsMetricsFilePath: """
			metrics/{{workflow.creationTimestamp.Y}}/{{workflow.creationTimestamp.m}}/{{workflow.creationTimestamp.d}}/{{workflow.name}}/{{inputs.parameters.appLabel}}_{{inputs.parameters.chaosType}}_{{inputs.parameters.jobN}}.json.tgz
			"""
			artifacts: [{
				name: "metrics-artifacts-gcs"
				path: #metricsPath
				gcs: {
					bucket: "{{ workflow.parameters.gcsBucket }}"
					key: #gcsMetricsFilePath
				}
			}]
			parameters: [{
				name: "metrics-file-path"
				value: #gcsMetricsFilePath
			}]
		}
	}, {
		name: "revert-chaosengine"
		inputs: parameters: [{
			name: "chaosEngineName"
		}, {
			name: "chaosResultName"
		}]
		container: {
			image: "bitnami/kubectl"
        	command: ["sh", "-c"]
        	args: ["""
			kubectl delete --wait chaosengine {{inputs.parameters.chaosEngineName}} -n {{workflow.parameters.adminModeNamespace}};
			kubectl delete --wait chaosresult {{inputs.parameters.chaosResultName}} -n {{workflow.parameters.adminModeNamespace}};
			true
			"""]
		}
	}, {
		// Note the following duplicate code in argowf-analytics.cue. 
		name: "run-tsdr-by-method"
		nodeSelector: {
			"cloud.google.com/gke-nodepool": "analytics-pool"
		}
		inputs: {
			parameters: [{
				name: "tsdrMethod"
			}, {
				name: "gcsMetricsFilePath"
			}]
			artifacts: [ {
				name: "metricsFile"
				path: "/tmp/metrics.json"
				gcs: {
					bucket: "{{ workflow.parameters.gcsBucket }}"
					key: "{{inputs.parameters.gcsMetricsFilePath}}"
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
				key: """
				results/{{=sprig.trimSuffix('.tgz', inputs.parameters.gcsMetricsFilePath)}}/\( #result_file_name + ".tgz" )
				"""
			}
		}]
	}, {
		name: "sleep-n-sec"
		inputs: parameters: [{
			name: "seconds"
		}]
		container: {
			image: "alpine:latest"
			command: ["sh", "-c"]
			args: ["echo sleeping for {{inputs.parameters.seconds}} seconds; sleep {{inputs.parameters.seconds}}; echo done"]
		}
	}, for type, exps in #chaosTypeToExps {
		name: "inject-chaos-\( type )"
		inputs: {
			parameters: [{
				name: "chaosEngineName"
			}, {
				name: "appLabel"
			}]
			artifacts: [{
				name: "manifest-for-injecting-\(type)"
				path: "/tmp/chaosengine.yaml"
				raw: data: yaml.Marshal(_cue_chaos_engine)
				_cue_chaos_engine: {
					apiVersion: "litmuschaos.io/v1alpha1"
					kind: "ChaosEngine"
					metadata: {
						name: "{{inputs.parameters.chaosEngineName}}"
						namespace: "{{workflow.parameters.adminModeNamespace}}"
					}
					spec: {
						annotationCheck: "false"
						engineState:     "active"
						monitoring:      true
						appinfo: {
							appns: "{{workflow.parameters.appNamespace}}"
							applabel: "name={{inputs.parameters.appLabel}}"
							appkind:  "deployment"
						}
						chaosServiceAccount: "{{workflow.parameters.chaosServiceAccount}}"
						jobCleanUpPolicy:    "{{workflow.parameters.litmusJobCleanupPolicy}}"
						components: runner: nodeSelector: {
							"cloud.google.com/gke-nodepool": "control-pool"
						}
						experiments: exps
					}
				}
			}]
		}
		script: {
			image: "bitnami/kubectl"
			command: ["sh"]
			// Wait until chaosresult resource is found
			source: """
			kubectl apply -f /tmp/chaosengine.yaml -n {{workflow.parameters.adminModeNamespace}}
			while true; do
				status=$(kubectl get -n {{workflow.parameters.adminModeNamespace}} chaosengines/{{inputs.parameters.chaosEngineName}} -o jsonpath='{.status.engineStatus}')
				if [ $? -eq 0 ]; then
					if [ $status = 'completed' ]; then
						exit 0
					fi
				fi
				sleep 3
			done
			"""
		}
		// timeout
		timeout: "{{=asInt(workflow.parameters.chaosDurationSec) * 2}}s"
	}]
}
