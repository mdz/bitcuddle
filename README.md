# bitcuddle

One Paragraph of project description goes here

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

### Installing

A step by step series of examples that tell you have to get a development env running

Say what the step will be

```
Give the example
```

And repeat

```
until finished
```

End with an example of getting some data out of the system or using it for a little demo

## Running the tests

Explain how to run the automated tests for this system

## Built With

* stuff

