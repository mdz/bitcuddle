# bitcuddle

One Paragraph of project description goes here

## To do
* Tests
* Settlement
* Decide on architecture: are Alice and Bob co-located or not?
* Data model and flow for contracts
* API

## Getting Started

```bash
# create the lnd_btc and btcd docker images
git clone git@github.com:devrandom/lnd.git
pushd lnd
git checkout networking
cd docker/lnd
docker-compose build)
popd

# start lnd and bitcuddle
docker-compose up -d lnd_btc bitcuddle
```

### Prerequisites

* docker
* docker-compose
* ssh stanza for compute instance (to run fund script)

## Running the tests

Explain how to run the automated tests for this system
