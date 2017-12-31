#!/usr/bin/env python3.6

import lnd.rpc_pb2 as ln
import lnd.rpc_pb2_grpc as lnrpc

#import btcwallet.api_pb2 as btcw
#import btcwallet.api_pb2_grpc as btcwrpc
import requests

import grpc
import os

class BitCuddle:
    def go(self):
        # Initialize the mining wallet
        wallet = BTCWalletNode('btcwallet')
        wallet.connect()
        print('Wallet balance:', wallet.getbalance())

        mining_address_file = '/rpc/mining_address'
        if not os.path.exists(mining_address_file):
            with open(mining_address_file) as f:
                mining_address = f.read()
        else:
            mining_address = wallet.getnewaddress()
            with open(mining_address_file, 'w') as f:
                f.write(mining_address)
            print(f"Created address {mining_address} for mining")
            
        print(f"Mining address: {mining_address}")

        # Bring up the lightning network
        hub = LightningNode('lnd_hub')
        hub.connect()

        bob = LightningNode('lnd_bob')
        bob.connect()
        bob.peer(hub)

        alice = LightningNode('lnd_alice')
        alice.connect()
        alice.peer(hub)

        # XXX - alice and bob should be able to find each other through the
        # hub, but this doesn't seem to work, so create a direct peering
        # between them
        alice.peer(bob)

        # Ensure that there are funds available to create a channel
        bob_balance = bob.wallet_balance()
        print(f"Bob's balance is {bob_balance}")
        if bob_balance["total_balance"] == 0:
            print("Funding bob from the mining wallet")
            bob_address = bob.new_address()
            wallet.unlock('password', 5)
            wallet.sendtoaddress(bob_address, 1)

        alice.create_channel(bob)

        # wait for block

        bob.send_payment(alice, value=1, memo="Test from bob to alice")
        alice.send_payment(bob, value=1, memo="Test from alice to bob")

class LightningNode:
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

class BTCWalletNode:
    def __init__(self, host):
        self.host = host
        self.stub = None

    def connect(self):
        print(f"Connecting to btcwallet on {self.host}")

        print(self._request("getinfo"))

    # TODO: decorator
    def getbalance(self):
        return self._request("getbalance")

    def getnewaddress(self):
        return self._request("getnewaddress")

    def importprivkey(self, privkey):
        return self._request("importprivkey", [privkey])

    def sendtoaddress(self, dest, amount):
        return self._request("sendtoaddress", [dest, amount])

    def unlock(self, passphrase, timeout):
        return self._request("walletpassphrase", [passphrase, timeout])

    def _request(self, method, params=[]):
        headers = {'content-type': 'application/json'}

        url = f'https://devuser:devpass@{self.host}:18554/'
        request = {
            "method": method,
            "params": params,
            "jsonrpc": "2.0",
            "id": 0
        }
        #print(request)
        resp = requests.post(url, json=request, headers=headers, verify='/rpc/rpc.cert')
        resp.raise_for_status()

        json = resp.json()
        print(json)
        if json['error'] != None:
            raise self.jsonrpc_error(json['error'])

        return json['result']

    class jsonrpc_error(Exception):
        def __init__(self, error):
            self.code = error['code']
            self.message = error['message']

        def __repr__(self):
            return { "code": self.code, "message": self.message }

bitcuddle = BitCuddle()
bitcuddle.go()
