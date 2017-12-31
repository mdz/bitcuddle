#!/bin/sh

btcwallet --createtemp --appdata=/data/btcwallet --simnet \
  --btcdusername=devuser --btcdpassword=devpass \
  --rpclisten 0.0.0.0 --rpccert /rpc/rpc.cert --rpckey /rpc/rpc.key \
  -u devuser -P devpass \
  --cafile /rpc/rpc.cert \
  --rpcconnect $RPC_CONNECT
