#!/usr/bin/env python3.6

import lnd.rpc_pb2 as ln
import lnd.rpc_pb2_grpc as lnrpc
import grpc
import os
import codecs

class BitCuddle:
    def go(self):
        print("Hello, bitcuddles!")

        cert = open(os.path.expanduser('/rpc/lnd.cert')).read()
        #print(cert)
        creds = grpc.ssl_channel_credentials(bytes(cert, 'ascii'))

        channel = grpc.secure_channel('lndrpc:10009', creds)
        self.stub = lnrpc.LightningStub(channel)

        response = self.stub.GetInfo(ln.GetInfoRequest())
        print(response)

        pubkey = os.environ['LND_PEER_PUBKEY']
        host = os.environ['LND_PEER_HOST']
        self.peer_with(pubkey=pubkey, host=host)

        self.create_channel(pubkey)

        self.send_payment(pubkey, 1, "Test")

    def peer_with(self, pubkey, host):
        lnd_address = ln.LightningAddress(pubkey=pubkey, host=host)

        response = self.stub.ListPeers(ln.ListPeersRequest())
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
            response = self.stub.ConnectPeer(ln.ConnectPeerRequest(addr=lnd_address, perm=True))
            print(response)

    def create_channel(self, pubkey):
        response = self.stub.ListChannels(ln.ListChannelsRequest())
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
            response = self.stub.OpenChannelSync(openChannelRequest)
            print(response)

    def send_payment(self, dest, value, memo):
        invoice = ln.Invoice(value=value, memo=memo)

        response = self.stub.AddInvoice(invoice)
        print(response)

        payment_request = response.payment_request

        payment = ln.SendRequest(dest_string=dest,
                                 amt=invoice.value,
                                 payment_request=payment_request,
                                 payment_hash=response.r_hash)
        response = self.stub.SendPaymentSync(payment)
        print(repr(response))

bitcuddle = BitCuddle()
bitcuddle.go()
