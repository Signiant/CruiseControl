# Micro-service deployment process using Jenkins, CloudFormation, and Docker

### Overview

This repository contains the files needed to deploy a micro-service to ECS using CloudFormation

The following diagram shows the major components of this process.

![ECS Deployment Diagram](/images/deploymentdiagram.png?raw=true)

The steps are as follows

1. In the project's Jenkins build plan, after the project has been built, a build-step is added to call the template `template_docker_image.sh`. This script gathers information about the image using environment variables, checks security variables to ensure that an image that should be private does not push to a private repository, builds the image, pushes the image to docker hub, and deletes the image locally.

Note: The template is called as follows:

![Calling template_docker_image.sh](/images/usebuilders.png?raw=true)

2. During the promotion process, the `cfn-promote.sh` script is called. This script leverages the AWS CLI to create a CloudFormation stack. The script also decides whether to update or create a stack, by checking if the stack exists and is in an updatable state, performs the creation/update, and waits for the creation to either complete successfully, ensure the stack rolls back if it does not, and if the stack was created, deletes the stack if it rolls back. (This is because the stack would not have anything to roll back to, therefore, would result in an unupdatable stack)

### File specifics

### `template_docker_image.sh`

This script contains multiple phases in order to build and push an image to dockerhub.com

The first step is gathering environment variables for the push. These values have defaults set in the script itself, but can be overridden by injecting the following environment variables.

| Environment Variable | Required | Default                                                     | Usage                                                                                                         |
|----------------------|----------|-------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| `IMAGE_BASE_NAME`      | No       | Uses the `BASENAME` variable's  value in the script           | Sets BASENAME in the script which is used for the library name on dockerhub. e.g. `signiant/PROJECT_TITLE`    |
| `DOCKER_PROJECT_TITLE` | No       | Uses `PROJECT_TITLE` environment variable from Jenkins        | Sets `PROJECT_TITLE` in the script which is used in the repository name on dockerhub. e.g. `BASENAME/someProject` |
| `DOCKER_REPO_TYPE`     | No       | Uses `DOCKER_REPO_SECURITY` environment variable from Jenkins |                                                                                                               |

The next step ensures docker files exists to successfully use the docker commands including the docker credentials to push an image to a private repository

The first step is to ensure that docker.sock was mounted. Since these docker commands run on docker containers, we mount the `docker.sock` file to be able to execute docker commands within the containers.
Next is to ensure that `/bin/docker` exists so we are able to issue those commands through docker.sock. Also, to be able to push images to private repositories, we make sure that the `dockercfg` file exists, which contains credentials needed to do just that.
For more information on dockercfg: https://coreos.com/os/docs/latest/registry-authentication.html

Now we are ready to build the docker image. First step is to move into the project directory, and into the app folder. This is where we keep our Dockerfile for the services.

The build is started by the command `docker build -t $BASENAME/$PROJECTTITLE:${PROJECT_BRANCH}-${BUILD_NUMBER} .`

As you can see, the image repo is set to the basename, and the image name as the project's title we retrieve from Jenkins. We use the project's branch and build number as the tag to be able to differentiate images.

At this point, if something goes wrong with building the image, the script will exit with an error code.

Assuming there was no error, we are ready to push the image to dockerhub.

The way our dockerhub repo is configured, when a new repo is created, it is set to `private`. This is for security reasons. Therefore, we need to make sure that we are pushing proprietary code to private repos only. This is done by first curling docker hub, and storing the return code.

If the variable `DOCKER_REPO_SECURITY` is set to `public`, we expect the repo to exist first before being able to push to it. If set to private and the curl returns with a code of `200`, we stop the push to protect against sending images with proprietary code to a public repo.

Once in a blue moon, the push may fail. In order to avoid building the entire project again, we try to push for a maximum of 3 tries with a delay of 10 seconds in between pushes.

### `cfn-template.json`

This template creates a task definition, a service, a load balancer and an optional Route53 entry.

