FROM golang:1.14.1-alpine3.11 as builder

RUN apk add --update git build-base libmnl-dev iptables

RUN git clone https://git.zx2c4.com/wireguard-go && \
    cd wireguard-go && \
    make && \
    make install

ENV WITH_WGQUICK=yes
RUN git clone https://git.zx2c4.com/wireguard-tools && \
    cd wireguard-tools && \
    cd src && \
    make && \
    make install

FROM python:alpine3.10
COPY --from=builder /usr/bin/wireguard-go /usr/bin/wg* /usr/bin/
COPY . /agent
WORKDIR ./agent
RUN apk add wireguard-tools iproute2 \
  && apk --update add python py-pip openssl ca-certificates py-openssl wget \
  && apk --update add --virtual build-dependencies libffi-dev openssl-dev python-dev py-pip build-base \
  && pip install --upgrade pip \
  && python setup.py install \
  && rm -rf /agent \
  && apk del build-dependencies

ENTRYPOINT ["/usr/local/bin/syntropy_agent", "run"]