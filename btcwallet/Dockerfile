FROM golang:1.8

# Expose btcwallet RPC port
EXPOSE 18554

# Grab and install the latest version of roasbeef's fork of btcd and all
# related dependencies.
RUN go get -u github.com/Masterminds/glide


RUN mkdir "/rpc"

# Create a volume to house pregenerated RPC credentials. This will be
# shared with any lnd, btcctl containers so they can securely query btcd's RPC
# server.
# You should NOT do this before certificate generation!
# Otherwise manually generated certificate will be overriden with shared
# mounted volume! For more info read dockerfile "VOLUME" documentation.
VOLUME ["/rpc"]

#### Install btcwallet

RUN git clone https://github.com/btcsuite/btcwallet.git $GOPATH/src/github.com/btcsuite/btcwallet
#RUN git clone -b bitcuddle https://github.com/mdz/btcwallet.git $GOPATH/src/github.com/btcsuite/btcwallet

WORKDIR $GOPATH/src/github.com/btcsuite/btcwallet

# Install dependencies
RUN glide install
# Build/install btcwallet
RUN go install . ./cmd/...

COPY "start-btcwallet.sh" .

RUN chmod +x start-btcwallet.sh
