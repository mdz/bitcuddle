#!/bin/sh

btcwallet --createtemp --appdata=/data/btcwallet --simnet \
  --btcdusername=devuser --btcdpassword=devpass -u devuser -P devpass \
  --cafile /rpc/rpc.cert \
  --rpclisten 0.0.0.0 --rpccert /rpc/rpc.cert --rpckey /rpc/rpc.key \
  --rpcconnect $RPC_CONNECT
