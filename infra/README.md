# Infrastructure Notes

`docker-compose.yml` provisions local dependencies for development:

- PostgreSQL with pgvector image
- Redis

Run from repository root:

```bash
make up
make down
```

Check effective compose configuration:

```bash
make compose-config
```
