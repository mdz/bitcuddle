#!/usr/bin/env python3.6

import lnd.rpc_pb2 as ln
import lnd.rpc_pb2_grpc as lnrpc
import grpc
import os

class BitCuddle:
    def go(self):
        #pubkey = os.environ['LND_PEER_PUBKEY']
        #host = os.environ['LND_PEER_HOST']

        hub = LightningNode('lnd_hub')
        hub.connect()

        bob = LightningNode('lnd_bob')
        bob.connect()
        bob.peer(hub)
        bob.create_channel(hub)

        alice = LightningNode('lnd_alice')
        alice.connect()
        alice.peer(hub)
        alice.create_channel(hub)

        # XXX - alice and bob should be able to find each other through the hub...
        alice.peer(bob)
        alice.create_channel(bob)

        # wait for block

        while True:
            bob.send_payment(alice, value=1, memo="Test from bob to alice")
            alice.send_payment(bob, value=1, memo="Test from alice to bob")

class LightningNode:
    def __init__(self, host):
        self.host = host
        self.stub = None

    def connect(self):
        print(f"Connecting to {self.host}")

        cert = open(os.path.expanduser(f'/rpc/lnd-{self.host}.cert')).read()
        #print(cert)
        creds = grpc.ssl_channel_credentials(bytes(cert, 'ascii'))

        channel = grpc.secure_channel(f'{self.host}:10009', creds)
        self.stub = lnrpc.LightningStub(channel)

        response = self.stub.GetInfo(ln.GetInfoRequest())
        print(response)

        self.pubkey = response.identity_pubkey

    def peer(self, other):
        lnd_address = ln.LightningAddress(pubkey=other.pubkey, host=other.host)

        response = self.stub.ListPeers(ln.ListPeersRequest())
        print(repr(response))

        peered = False
        for peer in response.peers:
            if peer.pub_key == other.pubkey:
                peered = True
                break

        if peered:
            print(f"Already peered with {other.pubkey}")
        else:
            print(f"Peering with {lnd_address}")
            response = self.stub.ConnectPeer(ln.ConnectPeerRequest(addr=lnd_address, perm=True))
            print(response)

    def create_channel(self, other):
        response = self.stub.ListChannels(ln.ListChannelsRequest())
        print(repr(response))

        opened = False
        for channel in response.channels:
            if channel.remote_pubkey == other.pubkey:
                opened = True
                break

        if opened:
            print(f"Already have a channel to {other.pubkey}")
        else:
            print(f"Opening channel to {other.pubkey}")
            openChannelRequest = ln.OpenChannelRequest(node_pubkey_string=other.pubkey,
                    local_funding_amount=100000,
                    push_sat = 50000)
            response = self.stub.OpenChannelSync(openChannelRequest)
            print(response)

    def send_payment(self, dest, value, memo):
        invoice = ln.Invoice(value=value, memo=memo)
        print(invoice)

        response = dest.stub.AddInvoice(invoice)
        print(response)

        payment_request = response.payment_request

        payment = ln.SendRequest(dest_string=dest.pubkey,
                                 amt=invoice.value,
                                 payment_request=payment_request,
                                 payment_hash=response.r_hash)
        print(payment)

        response = self.stub.SendPaymentSync(payment)
        print(response)

bitcuddle = BitCuddle()
bitcuddle.go()
