#!/usr/bin/env python3.6

import lnd.rpc_pb2 as ln
import lnd.rpc_pb2_grpc as lnrpc

#import btcwallet.api_pb2 as btcw
#import btcwallet.api_pb2_grpc as btcwrpc
#import requests
import jsonrpc_requests

import grpc
import os
import time

class BitCuddle:
    def go(self):
        # Initialize the mining wallet
        mining_wallet = BTCWalletRPC('btcwallet')
        mining_wallet.connect()

        mining_address_file = '/rpc/mining_address'
        if os.path.exists(mining_address_file):
            with open(mining_address_file) as f:
                mining_address = f.read()
        else:
            mining_address = wallet.getnewaddress()
            with open(mining_address_file, 'w') as f:
                f.write(mining_address)
            print(f"Created address {mining_address} for mining")
            
        print(f"Mining address: {mining_address}")

        # Connect to btcd
        btcd = BTCDRPC('btcd')
        btcd.connect()

        # Bring up the lightning network
        hub = LightningRPC('lnd_hub')
        hub.connect()

        bob = LightningRPC('lnd_bob')
        bob.connect()
        bob.peer(hub)

        alice = LightningRPC('lnd_alice')
        alice.connect()
        alice.peer(hub)

        # XXX - alice and bob should be able to find each other through the
        # hub, but this doesn't seem to work, so create a direct peering
        # between them
        alice.peer(bob)

        mining_wallet_balance = mining_wallet.getbalance()
        mining_wallet_balance_unconfirmed = mining_wallet.getunconfirmedbalance()
        print(f'Mining wallet balance: {mining_wallet_balance}')
        if mining_wallet_balance_unconfirmed > 0:
            print(f'Mining wallet unconfirmed balance: {mining_wallet.getunconfirmedbalance()} (generating)')
            btcd.generate_and_wait(100)

        need_blocks = False
        for node in [bob, alice]:
            balance = node.wallet_balance()
            print(f"Wallet balance in {node.host} is {balance}")
            if balance["total_balance"] == 0:
                print(f"Funding {node.host} from the mining wallet")
                node_address = node.new_address()
                mining_wallet.walletpassphrase('password', 5)
                mining_wallet.sendtoaddress(node_address, 1)
                need_blocks = True

        # wait for block
        if need_blocks:
            btcd.generate_and_wait(400)

        bob.create_channel(alice)

        bob.send_payment(alice, value=1, memo="Test from bob to alice")
        alice.send_payment(bob, value=1, memo="Test from alice to bob")

class LightningRPC:
    def __init__(self, host):
        self.host = host
        self.stub = None

    def connect(self):
        print(f"Connecting to lnd on {self.host}")

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

    def new_address(self, address_type='np2wkh'):
        type_map = {
            "p2wkh": ln.NewAddressRequest.WITNESS_PUBKEY_HASH,
            "np2wkh": ln.NewAddressRequest.NESTED_PUBKEY_HASH,
            "p2pkh": ln.NewAddressRequest.PUBKEY_HASH
        }

        request = ln.NewAddressRequest(type=type_map[address_type])

        response = self.stub.NewAddress(request)

        print(f"new address: '{str(response.address)}'")

        return response.address
        
    def wallet_balance(self):
        response = self.stub.WalletBalance(ln.WalletBalanceRequest())
        print(response)

        return {
            "total_balance": response.total_balance,
            "confirmed_balance": response.confirmed_balance,
            "unconfirmed_balance": response.unconfirmed_balance
        }

class JSONRPCWrapper:
    def __init__(self, name, host, port):
        self.name = name
        self.host = host
        self.port = port
        self.rpc = None

    def connect(self):
        url = f'https://devuser:devpass@{self.host}:{self.port}/'
        print(f"Connecting to {self.name} on {url}")

        self.rpc = jsonrpc_requests.Server(url, verify='/rpc/rpc.cert')

        print(f"Connected to {self.name}:",self.rpc.getinfo())

    def __getattr__(self, name):
        # If an attribute is not recognized, assume that it is an RPC method
        return getattr(self.rpc, name)

class BTCWalletRPC(JSONRPCWrapper):
    def __init__(self, host, port=18554):
        super().__init__('btcwallet', host, port)

class BTCDRPC(JSONRPCWrapper):
    def __init__(self, host, port=18556):
        super().__init__('btcd', host, port)

    def generate_and_wait(self, blocks):
        assert blocks > 0

        current = self.getinfo()['blocks']
        new = current + blocks
        self.generate(blocks)

        while current < new:
            print(f"Waiting for block {new}, currently at {current}")
            time.sleep(1)
            current = self.getinfo()['blocks']
        print(f"Reached {new}")

bitcuddle = BitCuddle()
bitcuddle.go()
