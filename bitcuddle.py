#!/usr/bin/env python3.6 -u

import lnd.rpc_pb2 as ln
import lnd.rpc_pb2_grpc as lnrpc

#import btcwallet.api_pb2 as btcw
#import btcwallet.api_pb2_grpc as btcwrpc
#import requests
import jsonrpc_requests

import grpc
import os
import time
from retrying import retry

class BitCuddle:
    def go(self):
        print("Hello, bitcuddlers!")

        # Initialize the mining wallet
        mining_wallet = BTCWalletRPC('btcwallet')
        mining_wallet.connect()
        mining_wallet.walletpassphrase('password', 0)

        # XXX - This might be better done in start-btcwallet.sh, but the
        # btcwallet container currently lacks btcctl
        mining_key = os.environ['MINING_PRIVATE_KEY']
        print("Importing mining key into wallet")
        print(mining_wallet.importprivkey(mining_key))

        # Connect to btcd
        btcd = BTCDRPC('btcd')
        btcd.connect()

        # Ensure that the mining wallet has confirmed funds
        mining_wallet_balance = mining_wallet.getbalance()

        if not mining_wallet_balance > 0:
            print(f'Generating some blocks to confirm mining funds')
            btcd.generate_and_wait(401)

            mining_wallet.wait_for_block_height(btcd.getinfo()['blocks'])
            # FIXME why are the getinfo height and the processed txs out of sync?
            while mining_wallet.getbalance() == 0:
                print('Still waiting for balance to show')
                time.sleep(2)

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

        # Ensure that bob and alice have confirmed funds
        for node in [bob, alice, hub]:
            balance = node.wallet_balance()
            confirmed = balance['confirmed_balance']
            unconfirmed = balance['unconfirmed_balance']
            print(f"Balance in lightning node {node.host} is {confirmed} confirmed, {unconfirmed} unconfirmed")

            if not confirmed > 0:
                if not unconfirmed > 0:
                    funding_amount = 1
                    print(f"Sending {funding_amount} to {node.host}")

                    node_address = node.new_address()
                    mining_wallet.sendfrom('imported', node_address, funding_amount)
                print("Generating a block")
                btcd.generate_and_wait(1)
                node.wait_for_block_height(btcd.getinfo()['blocks'])

        alice.create_channel(hub)
        while not alice.has_channel(hub):
            print("Waiting for alice channel")
            btcd.generate_and_wait(1)

        hub.create_channel(bob)
        while not hub.has_channel(bob):
            print("Waiting for hub channel to bob")
            btcd.generate_and_wait(1)

        btcd.generate_and_wait(6)

        # wait for channel announcements to propagate
        time.sleep(30)

        alice.send_payment(hub, value=1, memo="Test from alice to hub")
        hub.send_payment(bob, value=1, memo="Test from hub to bob")
        alice.send_payment(bob, value=1, memo="Test from alice to bob")
        bob.send_payment(alice, value=1, memo="Test from bob to alice")

class LightningRPC:
    def __init__(self, host):
        self.host = host
        self.stub = None

    @retry(wait_exponential_multiplier=1000, wait_exponential_max=30000)
    def connect(self):
        print(f"Connecting to lnd on {self.host}")

        cert = open(os.path.expanduser(f'/rpc/lnd-{self.host}.cert')).read()
        #print(cert)
        creds = grpc.ssl_channel_credentials(bytes(cert, 'ascii'))

        channel = grpc.secure_channel(f'{self.host}:10009', creds)
        self.stub = lnrpc.LightningStub(channel)

        response = self.get_info()
        self.pubkey = response.identity_pubkey

    def get_info(self):
        return self.stub.GetInfo(ln.GetInfoRequest())

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
                print(f"{self.host} waiting for {other.host} to confirm peering")
                time.sleep(1)
            print("Confirmed")

    @retry(wait_exponential_multiplier=100, wait_exponential_max=5000)
    def create_channel(self, other):
        if self.has_channel(other):
            print(f"{self.host} already has a channel to {other.host}")
        else:
            print(f"{self.host} opening channel to {other.host}")
            openChannelRequest = ln.OpenChannelRequest(node_pubkey_string=other.pubkey,
                    local_funding_amount=100000,
                    push_sat = 50000,
                    private = False)
            response = self.stub.OpenChannelSync(openChannelRequest)
            print(response)

    def has_channel(self, other):
        exists = False
        active = False
        for channel in self.list_channels():
            if channel.remote_pubkey == other.pubkey and channel.local_balance > 0:
                exists = True
                if channel.active:
                    active = True
                    print(channel)

        print(f"{self.host} has_channel {other.host} exists={exists}, active={active}")

        return exists and active

    def list_channels(self):
        return self.stub.ListChannels(ln.ListChannelsRequest()).channels

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
        if response.payment_error:
            raise Exception(response.payment_error)

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

    def wait_for_block_height(self, height):
        info = self.get_info()
        print(info)
        current = self.get_info().block_height
        while current < height:
            print(f'Waiting for lnd node {self.host} ({current}) to reach {height}')
            time.sleep(1)
            current = self.get_info().block_height

class JSONRPCWrapper:
    def __init__(self, name, host, port):
        self.name = name
        self.host = host
        self.port = port
        self.rpc = None

    @retry(wait_exponential_multiplier=1000, wait_exponential_max=30000)
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
