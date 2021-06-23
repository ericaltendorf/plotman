# Build deployable artifacts
ARG BASE_CONTAINER=ubuntu:20.04
FROM ${BASE_CONTAINER} as plotman-builder

ARG CHIA_GIT_REFERENCE

RUN DEBIAN_FRONTEND=noninteractive apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y curl jq python3 ansible tar bash ca-certificates git openssl unzip wget python3-pip sudo acl build-essential python3-dev python3.8-venv python3.8-distutils apt nfs-common python-is-python3

RUN echo "cloning ${CHIA_GIT_REFERENCE}"
RUN git clone --branch "${CHIA_GIT_REFERENCE}" https://github.com/Chia-Network/chia-blockchain.git \
&& cd chia-blockchain \
&& git submodule update --init mozilla-ca

WORKDIR /chia-blockchain
# Placeholder for patches
RUN /bin/bash ./install.sh

COPY . /plotman

RUN ["/bin/bash", "-c", "source ./activate && pip install /plotman && deactivate"] 

# Build deployment container
FROM ${BASE_CONTAINER} as plotman

ARG UID=10001
ARG GID=10001

RUN DEBIAN_FRONTEND=noninteractive apt-get update \
&& DEBIAN_FRONTEND=noninteractive apt-get install -y curl jq python3 python3.8-venv ca-certificates tzdata ssh rsync \
&& apt-get clean all \
&& rm -rf /var/lib/apt/lists

COPY --from=plotman-builder /chia-blockchain /chia-blockchain

RUN groupadd -g ${GID} chia
RUN useradd -m -u ${UID} -g ${GID} chia

RUN mkdir -p /data/chia/tmp \
&& mkdir -p /data/chia/plots \
&& mkdir -p /data/chia/logs

VOLUME ["/data/chia/tmp","/data/chia/plots","/data/chia/logs"]

RUN chown -R chia:chia /chia-blockchain \
&& chown -R chia:chia /data/chia

WORKDIR /chia-blockchain
USER chia

ENV VIRTUAL_ENV="/chia-blockchain/venv"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Kick off plots (assumes the environemnt is good to go)
CMD ["/bin/bash", "-c", "plotman plot" ]
# Alternative command to simply provide shell environment
# CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait" ]
