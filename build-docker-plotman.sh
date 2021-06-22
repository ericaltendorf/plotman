#!/bin/bash

LOCAL_REGISTRY="<local-registry>"
#DOCKER_REGISTRY="<docker-registry>"
PROJECT="chia-plotman"
TAG="plotter"
BASE_CONTAINER="ubuntu:20.04"
CHIA_GIT_REFERENCE="1.1.7"

docker rmi ${LOCAL_REGISTRY}/${PROJECT}:${TAG}

docker build . \
	--squash \
	--build-arg BASE_CONTAINER=${BASE_CONTAINER} \
	--build-arg CHIA_GIT_REFERENCE=${CHIA_GIT_REFERENCE} \
	-f Dockerfile \
	-t ${LOCAL_REGISTRY}/${PROJECT}:${TAG}
#     -t ${DOCKER_REGISTRY}/${PROJECT}:${TAG}

docker push ${LOCAL_REGISTRY}/${PROJECT}:${TAG}
#docker push ${DOCKER_REGISTRY}/${PROJECT}:${TAG}
