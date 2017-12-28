#!/usr/bin/env python3.6

import lnd.rpc_pb2 as ln
import lnd.rpc_pb2_grpc as lnrpc
import grpc
import os

print("Hello, world!")

# Lnd cert is at ~/.lnd/tls.cert on Linux and
# ~/Library/Application Support/Lnd/tls.cert on Mac
cert = bytes(open(os.path.expanduser('/rpc/rpc.cert')).read(), 'ascii')
print(repr(cert))
creds = grpc.ssl_channel_credentials(cert)
print(repr(creds))
channel = grpc.secure_channel('localhost:10009', creds)
stub = lnrpc.LightningStub(channel)
