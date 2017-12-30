#!/usr/bin/env python3.6

import lnd.rpc_pb2 as ln
import lnd.rpc_pb2_grpc as lnrpc
import grpc
import os

class BitCuddle:
    def __init__(self):
        self.lnds = dict()
        self.pubkeys = dict()

    def go(self):
        #pubkey = os.environ['LND_PEER_PUBKEY']
        #host = os.environ['LND_PEER_HOST']

        hub = self.connect_rpc('lnd_hub')
        hub_pubkey = self.pubkeys[hub]
        hub_host = 'lnd_hub'

        bob = self.connect_rpc('lnd_bob')
        self.connect_peer(bob, pubkey=hub_pubkey, host=hub_host)
        self.create_channel(bob, pubkey=hub_pubkey)

        alice = self.connect_rpc('lnd_alice')
        self.connect_peer(alice, pubkey=hub_pubkey, host=hub_host)
        self.create_channel(alice, pubkey=hub_pubkey)

        self.connect_peer(bob, pubkey=self.pubkeys[alice], host='lnd_alice')
        self.create_channel(bob, pubkey=self.pubkeys[alice])

        # wait for block

        self.send_payment(bob, alice, value=1, memo="Test")

    def connect_rpc(self, name):
        print(f"Hello, bitcuddles {name}!")

        cert = open(os.path.expanduser(f'/rpc/lnd-{name}.cert')).read()
        #print(cert)
        creds = grpc.ssl_channel_credentials(bytes(cert, 'ascii'))

        channel = grpc.secure_channel(f'{name}:10009', creds)
        lnd = lnrpc.LightningStub(channel)

        response = lnd.GetInfo(ln.GetInfoRequest())
        print(response)

        self.pubkeys[lnd] = response.identity_pubkey

        return self.lnds.setdefault(name, lnd)

    def connect_peer(self, stub, pubkey, host):
        lnd_address = ln.LightningAddress(pubkey=pubkey, host=host)

        response = stub.ListPeers(ln.ListPeersRequest())
        print(repr(response))

        peered = False
        for peer in response.peers:
            if peer.pub_key == pubkey:
                peered = True
                break

        if peered:
            print("Already peered with {}".format(pubkey))
        else:
            print("Peering with {}@{}".format(pubkey,host))
            response = stub.ConnectPeer(ln.ConnectPeerRequest(addr=lnd_address, perm=True))
            print(response)

    def create_channel(self, stub, pubkey):
        response = stub.ListChannels(ln.ListChannelsRequest())
        print(repr(response))

        opened = False
        for channel in response.channels:
            if channel.remote_pubkey == pubkey:
                opened = True
                break

        if opened:
            print("Already have a channel to {}".format(pubkey))
        else:
            print("Opening channel to {}".format(pubkey))
            openChannelRequest = ln.OpenChannelRequest(node_pubkey_string=pubkey,
                    local_funding_amount=100000,
                    push_sat = 50000)
            response = stub.OpenChannelSync(openChannelRequest)
            print(response)

    def send_payment(self, src, dest, value, memo):
        invoice = ln.Invoice(value=value, memo=memo)
        print(invoice)

        response = dest.AddInvoice(invoice)
        print(response)

        payment_request = response.payment_request

        payment = ln.SendRequest(dest_string=self.pubkeys[dest],
                                 amt=invoice.value,
                                 payment_request=payment_request,
                                 payment_hash=response.r_hash)
        print(payment)

        response = src.SendPaymentSync(payment)
        print(response)

bitcuddle = BitCuddle()
bitcuddle.go()
