#!/bin/sh

if [ -d certs ]; then
  echo "Certs directory already exists, aborting"
  exit 1
fi

mkdir certs && cd certs

# CA
openssl genrsa -out ca.key 4096
openssl req -x509 -new -nodes -key ca.key -sha256 -days 3650 -out ca.crt -subj "/C=SE/ST=Stockholm/O=SUNET/CN=TranscriberWorkerCA"

# Server cert
openssl genrsa -out server.key 4096
openssl req -new -key server.key -out server.csr -subj "/C=SE/ST=Stockholm/O=SUNET/CN=TranscriberBackend"
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt -days 365 -sha256

# Worker cert
openssl genrsa -out worker.key 4096
openssl req -new -key worker.key -out worker.csr -subj "/C=SE/ST=Stockholm/O=SUNET/CN=TranscriberWorker"
openssl x509 -req -in worker.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out worker.crt -days 365 -sha256

