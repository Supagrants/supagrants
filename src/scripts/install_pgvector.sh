sudo apt install build-essential libpq-dev
sudo apt-get install postgresql-server-dev-14

cd /tmp
git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git
cd pgvector
make
make install # may need sudo