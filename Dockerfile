FROM python:3.6

WORKDIR /usr/src/app

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python -m grpc_tools.protoc --proto_path=vendor --python_out=. --grpc_python_out=. vendor/lnd/rpc.proto
RUN python -m grpc_tools.protoc --proto_path=vendor --python_out=. --grpc_python_out=. vendor/btcwallet/api.proto

VOLUME /rpc

CMD [ "python", "bitcuddle.py" ]
