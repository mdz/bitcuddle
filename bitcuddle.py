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
        print("Hello, bitcuddlers!")

        # Initialize the mining wallet
        mining_wallet = BTCWalletRPC('btcwallet')
        mining_wallet.connect()

        # This might be better done in the btcwallet container, but it lacks btcctl
        mining_key = os.environ['MINING_PRIVATE_KEY']
        print("Importing mining key into wallet")
        mining_wallet.walletpassphrase('password', 5)
        print(mining_wallet.importprivkey(mining_key))

        mining_wallet_balance = mining_wallet.getbalance()
        mining_wallet_balance_unconfirmed = mining_wallet.getunconfirmedbalance()
        print(f'Mining wallet balance: {mining_wallet_balance} confirmed, {mining_wallet_balance_unconfirmed} unconfirmed')

        # Connect to btcd
        btcd = BTCDRPC('btcd')
        btcd.connect()

        # Ensure that the mining wallet has confirmed funds
        if not mining_wallet_balance > 0:
            if not mining_wallet_balance_unconfirmed > 0:
                print('Generating some blocks to mine')
                btcd.generate_and_wait(10)

            print(f'Generating some blocks to confirm mining funds')
            # segwit enabled at 400?
            btcd.generate_and_wait(400)

            mining_wallet.wait_for_block_height(btcd.getinfo()['blocks'])

        mining_wallet_balance = mining_wallet.getbalance()
        mining_wallet_balance_unconfirmed = mining_wallet.getunconfirmedbalance()
        print(f'Mining wallet balance: {mining_wallet_balance} confirmed, {mining_wallet_balance_unconfirmed} unconfirmed')

        # Bring up the lightning network
        hub = LightningRPC('lnd_hub')
        hub.connect()

        bob = LightningRPC('lnd_bob')
        bob.connect()
        alice = LightningRPC('lnd_alice')
        alice.connect()

        hub.peer(bob)
        hub.peer(alice)

        # XXX - shouldn't alice and bob find each other through the hub?
        alice.peer(bob)

        # Ensure that bob and alice have confirmed funds
        for node in [bob, alice]:
            balance = node.wallet_balance()
            confirmed = balance['confirmed_balance']
            unconfirmed = balance['unconfirmed_balance']
            print(f"Balance in lightning node {node.host} is {confirmed} confirmed, {unconfirmed} unconfirmed")

            if not confirmed > 0:
                if not unconfirmed > 0:
                    funding_amount = 1
                    print(f"Sending {funding_amount} to {node.host}")

                    node_address = node.new_address()
                    mining_wallet.walletpassphrase('password', 5)
                    mining_wallet.sendfrom('imported', node_address, funding_amount)
                print("Generating a block")
                btcd.generate_and_wait(1)

        bob.create_channel(alice)
        btcd.generate_and_wait(1)

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

    def peered(self, other):
        lnd_address = ln.LightningAddress(pubkey=other.pubkey, host=other.host)
        peers = self.stub.ListPeers(ln.ListPeersRequest()).peers
        #print(f"{self.host} is peered with:\n{peers}")

        for peer in peers:
            if peer.pub_key == other.pubkey:
                return True
        return False

    def peer(self, other):
        if self.peered(other):
            print(f"{self.host} already peered with {other.host}")
        else:
            lnd_address = ln.LightningAddress(pubkey=other.pubkey, host=other.host)
            print(f"{self.host} attempting to peer with {other.host}")
            response = self.stub.ConnectPeer(ln.ConnectPeerRequest(addr=lnd_address, perm=True))
            print(response)

            confirmed = False
            while not other.peered(self):
                print(f"Waiting for {other.host} to confirm peering with {self.host}")
                time.sleep(1)
            print("Confirmed")

    def create_channel(self, other):
        response = self.stub.ListChannels(ln.ListChannelsRequest())
        #print(repr(response))

        opened = False
        for channel in response.channels:
            if channel.remote_pubkey == other.pubkey:
                opened = True
                break

        if opened:
            print(f"Already have a channel to {other.host}")
        else:
            print(f"Opening channel to {other.host}")
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
        #print(response)

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

        # XXX should retry
        self.rpc = jsonrpc_requests.Server(url, verify='/rpc/rpc.cert')

        print(f"Connected to {self.name}:",self.rpc.getinfo())

    def __getattr__(self, name):
        # If an attribute is not recognized, assume that it is an RPC method
        return getattr(self.rpc, name)

class BTCWalletRPC(JSONRPCWrapper):
    def __init__(self, host, port=18554):
        super().__init__('btcwallet', host, port)

    def wait_for_block_height(self, height):
        while self.getinfo()['blocks'] < height: 
            print('Waiting for wallet ({wallet_blocks}) to catch up with btcd ({btcd_blocks})')
            time.sleep(1)

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
