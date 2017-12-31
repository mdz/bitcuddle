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
# build the lnd and btcd docker images
git clone -b networking git@github.com:devrandom/lnd.git
(cd lnd/docker/lnd && docker-compose build)

# start everything up
docker-compose up -d
```

### Prerequisites

* docker
* docker-compose
* ssh stanza for compute instance (to run fund script)

## Running the tests

Explain how to run the automated tests for this system
