#!/bin/sh

if [ -d certs ]; then
  echo "Certs directory already exists, aborting"
  exit 1
fi

mkdir certs && cd certs

# CA
openssl genrsa -out transcriber_ca_key.pem 4096
openssl req -x509 -new -nodes -key transcriber_ca_key.pem -sha256 -days 3650 -out transcriber_ca.pem -subj "/C=SE/ST=Stockholm/O=SUNET/CN=TranscriberWorkerCA"

# Server cert
openssl genrsa -out transcriber_server_key.pem 4096
openssl req -new -key transcriber_server_key.pem -out transcriber_server_csr.pem -subj "/C=SE/ST=Stockholm/O=SUNET/CN=TranscriberBackend"
openssl x509 -req -in transcriber_server_csr.pem -CA transcriber_ca.pem -CAkey transcriber_ca_key.pem -CAcreateserial -out transcriber_server.pem -days 365 -sha256

# Worker cert
openssl genrsa -out transcriber_worker_key.pem 4096
openssl req -new -key transcriber_worker_key.pem -out transcriber_worker_csr.pem -subj "/C=SE/ST=Stockholm/O=SUNET/CN=TranscriberWorker"
openssl x509 -req -in transcriber_worker_csr.pem -CA transcriber_ca.pem -CAkey transcriber_ca_key.pem -CAcreateserial -out transcriber_worker_crt.pem -days 365 -sha256

