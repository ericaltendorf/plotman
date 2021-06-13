# Build deployable artifacts
FROM ubuntu:latest as plotman-builder

ARG CHIA_BRANCH

RUN DEBIAN_FRONTEND=noninteractive apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y curl jq python3 ansible tar bash ca-certificates git openssl unzip wget python3-pip sudo acl build-essential python3-dev python3.8-venv python3.8-distutils apt nfs-common python-is-python3 cmake libsodium-dev g++

RUN echo "cloning ${CHIA_BRANCH}"
RUN git clone --branch ${CHIA_BRANCH} https://github.com/Chia-Network/chia-blockchain.git \
&& cd chia-blockchain \
&& git submodule update --init mozilla-ca \
&& chmod +x install.sh 

WORKDIR /chia-blockchain
# Placeholder for patches
RUN /usr/bin/sh ./install.sh

COPY . /plotman

RUN . ./activate \
&& pip install -e /plotman \
&& deactivate 

# Build deployment container
FROM ubuntu:latest as plotman

ARG UID=10001
ARG GID=10001

RUN DEBIAN_FRONTEND=noninteractive apt-get update \
&& DEBIAN_FRONTEND=noninteractive apt-get install -y curl jq python3 python3.8-venv python3.8-distutils ca-certificates tzdata vim ssh less rsync git tmux libsodium23 \
&& apt-get clean all \
&& rm -rf /var/lib/apt/lists

COPY --from=plotman-builder /chia-blockchain /chia-blockchain
COPY --from=plotman-builder /plotman /plotman

RUN groupadd -g ${GID} chia
RUN useradd -m -u ${UID} -g ${GID} chia

RUN mkdir -p /data/chia/tmp \
&& mkdir -p /data/chia/plots \
&& mkdir -p /data/chia/logs

VOLUME ["/data/chia/tmp","/data/chia/plots","/data/chia/logs"]

RUN chown -R chia:chia /chia-blockchain \
&& chown -R chia:chia /plotman \
&& chown -R chia:chia /data/chia

WORKDIR /chia-blockchain
USER chia

ENV VIRTUAL_ENV="/chia-blockchain/venv"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Kick off plots (assumes the environemnt is good to go)
CMD ["/bin/bash", "-c", "plotman plot" ]
# Alternative command to simply provide shell environment
#CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait" ]
