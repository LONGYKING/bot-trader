  To get started:

  cp .env.example .env   # fill in your values
  make docker-up         # start Postgres + Redis
  make migrate           # run Alembic migrations
  make seed-api-key      # create first admin key
  make dev               # start the API server
