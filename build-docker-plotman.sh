#!/bin/sh

DOCKER_REGISTRY="graemes"
LOCAL_REGISTRY="registry.graemes.com/graemes"
PROJECT="chia-plotman"
TAG="plotter"
CHIA_BRANCH="1.1.7"

docker rmi ${LOCAL_REGISTRY}/${PROJECT}:${TAG}

docker build . \
	--squash \
	--build-arg CHIA_BRANCH=${CHIA_BRANCH} \
	-f Dockerfile \
	-t ${LOCAL_REGISTRY}/${PROJECT}:${TAG}

#     -t ${DOCKER_REGISTRY}/${PROJECT}:${TAG} \

docker push ${LOCAL_REGISTRY}/${PROJECT}:${TAG}
#docker push ${DOCKER_REGISTRY}/${PROJECT}:${TAG}
