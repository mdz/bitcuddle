#!/usr/bin/env python3.6

import lnd.rpc_pb2 as ln
import lnd.rpc_pb2_grpc as lnrpc
import grpc
import os

print("Hello, world!")

cert = open(os.path.expanduser('/rpc/lnd.cert')).read()
#print(cert)
creds = grpc.ssl_channel_credentials(bytes(cert, 'ascii'))

channel = grpc.secure_channel('lndrpc:10009', creds)
stub = lnrpc.LightningStub(channel)

response = stub.GetInfo(ln.GetInfoRequest())
print(response)

lnd_key = os.environ['LND_PEER_PUBKEY']
lnd_host = os.environ['LND_PEER_HOST']
lnd_address = ln.LightningAddress(pubkey=lnd_key, host=lnd_host)

response = stub.ListPeers(ln.ListPeersRequest())
print(repr(response))

peered = False
for peer in response.peers:
    if peer.pub_key == lnd_key:
        peered = True
        break

if peered:
    print("Already peered with {}".format(lnd_key))
else:
    print("Peering with {}@{}".format(lnd_key,lnd_host))
    response = stub.ConnectPeer(ln.ConnectPeerRequest(addr=lnd_address, perm=True))
    print(response)

response = stub.ListChannels(ln.ListChannelsRequest())
print(repr(response))

opened = False
for channel in response.channels:
    if channel.remote_pubkey == lnd_key:
        opened = True
        break

if opened:
    print("Already have a channel to {}".format(lnd_key))
else:
    print("Opening channel to {}".format(lnd_key))
    openChannelRequest = ln.OpenChannelRequest(node_pubkey_string=lnd_key,
            local_funding_amount=100000,
            push_sat = 50000)
    response = stub.OpenChannelSync(openChannelRequest)
    print(response)
