#!/usr/bin/env python3

import argparse
import json

from google.cloud import storage


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gcs-bucket-name",
                        help="", required=True)
    parser.add_argument("--gcs-blob-prefix",
                        help="", required=True)
    args = parser.parse_args()

    sc = storage.Client()
    blobs = sc.list_blobs(args.gcs_bucket_name,
                          prefix=args.gcs_blob_prefix)

    print(json.dumps([blob.name for blob in blobs]))


if __name__ == '__main__':
    main()