It's important to note that the template outputs the service name which we will need to create the alarm for the service after this template's stack will be created.

| Environment Variable | Required | Default                                                     | Usage                                                                                                         |
|----------------------|----------|-------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| `TASK_ONLY`      | No       | false           | Set to True or False before calling.  If set, will assume only an ECS taskdef is being created, not a service    |
| `SERVICE_ALARM_ENDPOINT` | No       | None        | Value must map to a valid value in the `SNSMap` in `alarm-template.json`.  If not set, no alarm stack will be created  |

### `alarm-template.json`

This template creates 3 alarms for a service, and contains SNS Subscription endpoints for those alarms. (We use VictorOps endpoints to send to different endpoints depending on the SNS Subscription ie. dev or prod).

We use 2 CPU alarms to monitor 2 different characteristics of CPU usage. The first is when the CPU usage is higher than 200%. This alarm points out that the service CPU reservation is probably too low for it to operate correctly. The second alarm checks when the usage is higher than 80%, this is a normal CPU usage alarm which indicates that there might be a need to scale up the desired number of tasks.

### `*.cfn.yaml`

This file contains all the information we need to deploy a service on CloudFormation. Essentially, this is what contains all the parameters that get passed into the CloudFormation template. Ex. Image name, SSL cert, etc.

We read this file using shyaml. An open source project on github.

An alternative to this is to use a json file that contains all the parameters for the cloudformation template. Using this method, you could eliminate the need of using shyaml, and instead, directly pass in the json file.

For more information on passing parameters into CloudFormation, use the following link:
https://blogs.aws.amazon.com/application-management/post/Tx1A23GYVMVFKFD/Passing-Parameters-to-CloudFormation-Stacks-with-the-AWS-CLI-and-Powershell

### `cfn-promote.sh` - This is where all the magic happens.

This script needs 2 parameters passed into it. Those parameters are:
1. `ENVIRONMENT`: The name or alias of the region to promote to. We use this name to decide which configuration file to use in order to promote a service to ECS
2. `BUILD_PATH`: The path in which the created artifacts and deployment rules are stored. Since we build and promote on docker containers, this path is mounted on to both build and deployment containers.

This script makes calls to the AWS CLI. Therefore, it assumes that the environment variables required are already set. (`AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`)

Depending on the way you prefer things, you may opt to use a different method of configuring your aws cli. For more information on this, use the following link:
http://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-started.html

The first steps are self explanatory. We check if our deployment rules file exists, then start extracting the values that are needed first from them.

Since we create our cluster using a CloudFormation stack as well, that stack contains values that might change. (Such as the LoadBalancer security group, which gets created with the cluster). To reduce deployment errors due to modified parameters, we opted to retrieve the LoadBalancer security group and subnets from the cluster directly to use when promoting the service. We do that by describing the stack and saving the values of our filtered result.

After some error checking, we proceed to check the status of the service stack (if it exists). If the stack doesn't exist, we create it directly. If the stack exists, an update is performed instead. Before we can update though, we check the status of the stack since if a stack is in the process of updating or rolling back, we cannot issue an update.

If the stack is in an updatable state, we then perform an `update-stack` operation. If the stack does not exist, the operating is create-stack instead. All the parameters are passed in at this point.

In case the same build plan was promoted again (for example, to rerun automation tests), we also check if the operation returns a "No updates are to be performed" message, which should not fail a build. Otherwise, we enter a while loop that checks the status of the newly created/updated stack to ensure that the deployment will be completed without errors.

In case of an error, we wait for 5 minutes before checking to see if the stack rolled back successfully. Also, if the operation we used was `create-stack`, we output the stack events before we delete the stack since this stack will never be in an updatable state. (Only from failing to create-stack)

The next steps create the alarms for the service only if an environment variable labeled `SERVICE_ALARM_ENDPOINT` exists, which contains the value of the SNS Subscription used in the template. The process is very similar to the previous steps.
