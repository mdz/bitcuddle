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

# build btcwallet
(cd btcwallet && docker build . --tag btcwallet)

# start everything up
docker-compose up -d

# check what happened
docker-compose logs -f

# run bitcuddle again, just for fun
docker-compose up bitcuddle
```

## Cleaning up

You might need to do some of:

```bash
docker-compose down
docker volume prune -f
```

### Prerequisites

* docker (should be installed from docker CE repository)
* docker-compose (can be installed via `pip install`)

## Running the tests

Explain how to run the automated tests for this system
