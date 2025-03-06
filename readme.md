# about

# setup

The docker compose services follow the following policy for environment variables:

- variables that need to be dynamically updated (like AWS credentials with a fixed, short expiration date) will be referenced in the "environment" block of the docker compose service definition and will be read from the users local shell environment.
- Fixed variables will be referenced from a .env file in a env_file block. 

# entering dev environment
```
docker compose up -d
docker compose exec mosaic-dev bash
```

# tests
To run tests use a command of the form:

```
docker compose -f docker-compose-tests.yml run inundate-test
```

Each docker service in the tests docker compose file runs tests for a different job.
