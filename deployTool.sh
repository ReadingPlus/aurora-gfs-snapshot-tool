#!/usr/bin/env bash

#Get Bucket name from parameter
bucket=$1

if [[ -z "${bucket}" ]]; then
    echo "You need to specify a bucket to use."
    exit 1
fi

#get region name from parameter. Default is us-east-1
if [[ -z "${2}" ]]; then
    echo "No region specified. Defaulting to us-east-1"
    region="us-east-1"
else
    region=$2
fi

echo "Packaging code...."
aws cloudformation package --template cloudformation/template.json --s3-bucket ${bucket} --use-json --output-template-file cloudformation/packaged-template.json &> /dev/null

if [[ $? -eq 0 ]]; then
    #package uploaded correctly.
    echo "Uploading generated template to S3..."
    aws s3 cp cloudformation/packaged-template.json s3://${bucket}

    url="https://console.aws.amazon.com/cloudformation/home?region=${region}#/stacks/new?stackName=GFS-Snapshot-Tool&templateURL=https://s3.amazonaws.com/${bucket}/packaged-template.json"
    echo "Navigate to this url in your browser to complete installation:"
    echo ${url}
else
    echo "Packaging failed"
    exit 1
fi