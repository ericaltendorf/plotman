#!/bin/bash

DOCKER_REGISTRY="<docker-registry>"
PROJECT="chia-plotman"
TAG="plotter"
BASE_CONTAINER="ubuntu:20.04"
CHIA_GIT_REFERENCE="1.1.7"

# The UID/GID should match the 'chia' owner of the directories on the host system
UID=10001
GID=10001

docker rmi ${LOCAL_REGISTRY}/${PROJECT}:${TAG}

docker build . \
	--squash \
	--build-arg BASE_CONTAINER=${BASE_CONTAINER} \
	--build-arg CHIA_GIT_REFERENCE=${CHIA_GIT_REFERENCE} \
	--build-arg UID=${UID} \
	--build-arg GID=${GID} \
	-f docker/Dockerfile \
        -t ${DOCKER_REGISTRY}/${PROJECT}:${TAG}

docker push ${DOCKER_REGISTRY}/${PROJECT}:${TAG}
