#!/bin/bash

# rather than change every echo statement...
# alias stdout
exec 3>&1
# option to output everything to stderr
# except things explicitly redirected to 3
if [ -n "$REDIRECT_MESSAGES" ]; then
    exec 1>&2
fi

echo "***********************************************************************"
echo "****************** Configuring and Error Checking *********************"
echo "***********************************************************************"

BASENAME="Library"
echo "Image base name set to $BASENAME"

if [ ! -z "$IMAGE_BASE_NAME" ]; then
	BASENAME="$IMAGE_BASE_NAME"
	echo "Image base name changed to $IMAGE_BASE_NAME"
fi

PROJECTTITLE=${PROJECT_TITLE}
echo "Project title set to $PROJECTTITLE"

if [ ! -z "$DOCKER_PROJECT_TITLE" ]; then
    PROJECTTITLE="$DOCKER_PROJECT_TITLE"
    echo "Project title changed to $PROJECTTITLE"
fi

BUILD_DIR="./$PROJECTTITLE/app"
echo "Docker build directory set to $BUILD_DIR"

if [ ! -z "$DOCKER_BUILD_DIR" ]; then
    BUILD_DIR="./$DOCKER_BUILD_DIR"
    echo "Docker build directory changed to $BUILD_DIR"
fi


DOCKER_REPO_SECURITY="private"

if [ "$DOCKER_REPO_TYPE" == "public" ]; then
	DOCKER_REPO_SECURITY="public"
fi

echo "Checking for /var/run/docker.sock..."

if [ ! -e /var/run/docker.sock ]; then
	echo "*** ERROR! Could not find /var/run/docker.sock"
	exit -1
fi

echo "Found."

echo "Checking for /bin/docker..."

if [ ! -e /bin/docker ]; then
        echo "*** ERROR! Could not find /bin/docker"
        exit -1
fi

echo "Found."

echo "Checking for /home/user/.dockercfg..."

if [ ! -e /home/user/.dockercfg ]; then
        echo "*** ERROR! Could not find /home/user/.dockercfg"
        exit -1
fi

echo "Found."

echo "Building image..."
echo "Moving into app folder.."
cd "$BUILD_DIR"

DOCKER_FULL_NAME="$BASENAME/$PROJECTTITLE:${PROJECT_BRANCH}-${BUILD_NUMBER}"
echo "Starting docker build at $(date +%H:%M:%S)"
docker build -t "$DOCKER_FULL_NAME" .
CMDRET=$?

echo "Docker build complete at $(date +%H:%M:%S)"

if [ $CMDRET -ne 0 ]; then
	echo "*** ERROR! Image build failed with error code $CMDRET"
	exit -1
fi

echo "Checking if repo exists..."
CMDRET=`curl -s -o /dev/null -w "%{http_code}" https://registry.hub.docker.com/v1/repositories/${BASENAME}/${PROJECTTITLE}/tags`

if [ $DOCKER_REPO_SECURITY == "public" ]; then
	if [ $CMDRET -ne 200 ]; then
		echo "*** ERROR! $BASENAME/$PROJECTTITLE does not exist."
		echo "A public repo must be manually created in order to push"
		exit -1
	fi
else
	if [ $CMDRET -eq 200 ]; then
    	echo "*** ERROR! $BASENAME/$PROJECTTITLE exists as a public repo"
        echo "*** Cannot push a private build to a public repo, aborting"
        exit -1
    fi
fi

TRY=0
MAXTRIES=3
DELAY=10
CMDRET=1

while [ $MAXTRIES -ne $TRY ] && [ $CMDRET -ne 0 ]; do

  if [ $TRY -gt 0 ]; then
    echo "Push failed. Sleeping $DELAY seconds before trying again."
    sleep $DELAY
  fi

  echo "Starting docker push attempt number ${TRY} at $(date +%H:%M:%S)"
  docker push -f "$DOCKER_FULL_NAME"
  CMDRET=$?
  : $(( TRY++ ))
done

if [ $CMDRET -eq 0 ]; then
	echo "Docker push complete at $(date +%H:%M:%S)"
    echo "Removing local copy of image: $DOCKER_FULL_NAME"
    docker rmi "$DOCKER_FULL_NAME"
else
	echo "*** ERROR! Docker push failed"
    exit 1
fi

# finally, output the full name of container
echo "$DOCKER_FULL_NAME" 1>&3
