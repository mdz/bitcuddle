#!/usr/bin/env python3.6

import lnd.rpc_pb2 as ln
import lnd.rpc_pb2_grpc as lnrpc
import grpc
import os

print("Hello, world!")

cert = open(os.path.expanduser('/rpc/rpc.cert')).read()
print(cert)
creds = grpc.ssl_channel_credentials(bytes(cert, 'ascii'))

channel = grpc.secure_channel('lndrpc:10009', creds)
stub = lnrpc.LightningStub(channel)

response = stub.GetInfo(ln.GetInfoRequest())
print(response)
