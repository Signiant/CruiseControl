# AWS IP list service - CFN Deployment Sample

This is a sample of how to use CruiseControl.

The steps of a Jenkins build plan for this project would be as follows:

`git pull https://github.com/Signiant/aws-ip-list-service.git`

Use builders from another project -> `template_docker_image.sh`

Then, during the deployment phase, inject environment variables for the `cfn-promote.sh` script, and run the script with parameters for the environment and build path.

Pay extra attention to how environment variables for the container is passed and how they match between the `CFN/cfn-template.json` and the `deploy/useast1.cfn.yaml` files.
