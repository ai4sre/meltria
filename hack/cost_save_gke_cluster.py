#!/usr/bin/env python3

import argparse
import json
import logging
import os.path
import subprocess

GKE_CMD = 'gcloud -q container'
SCRIPT_NAME = os.path.basename(__file__)
RECOVER_FILE_PATH_PREFIX = '/tmp/meltria_gke_cluster'


def get_node_pools(cluster_name: str, zone: str) -> list:
    cmd = f'{GKE_CMD} node-pools list --cluster {cluster_name} -z {zone} --format "json"'
    logging.info(f"Running {cmd} ...")
    node_pools = json.loads(subprocess.check_output(cmd, shell=True).decode('utf-8').strip())
    return node_pools


def resize_node_pool(cluster_name: str, zone: str, pool_name: str, size: int):
    cmd = f'{GKE_CMD} clusters resize {cluster_name} -z {zone} --node-pool={pool_name} --num-nodes={size}'
    logging.info(f"Running {cmd} ...")
    subprocess.check_call(cmd, shell=True)


def recover_node_pool(cluster_name: str, zone: str, recover_file: str):
    pool_to_node_count: dict[str, int] = {}
    logging.info(f'Loading {recover_file} ...')
    with open(recover_file, mode='r') as f:
        saved_pools = json.load(f)
        for pool in saved_pools:
            pool_to_node_count[pool['name']] = pool['initialNodeCount']
    for pool in get_node_pools(cluster_name, zone):
        name = pool["name"]
        logging.info(f'Recovering node pool {name} in {cluster_name}')
        resize_node_pool(cluster_name, zone, name, pool_to_node_count[name])


def degrade_node_pool(cluster_name: str, zone: str, recover_file: str):
    pools = get_node_pools(cluster_name, zone)
    logging.info(f'Saving pool information into {recover_file} for recovering ...')
    with open(recover_file, mode='w') as f:
        json.dump(pools, f, indent=2)
    for pool in pools:
        logging.info(f'Degrading node pool {pool["name"]} in {cluster_name}')
        resize_node_pool(cluster_name, zone, pool['name'], 0)


def main():
    logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s', level=logging.INFO)

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="A tool to degrading and recovering GKE cluster's node pools for cost saving.",
        epilog=f"""An example of usage:
        $ {SCRIPT_NAME} --down --cluster-name train-ticket-01
        $ {SCRIPT_NAME} --up --cluster-name train-ticket-01
"""
    )
    parser.add_argument('--up', action='store_true', help='Recover the cluster')
    parser.add_argument('--down', action='store_true', help='Degrade the cluster')
    parser.add_argument('--cluster-name', required=True, help='GKE cluster name')
    parser.add_argument('--zone', help='gcp zone')
    parser.add_argument('--recover-file', help='File to store the recovery cluster')
    args = parser.parse_args()

    if args.up and args.down:
        logging.error('Please specify either --up or --down')
        exit(1)

    recover_file = args.recover_file
    if recover_file is None:
        recover_file = f'{RECOVER_FILE_PATH_PREFIX}.{args.cluster_name}.recover.json'

    if args.up:
        recover_node_pool(args.cluster_name, args.zone, recover_file)
    elif args.down:
        degrade_node_pool(args.cluster_name, args.zone, recover_file)
    else:
        logging.error('Please specify either --up or --down')
        exit(1)


if __name__ == '__main__':
    main()
