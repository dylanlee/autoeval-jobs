# about

# setup

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
