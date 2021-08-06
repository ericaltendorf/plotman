#!/bin/bash

DOCKER_REGISTRY="<docker-registry>"
PROJECT="chia-plotman"
TAG="latest"
BASE_CONTAINER="ubuntu:20.04"
CHIA_GIT_REFERENCE="1.2.3"

# The UID/GID should match the 'chia' owner of the directories on the host system
bUID=10001
bGID=10001

docker build . \
	--squash \
	--build-arg BASE_CONTAINER=${BASE_CONTAINER} \
	--build-arg CHIA_GIT_REFERENCE=${CHIA_GIT_REFERENCE} \
	--build-arg UID=${bUID} \
	--build-arg GID=${bGID} \
	-f docker/Dockerfile \
        -t ${DOCKER_REGISTRY}/${PROJECT}:${TAG}

docker push ${DOCKER_REGISTRY}/${PROJECT}:${TAG}
